"""The run: resolve the customer, resolve the hit, decide, write one line per hit.

The rules decide. Optional layers (see layers/__init__.py) add to an explain file and,
only when set to enforce, may turn a clearance into a review. With every layer at its
default the scored file is exactly what the rules alone produce.

No clock and no randomness in the decision path: the same folder gives the same file.
"""
import json
import os
import sys
import time

from . import countries as C
from . import dates as D
from . import layers
from .decide import AMBIGUOUS, DIFFERENT, REVIEW, Outcome, combine, decide, states
from .resolve import Resolver
from .store import Store, find_folder, read_jsonl, text
from .watchlist import build_hit


def _found_sentence(how, people):
    """How the alert was resolved to a customer, in one sentence."""
    if not people:
        return "No customer record fits the %s, so only the screened details could be compared." % how
    if len(people) > 1:
        records = ", ".join(rid for group, _ in people for rid in group)
        return "%d different people fit the %s (records %s)." % (len(people), how, records)
    group, first = people[0]
    others = [r for r in group if r != first]
    extra = ", and %s %s the same person" % (", ".join(others), "is" if len(others) == 1 else "are") if others else ""
    if how.startswith("screened"):
        return "The %s fit customer record %s%s." % (how, first, extra)
    return "The alert's %s leads to customer record %s%s." % (how, first, extra)


def _customer_view(customer):
    names = []
    for name, _source in customer.names:
        if name and name not in names:
            names.append(name)
    return {
        "kind": customer.kind, "verified_name": customer.verified_name,
        "verified_source": customer.verified_source, "names": names,
        "dob": D.show(customer.dob) or None, "dob_source": customer.dob_source,
        "countries": [{"code": code, "name": C.name_of(code), "sources": sorted(s for s in customer.countries[code] if s)}
                      for code in sorted(customer.countries)],
    }


def _hit_view(hit):
    return {
        "kind": hit.kind, "name": hit.name, "aliases": hit.names[1:],
        "dobs": [D.show(d) for d in hit.dobs], "dob_origin": hit.dob_origin,
        "countries": [{"code": code, "name": C.name_of(code)} for code in sorted(hit.countries)],
        "earliest_report": D.show(hit.earliest_report) or None, "death": D.show(hit.death) or None,
    }


class Run(object):
    def __init__(self, folder, modes=None):
        self.store = Store(folder)
        self.modes = dict(modes) if modes else layers.config()
        self.problems = []
        self.resolver = Resolver(self.store, layers.load_reader(self.store, self.modes, self.problems))
        self.enforcing = any(self.modes.get(name) == "enforce" for name in layers.ORDER)
        self._layers = None
        self._alerts = {}
        self._resolved = {}
        self._hits = {}

    @property
    def layers(self):
        """The annotating layers, built the first time something needs them: a plain
        scored run with nothing enforcing never loads them."""
        if self._layers is None:
            self._layers = layers.load(self.store, self.modes, self.problems)
        return self._layers

    def _people(self, alert):
        """(screened details, how found, people) for an alert, resolved once."""
        alert_id = text(alert.get("alert_id"))
        if alert_id not in self._resolved:
            self._resolved[alert_id] = self.resolver.people(alert)
        return self._resolved[alert_id]

    def customers_of(self, alert):
        """(found sentence, [Customer per distinct person], how many people) for an alert, built once."""
        alert_id = text(alert.get("alert_id"))
        if alert_id not in self._alerts:
            screened, how, people = self._people(alert)
            if people:
                pictures = [self.resolver.picture(group, first, screened) for group, first in people]
            else:
                pictures = [self.resolver.screened_only(screened)]
            self._alerts[alert_id] = (_found_sentence(how, people), pictures, len(people))
        return self._alerts[alert_id]

    def _hit(self, row):
        hit_id = text(row.get("hit_id"))
        if hit_id not in self._hits:
            self._hits[hit_id] = build_hit(row, self.store)
        return self._hits[hit_id]

    def warm(self, with_layers):
        """Let the model-backed layers fetch what they need in one concurrent batch, so
        the run itself only reads answers. Layers without a warm() are untouched."""
        reader = self.resolver.read_note
        if hasattr(reader, "warm"):
            items = []
            for alert in self.store.alerts:
                for group, _first in self._people(alert)[2]:
                    for rid in group:
                        for note in self.store.notes_of(rid):
                            items.append((text(note.get("text")), note.get("created_at"),
                                          text(note.get("channel")).lower() == "kyc"))
            reader.warm(items)
        warmers = [layer for _n, _m, layer in self.layers if hasattr(layer, "warm")] if with_layers else []
        if warmers:
            cases = []
            for row in self.store.hits:
                alert = self.store.alert.get(text(row.get("alert_id"))) or self.store.alert_of_hit.get(text(row.get("hit_id")))
                if alert is None:
                    continue
                hit = self._hit(row)
                for customer in self.customers_of(alert)[1]:
                    outcome = decide(customer, hit, self.store.rules)
                    cases.append(layers.Case(self.store, alert, row, customer, hit, outcome,
                                             states(customer, hit, self.store.rules), {}))
            for layer in warmers:
                layer.warm(cases)

    def _layered(self, alert, row, customer, hit, outcome):
        """Run the layers for one person. Returns (outcome to use, explain entry, change)."""
        st = states(customer, hit, self.store.rules)
        notes = {}
        case = layers.Case(self.store, alert, row, customer, hit, outcome, st, notes)
        for name, _mode, layer in self.layers:
            try:
                notes[name] = layer.annotate(case)
            except Exception as error:  # a layer that fails says nothing; the rules still stand
                notes[name] = None
                self.problems.append("%s failed on %s: %s" % (name, hit.hit_id, type(error).__name__))
        change, final = None, outcome
        if outcome.decision == DIFFERENT:
            for name, mode, layer in self.layers:
                if mode != "enforce" or not hasattr(layer, "guard"):
                    continue
                try:
                    why = layer.guard(case, notes.get(name))
                except Exception:
                    why = None
                if why:
                    change = {"layer": name, "why": why}
                    sentence = ("The rules found a contradiction (%s), but %s, so a person has to review it."
                                % (outcome.code, why.rstrip(".")))
                    final = Outcome(REVIEW, ["INSUFFICIENT_DATA"], [sentence], outcome.evidence, outcome.record_id)
                    break
        entry = {
            "record_ids": list(customer.record_ids),
            "decision": outcome.decision, "reason_code": outcome.code, "all_codes": list(outcome.codes),
            "customer": _customer_view(customer), "hit": _hit_view(hit),
            "states": {"name": st["name"], "dob": st["dob"], "location": st["location"]},
            "score": notes.get("score"), "briefing": notes.get("briefing"), "review": notes.get("reviewer"),
        }
        return final, entry, change

    def process(self, row, explain=False):
        """Decide one hit. Returns (scored line, explain line or None)."""
        hit_id, alert_id = text(row.get("hit_id")), text(row.get("alert_id"))
        alert = self.store.alert.get(alert_id) or self.store.alert_of_hit.get(hit_id)
        entries, change, found = [], None, ""
        if alert is None:
            outcome = rules_outcome = Outcome(
                REVIEW, ["INSUFFICIENT_DATA"],
                ["The hit's alert is not in the data, so the customer is unknown and a person has to review it."], [])
        else:
            found, pictures, count = self.customers_of(alert)
            hit = self._hit(row)
            by_rules = [decide(c, hit, self.store.rules) for c in pictures]
            final = list(by_rules)
            if explain or self.enforcing:
                for index, customer in enumerate(pictures):
                    final[index], entry, changed = self._layered(alert, row, customer, hit, by_rules[index])
                    entries.append(entry)
                    change = change or changed
            rules_outcome, outcome = combine(by_rules), combine(final)
            for o in (rules_outcome, outcome):
                if count > 1:
                    o.record_id = AMBIGUOUS
                elif count == 0:
                    o.record_id = None
        line = {
            "hit_id": hit_id,
            "alert_id": alert_id or (text(alert.get("alert_id")) if alert else ""),
            "decision": outcome.decision,
            "reason_code": outcome.code,
            "customer_record_id": outcome.record_id,
            "reason": " ".join(([found] if found else []) + outcome.sentences[:3]),
            "evidence": outcome.evidence,
        }
        if not explain:
            return line, None
        return line, {
            "hit_id": line["hit_id"], "alert_id": line["alert_id"], "decision": line["decision"],
            "reason_code": line["reason_code"], "customer_record_id": line["customer_record_id"],
            "rules": {"decision": rules_outcome.decision, "reason_code": rules_outcome.code},
            "changed_by": change, "layers": dict(self.modes), "people": entries,
        }

    def decide_hit(self, row):
        return self.process(row)[0]


def _unprocessed(row, error):
    """A hit that could not be processed goes to a person: never a silent clearance."""
    return {
        "hit_id": text(row.get("hit_id")), "alert_id": text(row.get("alert_id")),
        "decision": REVIEW, "reason_code": "INSUFFICIENT_DATA", "customer_record_id": None,
        "reason": "This hit could not be processed (%s), so a person has to review it." % type(error).__name__,
        "evidence": [],
    }


def _write(path, rows):
    parent = os.path.dirname(os.path.abspath(path))
    if not os.path.isdir(parent):
        os.makedirs(parent)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def run(folder, output, explain=None, modes=None):
    """Write the scored file, and the explain file when a path for it is given."""
    started = time.time()
    lines, notes, problems = [], [], []
    try:
        job = Run(folder, modes)
        hits = job.store.hits
    except Exception as error:  # the folder could not be loaded: every hit still gets a line
        job, hits = None, read_jsonl(os.path.join(find_folder(folder), "hits.jsonl"))
        lines = [_unprocessed(row, error) for row in hits]
        problems.append("the data folder could not be loaded: %s" % type(error).__name__)
    if job:
        try:
            job.warm(bool(explain) or job.enforcing)
        except Exception as error:  # a failed pre-fetch only means answers are fetched one by one
            problems.append("pre-fetch failed: %s" % type(error).__name__)
    for row in (hits if job else []):
        try:
            line, note = job.process(row, explain=bool(explain))
        except Exception as error:  # one unreadable hit must not lose the rest
            line, note = _unprocessed(row, error), None
        lines.append(line)
        if explain:
            notes.append(note or dict(line, rules={"decision": line["decision"], "reason_code": line["reason_code"]},
                                      changed_by=None, layers={}, people=[]))
    _write(output, lines)
    if explain:
        for note in notes:
            note.pop("reason", None)
            note.pop("evidence", None)
        _write(explain, notes)
    counts = {}
    for line in lines:
        counts[line["decision"]] = counts.get(line["decision"], 0) + 1
    if job:
        problems += job.problems
        modes_text = ", ".join("%s=%s" % (name, job.modes.get(name, "off")) for name in layers.NAMES)
    else:
        modes_text = "not loaded"
    sys.stderr.write("%d hits decided in %.1fs: %s\n" % (
        len(lines), time.time() - started, ", ".join("%s %d" % kv for kv in sorted(counts.items()))))
    sys.stderr.write("layers: %s\n" % modes_text)
    for problem in sorted(set(problems))[:10]:
        sys.stderr.write("note: %s\n" % problem)
    return lines
