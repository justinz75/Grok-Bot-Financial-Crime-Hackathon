"""Reviewer layer: a language model's second opinion on each clearance.

The rules clear a hit; the model is then shown the same facts and asked one question:
does the stated contradiction hold? It answers agree, disagree or unsure, with one
sentence of reasoning. It is a second pair of eyes, not a judge:

    mode "on"       its opinion is written to the explain file and changes nothing.
    mode "enforce"  a clearance it disagrees with in every run goes to a person.

It can never clear a hit, and it is only ever asked about clearances.
"""
import json

from .. import countries as C
from .. import dates as D
from .model import Client

SYSTEM = (
    "You are the second reviewer of a bank's name-screening decisions. "
    "A first reviewer decided that a watchlist entry is NOT the customer. "
    "Wrongly clearing an entry that is the customer is the worst mistake a reviewer can make. "
    "The bank allows an entry to be cleared only when one of these contradictions holds:\n"
    "1. Time: the customer was younger than 16 at the entry's earliest dated report, a company was "
    "incorporated after it, or the entry died before the customer was screened.\n"
    "2. Date of birth: the customer's birth year is more than one year away from every birth date the "
    "entry gives, or both give a month in the same year and the months differ.\n"
    "3. Country: every country tied to the customer differs from every country tied to the entry.\n"
    "4. Name: the customer's verified legal name agrees with none of the entry's names or aliases.\n"
    "5. Type: one is a person and the other a company.\n"
    "Use only the facts you are given. Check whether the contradiction the first reviewer stated "
    "really holds on those facts. "
    'Reply with one JSON object and nothing else: {"verdict": "agree" or "disagree" or "unsure", '
    '"reason": one sentence naming the facts you relied on}. '
    "Answer agree if the stated contradiction holds, disagree if it does not, "
    "and unsure if the facts given do not settle it."
)
VERDICTS = ("disagree", "unsure", "agree")  # the order ties are broken in: the cautious answer first


def _names(codes):
    return sorted(C.name_of(code) for code in codes)


def evidence_pack(case):
    """The facts of one clearance, as compact JSON: the same text for the same facts."""
    customer, hit, outcome = case.customer, case.hit, case.outcome
    declared = []
    for name, _source in customer.names:
        if name and name not in declared and name != customer.verified_name:
            declared.append(name)
    pack = {
        "customer": {
            "kind": customer.kind,
            "verified_legal_name": customer.verified_name,
            "other_names": declared[:6],
            "date_of_birth": D.show(customer.dob) or None,
            "countries": _names(customer.countries),
            "screened_on": D.show(customer.screened_at) or None,
        },
        "watchlist_entry": {
            "kind": hit.kind,
            "name": hit.name,
            "aliases": list(hit.names[1:13]),
            "dates_of_birth": [D.show(d) for d in hit.dobs],
            "dates_of_birth_taken_from": hit.dob_origin,
            "countries": _names(hit.countries),
            "earliest_dated_report": D.show(hit.earliest_report) or None,
            "date_of_death": D.show(hit.death) or None,
        },
        "first_reviewer": {
            "decision": outcome.decision,
            "grounds": list(outcome.codes),
            "stated_reasons": list(outcome.sentences),
        },
    }
    return json.dumps(pack, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def question(case):
    return "Facts:\n" + evidence_pack(case) + "\nDoes the stated contradiction hold?"


class Reviewer(object):
    def __init__(self, store, mode, client=None):
        self.store = store
        self.mode = mode
        self.client = client or Client()

    def _wanted(self, case):
        return case.outcome.decision == "DIFFERENT_ENTITY" and self.client.available

    def annotate(self, case):
        """The model's opinion of one clearance, or None when there is nothing to say."""
        if not self._wanted(case):
            return None
        try:
            answers = self.client.samples(SYSTEM, question(case))
        except Exception:
            return None
        counts, reasons = {}, {}
        for answer in answers:
            if not isinstance(answer, dict):
                continue
            verdict = answer.get("verdict")
            verdict = verdict.strip().lower() if isinstance(verdict, str) else None
            if verdict not in VERDICTS:
                continue
            counts[verdict] = counts.get(verdict, 0) + 1
            reason = answer.get("reason")
            if verdict not in reasons and isinstance(reason, str) and reason.strip():
                reasons[verdict] = " ".join(reason.split())[:300]
        if not counts:
            return None
        verdict = sorted(counts, key=lambda v: (-counts[v], VERDICTS.index(v)))[0]
        return {
            "verdict": verdict,
            "reason": reasons.get(verdict, ""),
            "model": self.client.model,
            "runs": len(answers),
            "agreement": round(counts[verdict] / float(len(answers)), 2),
        }

    def guard(self, case, note):
        """Why this clearance needs a person: only when every run disagreed with it."""
        if not note or note.get("verdict") != "disagree" or note.get("agreement") != 1.0:
            return None
        reason = (note.get("reason") or "").rstrip(".")
        if reason:
            return "a language model reviewing the same facts disagreed (%s)" % reason
        return "a language model reviewing the same facts disagreed"

    def warm(self, cases):
        """Ask about every clearance at once, so annotate() finds the answers already there."""
        asks = []
        for case in cases:
            if self._wanted(case):
                text = question(case)
                asks.extend((SYSTEM, text, run) for run in range(self.client.runs))
        if asks:
            self.client.ask_all(asks)
        return len(asks)


def build(store, mode, client=None):
    return Reviewer(store, mode, client)
