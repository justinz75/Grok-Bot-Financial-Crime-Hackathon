"""The run: resolve the customer, resolve the hit, decide, write one line per hit.

No clock, no randomness and no network: the same folder always gives the same file.
"""
import json
import sys
import time

from .decide import AMBIGUOUS, REVIEW, Outcome, combine, decide
from .resolve import Resolver
from .store import Store, text
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


class Run(object):
    def __init__(self, folder):
        self.store = Store(folder)
        self.resolver = Resolver(self.store)
        self._alerts = {}

    def customers_of(self, alert):
        """(found sentence, [Customer per distinct person]) for an alert, built once."""
        alert_id = text(alert.get("alert_id"))
        if alert_id not in self._alerts:
            screened, how, people = self.resolver.people(alert)
            if people:
                pictures = [self.resolver.picture(group, first, screened) for group, first in people]
            else:
                pictures = [self.resolver.screened_only(screened)]
            self._alerts[alert_id] = (_found_sentence(how, people), pictures, len(people))
        return self._alerts[alert_id]

    def decide_hit(self, row):
        hit_id, alert_id = text(row.get("hit_id")), text(row.get("alert_id"))
        alert = self.store.alert.get(alert_id) or self.store.alert_of_hit.get(hit_id)
        if alert is None:
            outcome = Outcome(REVIEW, ["INSUFFICIENT_DATA"],
                              ["The hit's alert is not in the data, so the customer is unknown and a person has to review it."], [])
            found = ""
        else:
            found, pictures, count = self.customers_of(alert)
            hit = build_hit(row, self.store)
            outcome = combine([decide(c, hit, self.store.rules) for c in pictures])
            if count > 1:
                outcome.record_id = AMBIGUOUS
            elif count == 0:
                outcome.record_id = None
        sentences = ([found] if found else []) + outcome.sentences[:3]
        return {
            "hit_id": hit_id,
            "alert_id": alert_id or (text(alert.get("alert_id")) if alert else ""),
            "decision": outcome.decision,
            "reason_code": outcome.code,
            "customer_record_id": outcome.record_id,
            "reason": " ".join(sentences),
            "evidence": outcome.evidence,
        }


def run(folder, output):
    started = time.time()
    job = Run(folder)
    lines = []
    for row in job.store.hits:
        try:
            lines.append(job.decide_hit(row))
        except Exception as error:  # one unreadable hit must not lose the rest: it goes to review
            lines.append({
                "hit_id": text(row.get("hit_id")), "alert_id": text(row.get("alert_id")),
                "decision": REVIEW, "reason_code": "INSUFFICIENT_DATA", "customer_record_id": None,
                "reason": "This hit could not be processed (%s), so a person has to review it." % type(error).__name__,
                "evidence": [],
            })
    with open(output, "w", encoding="utf-8", newline="\n") as handle:
        for line in lines:
            handle.write(json.dumps(line, ensure_ascii=False) + "\n")
    counts = {}
    for line in lines:
        counts[line["decision"]] = counts.get(line["decision"], 0) + 1
    sys.stderr.write("%d hits decided in %.1fs: %s\n" % (
        len(lines), time.time() - started, ", ".join("%s %d" % kv for kv in sorted(counts.items()))))
    return lines
