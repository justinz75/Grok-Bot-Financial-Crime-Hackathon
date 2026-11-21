"""A small OpenRouter client for the model layers. Standard library only.

The model never decides anything that is scored. It is asked narrow questions that
have a JSON answer, at temperature 0 with a fixed seed, and every way it can fail
(no key, timeout, an error status, a reply that is not JSON, the time budget used up)
comes back as None: "no answer". Callers treat no answer as nothing learned.

Set SCREENING_MODEL=fake to run without a key or a network: a built-in, fully
deterministic stand-in answers instead, which is enough to exercise every code path.
"""
import hashlib
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-4o-mini"
FAKE = "fake"
RETRIES = 2            # extra attempts after the first, on a network error or HTTP 429/5xx
PAUSE_SECONDS = 1.5    # fixed pause between attempts

# Indirections so tests can replace the network and the pause without touching either.
_open = urllib.request.urlopen
_sleep = time.sleep


def first_json(text):
    """The first JSON object in a reply, or None. Models wrap JSON in prose or fences."""
    if not isinstance(text, str):
        return None
    decoder = json.JSONDecoder()
    start = text.find("{")
    while start != -1:
        try:
            value, _end = decoder.raw_decode(text[start:])
        except ValueError:
            value = None
        if isinstance(value, dict):
            return value
        start = text.find("{", start + 1)
    return None


def _canonical(answer):
    return json.dumps(answer, sort_keys=True, ensure_ascii=False)


class Client(object):
    def __init__(self, model=None, key=None, fake=None, runs=None, budget_seconds=600,
                 max_workers=8, timeout=25, clock=None):
        chosen = model or os.environ.get("SCREENING_MODEL", "").strip() or DEFAULT_MODEL
        if chosen.lower() == FAKE and fake is None:
            fake = builtin_fake
        self.model = chosen
        self.fake = fake
        self.key = (key if key is not None else os.environ.get("OPENROUTER_API_KEY", "")).strip()
        if runs is None:
            try:
                runs = int(os.environ.get("SCREENING_MODEL_RUNS", "1"))
            except ValueError:
                runs = 1
        self.runs = max(1, int(runs))
        self.budget_seconds = budget_seconds
        self.max_workers = max(1, int(max_workers))
        self.timeout = timeout
        self._clock = clock or time.time
        self._lock = threading.Lock()
        self._cache = {}
        self._pending = {}
        self._started = None
        self._last = None
        self._calls = self._hits = self._failures = self._skipped = 0

    @property
    def available(self):
        """True when there is something to ask: a key, or a stand-in."""
        return bool(self.fake or self.key)

    # -- asking -----------------------------------------------------------------------
    def ask(self, system_prompt, user_prompt, run=0):
        """The model's JSON answer as a dict, or None. The same question with the same
        run index is asked once; later asks get the remembered answer."""
        if not self.available:
            return None
        digest = hashlib.sha256(
            json.dumps([self.model, system_prompt, user_prompt, run], ensure_ascii=False).encode("utf-8")).hexdigest()
        with self._lock:
            if digest in self._cache:
                self._hits += 1
                return self._copy(self._cache[digest])
            waiting = self._pending.get(digest)
            if waiting is None:
                now = self._clock()
                if self._started is None:
                    self._started = now
                if now - self._started > self.budget_seconds:
                    self._skipped += 1
                    return None
                self._pending[digest] = threading.Event()
                self._calls += 1
        if waiting is not None:  # another thread is already asking this exact question
            waiting.wait(self.timeout * (RETRIES + 2))
            with self._lock:
                self._hits += 1
                return self._copy(self._cache.get(digest))
        answer = None
        try:
            answer = first_json(self._reply(system_prompt, user_prompt))
        except Exception:
            answer = None
        with self._lock:
            if answer is None:
                self._failures += 1
            self._cache[digest] = answer
            self._last = self._clock()
            self._pending.pop(digest).set()
        return self._copy(answer)

    @staticmethod
    def _copy(answer):
        return json.loads(json.dumps(answer)) if answer is not None else None

    def ask_all(self, items):
        """Answers for (system, user, run) tuples, in the order given, asked concurrently."""
        items = list(items)
        if len(items) <= 1 or self.max_workers == 1:
            return [self.ask(*item) for item in items]
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(items))) as pool:
            return list(pool.map(lambda item: self.ask(*item), items))

    def samples(self, system_prompt, user_prompt):
        """One answer per run (run index 0 .. runs-1)."""
        return self.ask_all([(system_prompt, user_prompt, run) for run in range(self.runs)])

    def consensus(self, system_prompt, user_prompt):
        """(answer, agreement). The answer is given only when every run returned the same
        JSON; agreement is the share of runs that gave the most common answer."""
        answers = self.samples(system_prompt, user_prompt)
        counts = {}
        for answer in answers:
            if answer is not None:
                counts[_canonical(answer)] = counts.get(_canonical(answer), 0) + 1
        if not counts:
            return None, 0.0
        top, count = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0]
        agreement = count / float(len(answers))
        return (json.loads(top) if count == len(answers) else None), agreement

    def stats(self):
        with self._lock:
            seconds = (self._last - self._started) if self._started is not None and self._last is not None else 0.0
            return {"model": self.model, "runs": self.runs, "calls": self._calls, "cache_hits": self._hits,
                    "failures": self._failures, "skipped": self._skipped, "seconds": round(seconds, 2)}

    # -- the wire ---------------------------------------------------------------------
    def _reply(self, system_prompt, user_prompt):
        """The model's reply text, or None."""
        if self.fake is not None:
            return self.fake(system_prompt, user_prompt)
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            "temperature": 0, "top_p": 1, "seed": 7, "max_tokens": 300,
            "response_format": {"type": "json_object"},
        }
        for attempt in range(RETRIES + 1):
            request = urllib.request.Request(
                URL, data=json.dumps(body).encode("utf-8"), method="POST",
                headers={"Authorization": "Bearer " + self.key, "Content-Type": "application/json"})
            try:
                with _open(request, timeout=self.timeout) as response:
                    payload = json.loads(response.read().decode("utf-8", "replace"))
                content = payload["choices"][0]["message"]["content"]
                if isinstance(content, list):  # some providers return the text in parts
                    content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
                return content
            except urllib.error.HTTPError as error:
                code = error.code
                try:
                    error.close()  # an error response still holds a connection
                except Exception:
                    pass
                if code == 400 and "response_format" in body:
                    # this model does not take the optional settings: ask again without them
                    body.pop("response_format", None)
                    body.pop("seed", None)
                    continue
                if code != 429 and code < 500:
                    return None  # a bad key, no credit, an unknown model: asking again will not help
            except (urllib.error.URLError, OSError, ValueError, KeyError, IndexError, TypeError):
                pass
            if attempt < RETRIES:
                _sleep(PAUSE_SECONDS)
        return None


# -- a deterministic stand-in for the model --------------------------------------------
_NOTE = re.compile(r"<<<\n(.*?)\n>>>", re.S)
_CAPITAL = re.compile(r"^[A-ZÀ-Þ][A-Za-zÀ-ÿ'’-]*$")
_FAKE_STOP = frozenset((
    # months
    "january february march april may june july august september october november december "
    "jan feb mar apr jun jul aug sep sept oct nov dec "
    # words that start sentences
    "on the a an in at by for per as this that it its his her their he she they we with after "
    "following during upon when using via from to of and or "
    # document and process words
    "identity id kyc dob date birth document documents documentation passport driving licence license "
    "national card permit registry extract certificate check checks verification verified validation "
    "validated authenticated confirmed approved cleared review result record records name customer "
    "client holder subject applicant individual user account onboarding team note "
    # identity-check providers
    "sumsub veriff persona onfido jumio trulioo idnow yoti socure mitek"
).split())


def builtin_fake(system_prompt, user_prompt):
    """Answers reader and reviewer questions by fixed rules. Not a model: a stand-in so
    the model layers can be run, timed and tested without a key."""
    from .. import countries as C
    from .. import dates as D
    from .. import extract as X

    if "verdict" in system_prompt:
        return json.dumps({"verdict": "agree", "reason": "The stated contradiction holds on the facts given."})
    found = _NOTE.search(user_prompt)
    note = found.group(1) if found else user_prompt

    tokens = note.split() + [""]
    words = []
    for token in tokens:
        word = token.strip("()[]{}\"'‘’“”,.;:!?")
        if word.endswith("'s") or word.endswith("’s"):
            word = word[:-2]
        words.append(word)
    places = set()  # positions inside a country name, which may be several words long
    for width in (4, 3, 2, 1):
        for start in range(len(words) - width + 1):
            phrase = " ".join(words[start:start + width])
            code = C.resolve(phrase) if phrase.strip() else None
            if code is not None and code != C.IGNORED:
                places.update(range(start, start + width))

    best, run = [], []
    for position, token in enumerate(tokens):
        word = words[position]
        is_name = bool(word) and _CAPITAL.match(word) is not None and word.lower() not in _FAKE_STOP \
            and position not in places
        if is_name:
            run.append(word)
        if run and (not is_name or token != token.rstrip(",.;:!?)")):
            if sum(len(w) for w in run) > sum(len(w) for w in best):
                best = run
            run = []
    name = " ".join(best) if best else None
    if name and name not in note:
        name = None

    born, date = X._BORN.search(note), None
    if born:
        after = D.find_dates(note[born.end():], bare_years=True)
        if after:
            date = note[born.end() + after[0][1]:born.end() + after[0][2]]
    country = None
    for code in sorted(C.DISPLAY):
        display = C.DISPLAY[code]
        if re.search(r"(?<![A-Za-z])" + re.escape(display) + r"(?![A-Za-z])", note):
            country = display
            break
    outcome = "failed" if X._FAILED.search(note) else "passed"
    return json.dumps({"legal_name": name, "date_of_birth": date, "document_country": country, "outcome": outcome})
