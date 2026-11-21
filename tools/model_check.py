"""Ask a model the same question several times and see whether it answers the same way.

    python tools/model_check.py <model id> [--runs 5]

Needs OPENROUTER_API_KEY in the environment (the model id "fake" needs nothing and
uses the built-in stand-in). The question is one invented identity note, the same one
the reader layer would send. Exit code: 0 when every answer was identical, 1 when
they differed or one was missing, 2 when there is no key.
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "system"))

from screening import dates  # noqa: E402
from screening.layers import reader  # noqa: E402
from screening.layers.model import FAKE, Client  # noqa: E402

# Invented. No real person, provider report or document.
NOTE = ("Following the review on 2024-03-16, the onboarding team accepted the passport presented by "
        "Lars Peter Holm (13 December 1977). The document was issued in Germany.")
WRITTEN = "2024-03-16"


def main(argv):
    parser = argparse.ArgumentParser(description="Check that a model gives the same answer every time.")
    parser.add_argument("model", help="an OpenRouter model id, or 'fake'")
    parser.add_argument("--runs", type=int, default=5)
    args = parser.parse_args(argv[1:])

    if args.model.lower() != FAKE and not os.environ.get("OPENROUTER_API_KEY", "").strip():
        print("OPENROUTER_API_KEY is not set. Set it in this shell and run again.")
        return 2

    client = Client(model=args.model, runs=1, max_workers=1)
    user = reader.question(NOTE, WRITTEN)
    print("model: %s" % client.model)
    print("note:  %s" % NOTE)
    answers = []
    for run in range(max(1, args.runs)):
        started = time.time()
        answer = client.ask(reader.SYSTEM, user, run=run)  # a new run index is never answered from memory
        answers.append(answer)
        text = json.dumps(answer, sort_keys=True, ensure_ascii=False) if answer is not None else "NO ANSWER"
        print("run %d  %5.2fs  %s" % (run + 1, time.time() - started, text))

    distinct = set(json.dumps(a, sort_keys=True, ensure_ascii=False) for a in answers)
    identical = len(distinct) == 1 and None not in answers
    if identical:
        facts = reader.verify(answers[0], NOTE, WRITTEN)
        print("checked against the note: name %r, date of birth %r, country %r, outcome %r"
              % (facts["name"], dates.show(facts["dob"]) or None, facts["code"], facts["outcome"]))
        print("a correct reading is:     name 'Lars Peter Holm', date of birth '1977-12-13', country 'DE', outcome 'passed'")
        print("(the built-in stand-in 'fake' gives no date here: it only finds a date that a birth word marks)")
    print("identical: %s (%d distinct answer%s in %d runs)"
          % ("yes" if identical else "NO", len(distinct), "" if len(distinct) == 1 else "s", len(answers)))
    print("client: %s" % json.dumps(client.stats(), sort_keys=True))
    return 0 if identical else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
