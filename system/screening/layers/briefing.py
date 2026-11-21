"""The analyst briefing layer.

For one customer against one hit it says, in plain sentences, what decided the hit,
which facts were not available, and what one more fact would settle it. It reads the
rules' outcome and the two pictures; it decides nothing and changes nothing.

Arithmetic and wording only: no model, no randomness, the same input gives the same text.
"""
from .. import countries as C
from .. import dates as D
from ..decide import COMPANY, DIFFERENT, REVIEW, SAME

KEYS = ("headline", "decided_by", "missing", "would_settle", "strength", "caveats")
_NUMBER_WORDS = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}
# Closing sentences of a review that state no fact of their own.
_CLOSING = (
    "Nothing in the customer's records contradicts the hit",
    "The screened details are unverified",
    "Each of them leads to the same decision",
    "This hit could not be processed",
    "The hit's alert is not in the data",
)
_POLICY_TAIL = ", and a country difference does not clear"
_ONE_GROUND = {
    "LOCATION_MISMATCH": "one ground, country only",
    "NAME_MISMATCH_VERIFIED": "one ground, the verified legal name",
    "TEMPORAL_IMPOSSIBILITY": "one ground, timing",
    "DECEASED": "one ground, date of death",
    "ENTITY_TYPE_MISMATCH": "one ground, entity type",
}


def build(store, mode):
    return Briefing()


def _empty(headline="Needs a person: the briefing could not be written for this hit."):
    return {"headline": headline, "decided_by": [], "missing": [], "would_settle": [],
            "strength": "open", "caveats": []}


def _join(items, last="and"):
    items = [str(i) for i in items]
    if len(items) <= 1:
        return "".join(items)
    return "%s %s %s" % (", ".join(items[:-1]), last, items[-1])


def _countries(codes, last="and"):
    return _join(sorted(C.name_of(c) for c in codes), last)


def _sentence(text):
    text = str(text).strip()
    return text if text.endswith((".", "!", "?")) else text + "."


def _years(dates):
    return sorted(set(d.year for d in dates))


def _gap(dob, hit_dobs):
    """Fewest years between the customer's birth year and any year the hit gives."""
    return min(abs(dob.year - d.year) for d in hit_dobs)


def _words(kind_is_company):
    """The nouns that change between a person and a company."""
    if kind_is_company:
        return {"noun": "company", "date": "incorporation date", "year": "incorporation year",
                "listed": "listed company", "born": "incorporated"}
    return {"noun": "person", "date": "date of birth", "year": "birth year",
            "listed": "listed person", "born": "born"}


def _usable_names(customer, rules, company):
    """How many real parts the customer's best name has."""
    names = ([customer.verified_name] if customer.verified_name else []) + [n for n, _s in customer.names]
    best = 0
    for name in names:
        try:
            best = max(best, len(rules.parts(name, company)))
        except Exception:
            continue
    return best


class Briefing(object):
    def annotate(self, case):
        try:
            return self._brief(case)
        except Exception:
            return _empty()

    # -- the briefing ------------------------------------------------------------
    def _brief(self, case):
        customer, hit, outcome = case.customer, case.hit, case.outcome
        states = case.states or {}
        st = {"name": states.get("name", "unknown"), "dob": states.get("dob", "unknown"),
              "location": states.get("location", "unknown")}
        company = customer.kind == COMPANY
        w = _words(company)
        codes = list(getattr(outcome, "codes", None) or [])
        decision = getattr(outcome, "decision", None)
        notes = case.notes or {}
        raw_dob = D.compare(customer.dob, hit.dobs)

        return {
            "headline": self._headline(decision, codes, st, customer, hit, w, raw_dob),
            "decided_by": self._decided_by(decision, outcome),
            "missing": self._missing(customer, hit, st, case.rules, company, w),
            "would_settle": self._would_settle(decision, codes, st, customer, hit, case.rules, company, w, raw_dob),
            "strength": self._strength(decision, codes, st, customer, company),
            "caveats": self._caveats(decision, codes, st, customer, hit, notes, w),
        }

    def _headline(self, decision, codes, st, customer, hit, w, raw_dob):
        noun, code = w["noun"], (codes[0] if codes else None)
        if decision == DIFFERENT:
            if code == "ENTITY_TYPE_MISMATCH":
                return "Different: one is a person and the other a company."
            if code == "DECEASED":
                if noun == "company":
                    return "Different company: the listing gives an end date before this customer was screened."
                return "Different person: the listed person died before this customer was screened."
            if code == "TEMPORAL_IMPOSSIBILITY":
                if noun == "company":
                    return "Different company: incorporated after the earliest report."
                if customer.dob and hit.earliest_report and customer.dob.year > hit.earliest_report.year:
                    return "Different person: born after the earliest report was published."
                return "Different person: too young when the earliest report was published."
            if code == "DOB_MISMATCH" and customer.dob and hit.dobs:
                gap = _gap(customer.dob, hit.dobs)
                if gap == 0:
                    return "Different %s: %s in the same year but on a different date." % (noun, w["born"])
                return "Different %s: %s %d year%s apart." % (noun, w["born"], gap, "" if gap == 1 else "s")
            if code == "LOCATION_MISMATCH":
                return "Different %s by policy: no country in common." % noun
            if code == "NAME_MISMATCH_VERIFIED":
                return "Different %s: the verified legal name is not the listed name." % noun
            return "Different %s: the records contradict the listing." % noun
        if decision == SAME:
            if code == "NAME_LOCATION_MATCH" or noun == "company":
                return "Same company: name and country agree."
            if st["location"] == "agree":
                return "Same person: name and date of birth agree, and so does the country."
            return "Same person: name and date of birth agree."
        if decision == REVIEW:
            if code == "AMBIGUOUS_CUSTOMER_RECORD":
                return "Needs a person: more than one customer fits the alert."
            if not customer.confirmable or not customer.record_ids:
                return "Needs a person: no customer record fits the alert."
            if noun == "company":
                if st["name"] == "agree" and st["dob"] == "agree" and st["location"] == "mismatch":
                    return "Needs a person: name and incorporation date agree, but no country is shared."
                if st["name"] == "agree":
                    return "Needs a person: the name agrees, but no country ties the company to the listing."
                if st["location"] == "agree":
                    return "Needs a person: the country agrees, but the name cannot be confirmed."
                return "Needs a person: the name cannot be confirmed against the listing."
            if st["name"] == "agree" and st["dob"] == "agree":
                return "Needs a person: name and date of birth agree, but no country is shared."
            if st["name"] == "agree":
                lead = "name and country agree" if st["location"] == "agree" else "the name agrees"
                if not customer.dob or not hit.dobs:
                    return "Needs a person: %s, but there is no date of birth to compare." % lead
                if raw_dob == "mismatch":
                    return "Needs a person: %s, but the customer's date of birth could not be verified." % lead
                return "Needs a person: %s, but the birth years are one year apart." % lead
            if st["dob"] == "agree":
                return "Needs a person: the date of birth agrees, but the name cannot be confirmed."
            return "Needs a person: the name cannot be confirmed against the listing."
        return "Needs a person: the evidence does not settle it."

    def _decided_by(self, decision, outcome):
        out = []
        for sentence in list(getattr(outcome, "sentences", None) or []):
            sentence = str(sentence).strip()
            if not sentence:
                continue
            if decision == REVIEW:
                if sentence.startswith(_CLOSING):
                    continue
                if _POLICY_TAIL in sentence:  # keep the countries, drop the policy wording
                    sentence = sentence.split(_POLICY_TAIL)[0] + "."
            if sentence not in out:
                out.append(sentence)
        return out

    def _missing(self, customer, hit, st, rules, company, w):
        out = []
        has_record = bool(customer.record_ids)
        hit_company = (hit.kind == COMPANY) if hit.kind else company
        hw = _words(hit_company)
        if not has_record:
            out.append("No customer record was found, so only the screened details were compared.")
        elif customer.verified_source is None:
            if company:
                out.append("There is no approved registry check, so the legal name and incorporation date are unverified.")
            else:
                out.append("There is no approved identity check, so the legal name and date of birth are unverified.")
        if customer.dob is None:
            if has_record:
                out.append("The customer has no %s on any record." % w["date"])
            else:
                out.append("No %s was screened for the customer." % w["date"])
        if not hit.dobs:
            if hit_company:
                out.append("The hit gives no incorporation date.")
            else:
                out.append("The hit gives no date of birth in its field, its profile notes or search results about it.")
        elif (customer.dob is not None and customer.dob.month and st["dob"] != "mismatch"
              and all(d.month is None for d in hit.dobs)):
            plural = "s" if len(hit.dobs) > 1 else ""
            article = "" if plural else ("an " if hit_company else "a ")
            out.append("The hit gives %s%s%s only, so the day and month could not be compared."
                       % (article, hw["year"], plural))
        if not hit.countries:
            out.append("No country is tied to the hit.")
        if not customer.countries:
            out.append("No country is tied to the customer.")
        for raw in customer.unknown_countries:
            sentence = "The customer country \"%s\" could not be read." % str(raw).strip()
            if sentence not in out:
                out.append(sentence)
        for raw in hit.unknown_countries:
            sentence = "The hit location \"%s\" could not be read." % str(raw).strip()
            if sentence not in out:
                out.append(sentence)
        if not company and _usable_names(customer, rules, company) < 2:
            out.append("The customer's name has fewer than two real parts, so it can neither confirm nor clear the hit.")
        if has_record and not (customer.dob_can_clear and customer.name_can_clear):
            out.append("An identity check on file could not be read with confidence, so what it says can "
                       "support a match but cannot clear one.")
        return out

    def _would_settle(self, decision, codes, st, customer, hit, rules, company, w, raw_dob):
        if decision != REVIEW:
            return []
        if not customer.confirmable or not customer.record_ids:
            return ["Identifying the customer in the system of record would settle it: screened details "
                    "alone can neither clear nor confirm a hit."]
        out = []
        date, listed = w["date"], w["listed"]

        # the name
        if st["name"] != "agree":
            if not company and _usable_names(customer, rules, company) < 2:
                out.append("A verified legal name with at least two parts would settle the name: it would "
                           "either agree with the hit's name or clear the hit.")
            else:
                out.append("A verified legal name would settle the name: one that agrees with none of the "
                           "hit's names would clear the hit, and one that agrees would support the match.")

        # the date
        if st["name"] == "agree" and st["dob"] == "agree" and st["location"] == "mismatch":
            out.append("Evidence that ties the customer to %s would confirm the match; a country difference "
                       "alone cannot clear a hit whose name and %s agree."
                       % (_countries(hit.countries, "or"), date))
        elif not company and st["dob"] != "agree":
            if customer.dob and not hit.dobs:
                year = customer.dob.year
                out.append("A %s for the %s would settle it: %d, with nothing else against it, would confirm "
                           "the match, and %d or earlier, or %d or later, would clear the hit."
                           % (date, listed, year, year - 2, year + 2))
            elif hit.dobs and not customer.dob:
                years = _years(hit.dobs)
                detail = ", matching the day and month where the hit gives them," if any(d.month for d in hit.dobs) else ","
                out.append("The customer's %s would settle it: %s%s with nothing else against it, would confirm "
                           "the match, and %d or earlier, or %d or later, would clear the hit."
                           % (date, _join(years, "or"), detail, years[0] - 2, years[-1] + 2))
            elif not customer.dob and not hit.dobs:
                out.append("A %s for both the customer and the %s would settle it: neither has one, so the "
                           "two cannot be compared." % (date, listed))
            elif raw_dob == "mismatch":
                out.append("A readable approved identity check would settle it: the customer's %s on file (%s) "
                           "contradicts the hit's (%s), but an unverified date is not allowed to clear a hit."
                           % (date, D.show(customer.dob), _join([D.show(d) for d in hit.dobs], "or")))
            else:
                year = customer.dob.year
                nearest = min(_years(hit.dobs), key=lambda y: (abs(y - year), y))
                out.append("A full %s for the %s would settle it: the birth years are one year apart (%d against "
                           "%d), which neither agrees nor contradicts; the same year would confirm the match and "
                           "a gap of more than one year would clear the hit." % (date, listed, year, nearest))

        # the country, which is what confirms a company
        if company and st["name"] == "agree" and st["location"] != "agree" and not (
                st["dob"] == "agree" and st["location"] == "mismatch"):
            if not hit.countries:
                if customer.countries:
                    out.append("A country for the listed company would settle it: %s would confirm the match "
                               "and any other country would clear the hit." % _countries(customer.countries, "or"))
                else:
                    out.append("A country for both the customer and the listed company would settle it: "
                               "neither has one, so the two cannot be compared.")
            elif not customer.countries:
                out.append("A country for the customer would settle it: %s would confirm the match and any "
                           "other country would clear the hit." % _countries(hit.countries, "or"))
            else:
                unread = [str(u).strip() for u in list(customer.unknown_countries) + list(hit.unknown_countries)]
                mentioned = sorted(set(getattr(customer, "possible_countries", None) or {}) & set(hit.countries))
                if mentioned and not unread:
                    out.append("Finding out whether the customer is tied to %s would settle it: a note about them "
                               "mentions it, and a shared country would confirm the match."
                               % _countries(mentioned, "or"))
                else:
                    out.append("Reading the country written as %s would settle it: a country shared with the "
                               "other side would confirm the match." % _join(["\"%s\"" % u for u in unread] or ["unknown"], "and"))

        if not out:
            out.append("A person needs to compare the records: the facts available neither contradict nor "
                       "confirm the hit.")
        return out

    def _strength(self, decision, codes, st, customer, company):
        if decision == DIFFERENT:
            if len(codes) >= 2:
                return "%s independent grounds" % _NUMBER_WORDS.get(len(codes), str(len(codes)))
            code = codes[0] if codes else None
            if code == "DOB_MISMATCH":
                source = str(customer.dob_source or "")
                if source.startswith("KYC-") or source.startswith("NOTE-"):
                    return "one ground, from a verified identity check"
                return "one ground, from a declared date of birth"
            return _ONE_GROUND.get(code, "one ground")
        if decision == SAME:
            if company:
                return "name and country agree"
            if st["location"] == "agree":
                return "name, date of birth and country agree"
            return "name and date of birth agree; no shared country is known"
        return "open"

    def _caveats(self, decision, codes, st, customer, hit, notes, w):
        out = []
        if decision == DIFFERENT and codes == ["LOCATION_MISMATCH"] and st["name"] == "agree":
            if st["dob"] == "unknown":
                out.append("The name agrees and no %s could be compared, so this clearance rests on country alone."
                           % w["date"])
            else:
                out.append("The name agrees, so this clearance rests on country alone.")
        if decision == DIFFERENT and "DOB_MISMATCH" in codes and customer.dob and hit.dobs:
            gap = _gap(customer.dob, hit.dobs)
            if gap == 0:
                out.append("The years are the same; only the month or day differs.")
            elif gap <= 3:
                out.append("The dates are only %d years apart, close to the one-year tolerance." % gap)
        if hit.dobs and st["dob"] in ("agree", "mismatch"):
            if hit.dob_origin == "search":
                cited = _join(sorted(hit.dob_evidence), "and")
                out.append("The hit's birth years come from a web search result%s, not from the listing itself."
                           % (" (%s)" % cited if cited else ""))
            elif hit.dob_origin == "notes":
                if any(d.month for d in hit.dobs):
                    out.append("The hit's date of birth comes from a sentence in its profile notes, not from its "
                               "date-of-birth field.")
                else:
                    out.append("The hit's birth years are worked out from an age given in its profile notes.")
        score = notes.get("score")
        if isinstance(score, dict) and score.get("conflict"):
            bits = score.get("bits")
            shown = " (%+.1f bits)" % bits if isinstance(bits, (int, float)) and not isinstance(bits, bool) else ""
            out.append("The strength-of-evidence score leans the other way%s: towards the same %s." % (shown, w["noun"]))
        review = notes.get("reviewer")
        if isinstance(review, dict) and review.get("verdict") in ("disagree", "unsure"):
            verb = "disagreed with the rules" if review["verdict"] == "disagree" else "was unsure"
            reason = str(review.get("reason") or "").strip()
            out.append(_sentence("The model reviewer %s%s" % (verb, ", saying: " + reason if reason else "")))
        if len(customer.record_ids) > 1:
            out.append("The customer is %d records treated as one %s: %s."
                       % (len(customer.record_ids), w["noun"], _join(customer.record_ids, "and")))
        return out
