"""Name rules (POLICY.md principle 8).

Two names agree when at least two parts match, or every part of the shorter name
matches. Parts are compared ignoring case, accents, punctuation and brackets.
"""
import json
import re

from .textutil import fold, words

# Fallback copy of name_variants.json; the file in the data folder wins when present.
DEFAULT_VARIANT_GROUPS = [
    "muhammad mohammed mohammad mohamed muhammed mohamad mohd muhamad",
    "ahmed ahmad ahmet", "abdul abdel abd", "abdullah abdallah abdulla",
    "abubakar abubakr aboubakar bubakar", "ibrahim ebrahim ibraheem brahim",
    "yusuf yousef youssef yousuf josef joseph joe", "umar omar omer",
    "usman uthman othman osman", "hussein hussain husain hossain hosein",
    "hassan hasan", "ali aly", "faruk farouk faruq farooq faroq",
    "sulaiman suleiman sulayman suleman solomon", "aminu amin ameen",
    "anthony antony tony antonio", "robert rob robbie bob bobby roberto",
    "william will bill billy liam guillermo", "richard rick ricky dick ricardo",
    "james jim jimmy jamie jaime", "john johnny jon jack juan jean johann johannes",
    "michael mike mick mikey miguel michel michele", "daniel dan danny dani",
    "david dave davey davit", "christopher chris kristopher cristobal",
    "matthew matt mateo matteo mathieu", "andrew andy drew andres andrea andreas",
    "thomas tom tommy tomas tomasz", "joshua josh",
    "nicholas nick nicolas nicola nikola nikolai",
    "alexander alex alejandro alessandro aleksandr sasha", "peter pete pedro pietro pierre",
    "paul pablo paolo", "stephen steven steve stefan esteban stefano",
    "joseph joe jose giuseppe jozef", "francis frank francisco francesco franco francois",
    "charles charlie chuck carlos carlo karl karol", "edward ed eddie ted eduardo edoardo",
    "henry harry enrique enrico henrik heinrich", "mark marc marco", "markus marcus marcos",
    "catherine katherine kathryn kate katie cathy catalina katarzyna",
    "elizabeth liz beth betty elisabeth isabel", "margaret maggie meg peggy margarita",
    "jennifer jen jenny", "rebecca becky", "susan sue susanna susana",
    "maria mary marie mariya", "olumide mide", "oluwaseun seun", "babatunde tunde",
    "oluwatobiloba tobi", "chukwuemeka emeka", "ifeanyichukwu ifeanyi", "nnamdi namdi",
]
DEFAULT_LEGAL_FORMS = (
    "ab ag as asa bv co company corp corporation gmbh inc kg limited llc llp lp ltd "
    "na nv oy oyj plc sa sarl sas se sf sl spa srl"
)

# "NA, N/A, TEST, UNKNOWN, XXX, NONE, digits and the like" are not name parts.
PLACEHOLDERS = frozenset(
    "na test unknown none null nil tbc tbd dummy noname placeholder anonymous undefined".split()
)

_BRACKETED = re.compile(r"\([^()]*\)|\[[^\[\]]*\]|\{[^{}]*\}")
_MAX_PARTS = 14


def strip_brackets(text):
    """Drop anything in brackets, innermost first."""
    prev = None
    while prev != text:
        prev = text
        text = _BRACKETED.sub(" ", text)
    return re.sub(r"[()\[\]{}]", " ", text)


def _is_placeholder(token):
    return token in PLACEHOLDERS or token.isdigit() or (len(token) >= 2 and set(token) == {"x"})


def _within(a, b, limit):
    """True when a and b differ by at most `limit` edits (add, remove or change a letter)."""
    if abs(len(a) - len(b)) > limit:
        return False
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        if min(cur) > limit:
            return False
        prev = cur
    return prev[-1] <= limit


def _strings(node):
    """All strings inside a JSON value; comma lists are split."""
    if isinstance(node, str):
        return [p.strip() for p in node.split(",") if p.strip()]
    if isinstance(node, (list, tuple)):
        return [s for item in node for s in _strings(item)]
    return []


class NameRules:
    def __init__(self, variant_groups=None, legal_forms=None):
        groups = DEFAULT_VARIANT_GROUPS if variant_groups is None else variant_groups
        forms = DEFAULT_LEGAL_FORMS if legal_forms is None else legal_forms
        self.groups = {}  # folded form -> ids of the groups listing it
        for gid, group in enumerate(groups):
            members = group.split() if isinstance(group, str) else list(group)
            for member in members:
                for token in words(fold(member)):
                    self.groups.setdefault(token, set()).add(gid)
        forms = forms.split() if isinstance(forms, str) else list(forms)
        self.legal_forms = frozenset(t for f in forms for t in words(fold(f)))
        self._cache = {}

    @classmethod
    def from_file(cls, path):
        """Read name_variants.json: {"groups": [[forms...], ...], "company_legal_forms": [...]}.
        A missing or unreadable file falls back to the built-in copy."""
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            return cls()
        groups, forms = [], []
        items = data.items() if isinstance(data, dict) else [("groups", data)]
        for key, value in items:
            if not isinstance(value, list):
                continue
            if re.search(r"legal|form|compan", str(key), re.I):
                forms.extend(_strings(value))
                continue
            for group in value:
                members = _strings(group)
                if len(members) >= 2:
                    groups.append(members)
        return cls(groups or None, forms or None)

    # -- parts ---------------------------------------------------------------
    def parts(self, raw, company=False):
        """The distinct real parts of a name, in order."""
        if not raw:
            return ()
        key = (raw, company)
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        out = []
        for token in words(fold(strip_brackets(str(raw)))):
            if len(token) < 2 or _is_placeholder(token):
                continue  # initials and placeholders are not parts
            if company and token in self.legal_forms:
                continue
            if token not in out:
                out.append(token)
        out = tuple(out[:_MAX_PARTS])
        self._cache[key] = out
        return out

    def part_match(self, a, b):
        if a == b:
            return True
        ga, gb = self.groups.get(a), self.groups.get(b)
        if ga and gb and ga & gb:
            return True
        shorter = min(len(a), len(b))
        if shorter < 4:
            return False
        return _within(a, b, 1 if shorter <= 6 else 2)

    # -- agreement -----------------------------------------------------------
    def _best(self, a, b, cover):
        """Most matched units between part lists a and b, each part used once.
        A part written together on one side and apart on the other is one unit.
        With cover=True every part of `a` must be used; returns -1 if impossible."""
        n, m = len(a), len(b)
        memo = {}
        fail = -1

        def go(i, used):
            if i >= n:
                return 0
            key = (i, used)
            if key in memo:
                return memo[key]
            best = fail if cover else go(i + 1, used)
            for j in range(m):
                if used >> j & 1:
                    continue
                if self.part_match(a[i], b[j]):
                    rest = go(i + 1, used | 1 << j)
                    if rest != fail:
                        best = max(best, 1 + rest)
                for width in (2, 3):  # a[i..] written apart, b[j] together
                    if i + width <= n and "".join(a[i:i + width]) == b[j]:
                        rest = go(i + width, used | 1 << j)
                        if rest != fail:
                            best = max(best, 1 + rest)
            for width in (2, 3):  # a[i] together, b[j..] written apart
                for j in range(m - width + 1):
                    mask = ((1 << width) - 1) << j
                    if not used & mask and a[i] == "".join(b[j:j + width]):
                        rest = go(i + 1, used | mask)
                        if rest != fail:
                            best = max(best, 1 + rest)
            memo[key] = best
            return best

        return go(0, 0)

    def agree(self, a, b):
        """Names agree when at least two parts match, or every part of the shorter
        name matches."""
        if not a or not b:
            return False
        if self._best(a, b, False) >= 2:
            return True
        return self._best(a, b, True) > 0 or self._best(b, a, True) > 0

    def names_agree(self, raw_a, raw_b, company=False):
        return self.agree(self.parts(raw_a, company), self.parts(raw_b, company))
