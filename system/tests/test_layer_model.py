"""Tests for the model layers: the client, the reader and the reviewer.

Nothing here touches the network: the model is always a stand-in. Every name and
sentence is invented; none comes from the hackathon data.
"""
import io
import json
import os
import sys
import threading
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from screening import dates as D  # noqa: E402
from screening import extract as X  # noqa: E402
from screening.decide import PERSON, Customer, Hit, decide, states  # noqa: E402
from screening.layers import Case, model, reader, reviewer  # noqa: E402
from screening.layers.model import Client  # noqa: E402
from screening.names import NameRules  # noqa: E402

RULES = NameRules()
NO_ENV = {"OPENROUTER_API_KEY": "", "SCREENING_MODEL": "", "SCREENING_MODEL_RUNS": ""}


class FakeStore(object):
    rules = RULES


class Scripted(object):
    """A stand-in model: replies from a list, repeats the last one, counts its calls."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = 0
        self.prompts = []
        self._lock = threading.Lock()

    def __call__(self, system_prompt, user_prompt):
        with self._lock:
            reply = self.replies[min(self.calls, len(self.replies) - 1)]
            self.calls += 1
            self.prompts.append((system_prompt, user_prompt))
        if isinstance(reply, Exception):
            raise reply
        return reply


def client(*replies, **options):
    options.setdefault("max_workers", 1)
    options.setdefault("key", "")
    fake = Scripted(*replies)
    return Client(fake=fake, **options), fake


def says(name=None, dob=None, country=None, outcome="passed"):
    return json.dumps({"legal_name": name, "date_of_birth": dob, "document_country": country, "outcome": outcome})


class Clock(object):
    now = 0.0

    def __call__(self):
        return self.now


class ClientTests(unittest.TestCase):
    def test_no_key_and_no_stand_in(self):
        with mock.patch.dict(os.environ, NO_ENV):
            c = Client()
            self.assertFalse(c.available)
            self.assertIsNone(c.ask("system", "user"))
            self.assertEqual(c.consensus("system", "user"), (None, 0.0))
            self.assertEqual(c.stats()["calls"], 0)
            self.assertEqual(c.model, model.DEFAULT_MODEL)

    def test_same_question_is_asked_once(self):
        c, fake = client('{"a": 1}')
        self.assertEqual(c.ask("s", "u"), {"a": 1})
        self.assertEqual(c.ask("s", "u"), {"a": 1})
        self.assertEqual(fake.calls, 1)
        c.ask("s", "u", run=1)        # another run index is another question
        c.ask("s", "something else")
        self.assertEqual(fake.calls, 3)
        self.assertEqual(c.stats()["cache_hits"], 1)

    def test_an_answer_cannot_be_changed_through_the_cache(self):
        c, _ = client('{"a": [1]}')
        c.ask("s", "u")["a"].append(2)
        self.assertEqual(c.ask("s", "u"), {"a": [1]})

    def test_reply_that_is_not_json(self):
        c, _ = client("I cannot help with that.")
        self.assertIsNone(c.ask("s", "u"))
        self.assertEqual(c.stats()["failures"], 1)
        c, _ = client('Sure, here it is:\n```json\n{"a": 1}\n```')
        self.assertEqual(c.ask("s", "u"), {"a": 1})
        c, _ = client("[1, 2, 3]")
        self.assertIsNone(c.ask("s", "u"))

    def test_a_stand_in_that_raises_gives_no_answer(self):
        c, _ = client(RuntimeError("boom"))
        self.assertIsNone(c.ask("s", "u"))

    def test_consensus(self):
        c, fake = client('{"v": 1}', runs=3)
        self.assertEqual(c.consensus("s", "u"), ({"v": 1}, 1.0))
        self.assertEqual(fake.calls, 3)
        c, _ = client('{"v": 1}', '{"v": 2}', '{"v": 1}', runs=3)
        answer, agreement = c.consensus("s", "u")
        self.assertIsNone(answer)
        self.assertAlmostEqual(agreement, 2 / 3.0)
        c, _ = client("nothing", runs=3)
        self.assertEqual(c.consensus("s", "u"), (None, 0.0))
        c, _ = client('{"v": 1}', "nothing", '{"v": 1}', runs=3)   # a missing answer is a disagreement
        self.assertIsNone(c.consensus("s", "u")[0])

    def test_key_order_does_not_break_consensus(self):
        c, _ = client('{"a": 1, "b": 2}', '{"b": 2, "a": 1}', runs=2)
        self.assertEqual(c.consensus("s", "u"), ({"a": 1, "b": 2}, 1.0))

    def test_budget(self):
        clock = Clock()
        c, fake = client('{"a": 1}', budget_seconds=10, clock=clock)
        self.assertEqual(c.ask("s", "first"), {"a": 1})
        clock.now = 11.0
        self.assertIsNone(c.ask("s", "second"))            # out of time: not asked
        self.assertEqual(c.ask("s", "first"), {"a": 1})    # what was already answered is kept
        self.assertEqual(fake.calls, 1)
        self.assertEqual(c.stats()["skipped"], 1)

    def test_ask_all_keeps_order(self):
        c = Client(fake=lambda s, u: json.dumps({"u": u}), key="", max_workers=6)
        items = [("s", "question %d" % i, 0) for i in range(30)]
        self.assertEqual([a["u"] for a in c.ask_all(items)], ["question %d" % i for i in range(30)])

    def test_built_in_stand_in(self):
        with mock.patch.dict(os.environ, dict(NO_ENV, SCREENING_MODEL="fake", SCREENING_MODEL_RUNS="2")):
            c = Client()
            self.assertTrue(c.available)
            self.assertEqual((c.model, c.runs), ("fake", 2))
            self.assertEqual(c.ask(reviewer.SYSTEM, "Facts:\n{}")["verdict"], "agree")


class Reply(object):
    def __init__(self, content):
        self.body = json.dumps({"choices": [{"message": {"content": content}}]}).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self.body


def http_error(code):
    return urllib.error.HTTPError(model.URL, code, "error", {}, io.BytesIO(b""))


class WireTests(unittest.TestCase):
    """The HTTP path, with the network replaced."""

    def ask(self, *results):
        calls = []

        def opened(request, timeout=None):
            calls.append(request)
            result = results[min(len(calls) - 1, len(results) - 1)]
            if isinstance(result, Exception):
                raise result
            return result

        with mock.patch.object(model, "_open", opened), mock.patch.object(model, "_sleep", lambda seconds: None):
            answer = Client(model="vendor/small", key="test-key", fake=None).ask("system text", "user text")
        return answer, calls

    def test_request_shape(self):
        answer, calls = self.ask(Reply('{"a": 1}'))
        self.assertEqual(answer, {"a": 1})
        self.assertEqual(len(calls), 1)
        request = calls[0]
        self.assertEqual(request.full_url, model.URL)
        self.assertEqual(request.get_header("Authorization"), "Bearer test-key")
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual((body["model"], body["temperature"], body["top_p"], body["seed"], body["max_tokens"]),
                         ("vendor/small", 0, 1, 7, 300))
        self.assertEqual(body["response_format"], {"type": "json_object"})
        self.assertEqual([m["role"] for m in body["messages"]], ["system", "user"])

    def test_retries_on_a_server_error(self):
        answer, calls = self.ask(http_error(500), http_error(429), Reply('{"a": 1}'))
        self.assertEqual((answer, len(calls)), ({"a": 1}, 3))

    def test_gives_up_after_three_attempts(self):
        answer, calls = self.ask(urllib.error.URLError("down"))
        self.assertEqual((answer, len(calls)), (None, 3))

    def test_does_not_retry_a_refused_key(self):
        answer, calls = self.ask(http_error(401), Reply('{"a": 1}'))
        self.assertEqual((answer, len(calls)), (None, 1))

    def test_drops_optional_settings_a_model_rejects(self):
        answer, calls = self.ask(http_error(400), Reply('{"a": 1}'))
        self.assertEqual(answer, {"a": 1})
        second = json.loads(calls[1].data.decode("utf-8"))
        self.assertNotIn("response_format", second)
        self.assertNotIn("seed", second)
        self.assertEqual(second["temperature"], 0)

    def test_a_broken_reply_gives_no_answer(self):
        class Broken(Reply):
            def read(self):
                return b"<html>gateway timeout</html>"
        answer, calls = self.ask(Broken(""))
        self.assertEqual((answer, len(calls)), (None, 3))


# Notes the rules cannot read: the legal name is not in capitals and no word marks the birth date.
TITLE_NOTE = "On 2023-02-19 the provider checked the passport of Lars Holm (13 December 1977), issued in Germany."
WRITTEN = "2023-02-19"


class ReaderTests(unittest.TestCase):
    def build(self, mode, *replies, **options):
        c, fake = client(*replies, **options)
        return reader.build(FakeStore(), mode, client=c), fake

    def test_the_rules_win_when_they_can_read_the_note(self):
        note = "Sumsub completed identity verification for LARS HOLM, born December 13, 1977, using a national ID issued in Germany on 2023-02-19."
        read, fake = self.build("enforce", says("Somebody Else", "1 January 1950", "France"))
        self.assertEqual(read(note, WRITTEN, True), X.read_identity_note(note, WRITTEN, True))
        self.assertEqual(fake.calls, 0)
        self.assertNotIn("soft", read(note, WRITTEN, True))

    def test_the_rules_cannot_read_the_test_note(self):
        self.assertIsNone(X.read_identity_note(TITLE_NOTE, WRITTEN, True))

    def test_reads_a_name_that_is_not_in_capitals(self):
        read, fake = self.build("on", says("Lars Holm", "13 December 1977", "Germany"))
        got = read(TITLE_NOTE, WRITTEN, True)
        self.assertEqual(got["name"], "Lars Holm")
        self.assertEqual(got["dob"], D.parse_date("1977-12-13"))
        self.assertEqual((got["country"], got["countries"]), ("DE", ["DE"]))
        self.assertEqual((got["approved"], got["soft"], got["read_by"]), (True, True, "model"))
        self.assertEqual(fake.calls, 1)
        self.assertIn(TITLE_NOTE, fake.prompts[0][1])
        read, _ = self.build("enforce", says("Lars Holm", "13 December 1977", "Germany"))
        self.assertFalse(read(TITLE_NOTE, WRITTEN, True)["soft"])

    def test_a_name_that_is_not_in_the_note_is_dropped(self):
        read, _ = self.build("on", says("Peter Schmidt", "13 December 1977", "Germany"))
        got = read(TITLE_NOTE, WRITTEN, True)       # inside the check channel the date still stands
        self.assertIsNone(got["name"])
        self.assertEqual(got["dob"], D.parse_date("1977-12-13"))
        self.assertTrue(got["soft"])
        read, _ = self.build("on", says("Peter Schmidt", "13 December 1977", "Germany"))
        self.assertIsNone(read(TITLE_NOTE, WRITTEN, False))   # outside it a date with no name is not believed
        read, _ = self.build("enforce", says("Peter Schmidt", "13 December 1977", "Germany"))
        self.assertIsNone(read(TITLE_NOTE, WRITTEN, True))    # and nothing counts in full without a name

    def test_a_country_or_a_document_date_is_not_a_fact_about_the_person(self):
        note = ("On 2023-02-19 the provider checked the passport of Lars Holm (13 December 1977), "
                "issued in the United States on 2019-05-01.")
        facts = reader.verify(json.loads(says("United States", "2019-05-01", "United States")), note, WRITTEN)
        self.assertEqual((facts["name"], facts["dob"], facts["code"]), (None, None, "US"))
        facts = reader.verify(json.loads(says("Lars Holm", "13 December 1977", "United States")), note, WRITTEN)
        self.assertEqual((facts["name"], facts["dob"]), ("Lars Holm", D.parse_date("1977-12-13")))

    def test_the_bank_must_already_know_the_name(self):
        class Filed(FakeStore):
            notes = [{"text": TITLE_NOTE, "requester_email": "Holm.Family@mail.example"}]

            def __init__(self, held):
                self.customers_by_email = {"holm.family@mail.example": [{"full_name": held, "preferred_name": None}]}

        reply = says("Lars Holm", "13 December 1977", "Germany")
        for held, known in (("Lars Holm", True), ("Ingrid Holm", True), ("HOLM lars", True),
                            ("Peter Schmidt", False), ("", False)):
            c, _ = client(reply)
            got = reader.build(Filed(held), "enforce", client=c)(TITLE_NOTE, WRITTEN, True)
            self.assertEqual(got is not None, known, held)
        c, _ = client(reply)       # a note that is on nobody's file supports nothing
        other = TITLE_NOTE.replace("Lars Holm", "Lars  Holm")
        self.assertIsNone(reader.build(Filed("Lars Holm"), "enforce", client=c)(other, WRITTEN, True))

    def test_a_date_that_is_not_in_the_note_is_dropped(self):
        facts = reader.verify(json.loads(says("Lars Holm", "1 January 1980", "Germany")), TITLE_NOTE, WRITTEN)
        self.assertEqual((facts["name"], facts["dob"], facts["code"]), ("Lars Holm", None, "DE"))

    def test_the_day_of_the_check_is_not_a_birth_date(self):
        facts = reader.verify(json.loads(says("Lars Holm", "2023-02-19", "Germany")), TITLE_NOTE, WRITTEN)
        self.assertIsNone(facts["dob"])

    def test_a_check_read_without_its_birth_date_stays_unread(self):
        # Calling it read would let the customer's declared date of birth clear a hit.
        for mode in ("on", "enforce"):
            for reply in (says("Lars Holm", None, "Germany"), says("Lars Holm", "1 January 1980", "Germany"),
                          says("Lars Holm", "2023-02-19", "Germany")):
                read, fake = self.build(mode, reply)
                self.assertIsNone(read(TITLE_NOTE, WRITTEN, True), (mode, reply))
                self.assertEqual(fake.calls, 1)

    def test_a_country_that_is_not_in_the_note_is_dropped(self):
        read, _ = self.build("on", says("Lars Holm", "13 December 1977", "France"))
        self.assertEqual(read(TITLE_NOTE, WRITTEN, True)["countries"], ["DE"])   # Germany is what the note says

    def test_cautious_mode_keeps_a_country_inside_the_name(self):
        note = "On 2023-02-19 the provider checked the passport of Jordan Holm (13 December 1977), issued in Germany."
        read, _ = self.build("on", says("Jordan Holm", "13 December 1977", "Germany"))
        self.assertEqual(sorted(read(note, WRITTEN, True)["countries"]), ["DE", "JO"])   # more countries never clears
        read, _ = self.build("enforce", says("Jordan Holm", "13 December 1977", "Germany"))
        self.assertEqual(read(note, WRITTEN, True)["countries"], ["DE"])

    def test_a_role_word_is_not_a_name(self):
        note = "On 2023-02-19 Veriff checked the passport of the customer (13 December 1977), issued in Germany."
        for nobody in ("the customer", "Veriff", "Germany", "passport"):
            facts = reader.verify(json.loads(says(nobody, "13 December 1977", "Germany")), note, WRITTEN)
            self.assertIsNone(facts["name"], nobody)
        read, _ = self.build("on", says("the customer", "13 December 1977", "Germany"))
        self.assertIsNone(read(note, WRITTEN, False))
        self.assertIsNone(reader.verify({"legal_name": "Lars Holm 2"}, "the passport of Lars Holm 2 was checked", None)["name"])

    def test_cautious_mode_never_sets_a_check_aside(self):
        read, _ = self.build("on", says("Lars Holm", "13 December 1977", "Germany", "failed"))
        self.assertIsNone(read(TITLE_NOTE, WRITTEN, True))    # treated as unreadable, the rules' cautious path
        read, _ = self.build("enforce", says("Lars Holm", "13 December 1977", "Germany", "failed"))
        got = read(TITLE_NOTE, WRITTEN, True)
        self.assertEqual((got["name"], got["approved"]), ("Lars Holm", False))

    def test_a_date_the_rules_read_keeps_its_weight(self):
        note = "On 2023-02-19 the provider checked the passport of Lars Holm, born 13 December 1977, issued in Germany."
        by_rules = X.read_identity_note(note, WRITTEN, True)
        self.assertEqual((by_rules["name"], by_rules["dob"]), (None, D.parse_date("1977-12-13")))
        read, fake = self.build("on", says("Lars Holm", "13 December 1977", "Germany"))
        self.assertEqual(read(note, WRITTEN, True), by_rules)     # cautious mode: left exactly as the rules had it
        self.assertEqual(fake.calls, 0)
        read, fake = self.build("enforce", says("Lars Holm", None, None))
        got = read(note, WRITTEN, True)                            # trusting mode: the model adds the name
        self.assertEqual((got["name"], got["dob"], got["soft"]), ("Lars Holm", D.parse_date("1977-12-13"), False))

    def test_ordinary_notes_never_reach_the_model(self):
        read, fake = self.build("enforce", says("Lars Holm", "13 December 1977", "Germany"))
        for note in [
            "Customer asked about savings interest rates and was sent the current tariff.",
            "Documentation shows the individual resided and held employment within Norway between 2008 and 2011.",
            "Records verify that the client lived and worked in Spain for the years 2010 to 2013.",
            "",
        ]:
            self.assertIsNone(read(note, WRITTEN, False), note)
        self.assertEqual(fake.calls, 0)

    def test_runs_that_disagree_teach_nothing(self):
        read, fake = self.build("on", says("Lars Holm", "13 December 1977", "Germany"),
                                says("Lars", "13 December 1977", "Germany"), runs=2)
        self.assertIsNone(read(TITLE_NOTE, WRITTEN, True))
        self.assertEqual(fake.calls, 2)

    def test_no_answer_and_no_model_fall_back_to_the_rules(self):
        read, _ = self.build("on", "I am unable to help.")
        self.assertIsNone(read(TITLE_NOTE, WRITTEN, True))
        read, _ = self.build("on", RuntimeError("down"))
        self.assertIsNone(read(TITLE_NOTE, WRITTEN, True))
        read, _ = self.build("on", '{"legal_name": ["Lars", "Holm"], "date_of_birth": 1977}')
        self.assertIsNone(read(TITLE_NOTE, WRITTEN, True))
        with mock.patch.dict(os.environ, NO_ENV):
            read = reader.build(FakeStore(), "on")
            self.assertFalse(read.client.available)
            self.assertIsNone(read(TITLE_NOTE, WRITTEN, True))

    def test_warm_asks_ahead(self):
        read, fake = self.build("on", says("Lars Holm", "13 December 1977", "Germany"))
        other = "Customer reported a lost card. Card frozen and a replacement ordered to the address on file."
        self.assertEqual(read.warm([(TITLE_NOTE, WRITTEN, True), (other, WRITTEN, False)]), 1)
        self.assertEqual(fake.calls, 1)
        self.assertEqual(read(TITLE_NOTE, WRITTEN, True)["name"], "Lars Holm")
        self.assertEqual(fake.calls, 1)

    def test_built_in_stand_in_reads_a_note(self):
        note = "On 2023-02-19 Veriff accepted the passport of Lars Holm, issued in Germany; date of birth 13 December 1977."
        read = reader.build(FakeStore(), "enforce", client=Client(model="fake", key=""))
        got = read(note, WRITTEN, True)
        self.assertEqual((got["name"], got["dob"], got["countries"]), ("Lars Holm", D.parse_date("1977-12-13"), ["DE"]))
        reply = json.loads(model.builtin_fake(reader.SYSTEM, reader.question(
            "On 2023-02-19 Onfido accepted a United States passport for lars holm; date of birth 13 December 1977.")))
        self.assertEqual((reply["legal_name"], reply["date_of_birth"], reply["document_country"]),
                         (None, "13 December 1977", "United States"))   # a country is never offered as the name


def person(name, dob, countries):
    return Customer(PERSON, ["CUS-000001"], verified_name=name.upper(), verified_source="KYC-0000A1",
                    names=[(name, "CUS-000001")], dob=D.parse_date(dob), dob_source="KYC-0000A1",
                    countries=dict((code, ["CUS-000001"]) for code in countries), screened_at=D.parse_date("2026-11-06"))


def listed(name, dobs, countries):
    return Hit("H-0000A1", PERSON, name, dobs=D.parse_dates(dobs), dob_origin="listed" if dobs else None,
               countries=countries)


def case_of(customer, hit):
    outcome = decide(customer, hit, RULES)
    return Case(FakeStore(), {}, {}, customer, hit, outcome, states(customer, hit, RULES), {})


CLEARED = case_of(person("Lars Holm", "1977-12-13", ["DE"]), listed("Holm, Lars", "1951", ["DE"]))
MATCHED = case_of(person("Li Wei", "1975-06-02", ["SG"]), listed("Wei Li", "1975", ["SG"]))
OPEN = case_of(person("Anna Petrova", "1969-01-01", ["RU"]), listed("Anna Petrova", "", ["RU"]))


def verdict(word, reason="The birth years are 26 years apart."):
    return json.dumps({"verdict": word, "reason": reason})


class ReviewerTests(unittest.TestCase):
    def build(self, mode, *replies, **options):
        c, fake = client(*replies, **options)
        return reviewer.build(FakeStore(), mode, client=c), fake

    def test_the_cases_are_what_they_say(self):
        self.assertEqual((CLEARED.outcome.decision, MATCHED.outcome.decision, OPEN.outcome.decision),
                         ("DIFFERENT_ENTITY", "SAME_ENTITY", "REVIEW"))

    def test_only_clearances_are_reviewed(self):
        layer, fake = self.build("on", verdict("agree"))
        self.assertIsNone(layer.annotate(MATCHED))
        self.assertIsNone(layer.annotate(OPEN))
        self.assertEqual(fake.calls, 0)

    def test_a_clearance_gets_an_opinion(self):
        layer, fake = self.build("on", verdict("agree"))
        note = layer.annotate(CLEARED)
        self.assertEqual(note, {"verdict": "agree", "reason": "The birth years are 26 years apart.",
                                "model": layer.client.model, "runs": 1, "agreement": 1.0})
        self.assertEqual(fake.calls, 1)
        self.assertIsNone(layer.guard(CLEARED, note))

    def test_the_model_sees_the_facts_and_the_stated_reason(self):
        pack = json.loads(reviewer.evidence_pack(CLEARED))
        self.assertEqual(pack["customer"]["verified_legal_name"], "LARS HOLM")
        self.assertEqual(pack["customer"]["date_of_birth"], "1977-12-13")
        self.assertEqual(pack["customer"]["countries"], ["Germany"])
        self.assertEqual(pack["watchlist_entry"]["dates_of_birth"], ["1951"])
        self.assertEqual(pack["first_reviewer"]["grounds"], ["DOB_MISMATCH"])
        self.assertEqual(reviewer.evidence_pack(CLEARED), reviewer.evidence_pack(CLEARED))
        layer, fake = self.build("on", verdict("agree"))
        layer.annotate(CLEARED)
        self.assertIn(reviewer.evidence_pack(CLEARED), fake.prompts[0][1])
        self.assertIn("worst mistake", fake.prompts[0][0])

    def test_guard_needs_every_run_to_disagree(self):
        layer, _ = self.build("enforce", verdict("disagree", "The dates could be the same person."), runs=3)
        note = layer.annotate(CLEARED)
        self.assertEqual((note["verdict"], note["runs"], note["agreement"]), ("disagree", 3, 1.0))
        why = layer.guard(CLEARED, note)
        self.assertIn("disagreed", why)
        self.assertIn("The dates could be the same person", why)

        layer, _ = self.build("enforce", verdict("disagree"), verdict("agree"), verdict("disagree"), runs=3)
        note = layer.annotate(CLEARED)
        self.assertEqual((note["verdict"], note["agreement"]), ("disagree", 0.67))
        self.assertIsNone(layer.guard(CLEARED, note))

        layer, _ = self.build("enforce", verdict("unsure"), runs=3)
        self.assertIsNone(layer.guard(CLEARED, layer.annotate(CLEARED)))
        self.assertIsNone(layer.guard(CLEARED, None))

    def test_a_tie_goes_to_the_cautious_verdict(self):
        layer, _ = self.build("on", verdict("agree"), verdict("disagree"), runs=2)
        note = layer.annotate(CLEARED)
        self.assertEqual((note["verdict"], note["agreement"]), ("disagree", 0.5))
        self.assertIsNone(layer.guard(CLEARED, note))

    def test_an_unusable_answer_says_nothing(self):
        for reply in ('{"verdict": "maybe"}', "no idea", '{"verdict": 1}', RuntimeError("down")):
            layer, _ = self.build("on", reply)
            self.assertIsNone(layer.annotate(CLEARED))

    def test_no_model_says_nothing(self):
        with mock.patch.dict(os.environ, NO_ENV):
            layer = reviewer.build(FakeStore(), "on")
            self.assertIsNone(layer.annotate(CLEARED))

    def test_warm_asks_ahead(self):
        layer, fake = self.build("on", verdict("agree"), runs=2)
        self.assertEqual(layer.warm([CLEARED, MATCHED, OPEN]), 2)
        self.assertEqual(fake.calls, 2)
        self.assertEqual(layer.annotate(CLEARED)["runs"], 2)
        self.assertEqual(fake.calls, 2)


if __name__ == "__main__":
    unittest.main()
