"""Build the viewer's built-in sample with the real system, from an invented data folder.

    python tools/make_viewer_sample.py           rewrite viewer/sample/ and the copy inside viewer/index.html
    python tools/make_viewer_sample.py --check   exit 1 if either is out of date

Every name, date and record in the sample is invented here. Nothing comes from the hackathon
data, so the sample can be published and shown in a demo. The folder is built with the same
builder the whole-run tests use, and the two files are whatever `system/run` writes for it with
the default layers on.
"""
import io
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "system"))
sys.path.insert(0, os.path.join(ROOT, "system", "tests"))

from screening import pipeline  # noqa: E402
from test_pipeline import Folder  # noqa: E402

SAMPLE = os.path.join(ROOT, "viewer", "sample")
PAGE = os.path.join(ROOT, "viewer", "index.html")
MODES = {"score": "on", "briefing": "on", "reviewer": "off", "reader": "off"}
VARIANTS = {"groups": [["tom", "thomas"], ["tony", "anthony"]], "company_legal_forms": ["ltd", "gmbh", "sa"]}
BLOCKS = (("sample-scored", "dev.jsonl"), ("sample-explain", "dev.explain.jsonl"))


def invented():
    """One small folder that shows each kind of outcome once or twice."""
    f = Folder()
    account = lambda rid: f.field("accounts", "customer_id", rid, "account_id")  # noqa: E731

    # Other customers, so that a name or a country shared with the hit means something.
    for name, born, country in (
            ("Ingrid Solberg", "1969-09-30", "Norway"), ("Pedro Almeida", "1983-01-17", "Portugal"),
            ("Hana Kimura", "1991-07-08", "Japan"), ("Oskar Nowak", "1972-11-02", "Poland"),
            ("Amara Diallo", "1986-05-25", "Senegal"), ("Jonas Weber", "1979-03-11", "Germany"),
            ("Sofia Marin", "1994-12-01", "Spain"), ("Rahul Mehta", "1965-08-19", "India")):
        f.customer(name, born, country)

    # Two hits on one customer, both cleared: the alert is closed.
    lars = f.customer("Lars Holm", "1977-12-13", "Germany")
    alert = f.alert("Lars Holm", account=account(lars))
    f.hit(alert, "Holm, Lars", ["1951"], ["Germany"], category="Sanctions")
    f.hit(alert, "Lars Holm", [], ["Switzerland"], aliases=["L. Holm"])

    # The identity check exists only as a note. One hit is confirmed and one stays open.
    wei = f.customer("Li Wei", "1975-06-02", "Singapore", verified=None)
    f.note(wei, "The provider verified the passport of LI WEI, born 1975-06-02, issued in Singapore, on 2024-03-01.",
           channel="kyc", created_at="2024-03-01")
    alert = f.alert("Li Wei", email=f.field("customers", "record_id", wei, "email"))
    f.hit(alert, "Wei Li", ["1975"], ["Singapore"], category="Sanctions")
    f.hit(alert, "Li Wei", ["1975"], ["China"], category="Adverse Media")

    # The name and the country agree and the hit gives no date of birth.
    anna = f.customer("Anna Petrova", "1988-04-21", "Bulgaria")
    alert = f.alert("Anna Petrova", login=f.field("accounts", "customer_id", anna, "login_handle"))
    f.hit(alert, "Anna Petrova", [], ["Bulgaria"])

    # No link to an account: two different people fit what was screened, and they disagree.
    f.customer("Chen Ming", "1988-03-14", "China", verified=("CHEN MING", "1988-03-14", "China"))
    f.customer("Chen Ming", "1988-03-14", "China", verified=("CHEN MING", "1958-03-14", "China"))
    alert = f.alert("Chen Ming", dob="1988-03-14", country="China")
    f.hit(alert, "Ming Chen", ["1988"], ["China"])

    # A company: the name and the country agree.
    marisol = f.customer("Marisol SA", "2001-01-01", "Spain", kind="Company")
    alert = f.alert("Marisol SA", account=account(marisol), kind="Company")
    f.hit(alert, "Marisol, Sociedad Anonima", [], ["Spain"], kind="Company", category="Sanctions")

    # The customer was a child when the hit was first reported.
    tom = f.customer("Tom Okafor", "2008-02-02", "Nigeria")
    alert = f.alert("Tom Okafor", account=account(tom))
    f.hit(alert, "Thomas Okafor", [], ["Nigeria"], category="Adverse Media",
          notes="According to news.example; June 9, 2020: He was charged with fraud.\n\n"
                "According to news.example; May 1, 2022: He was convicted.")

    # The verified legal name is not the name on the record.
    marco = f.customer("Marco Bellini", "1981-10-09", "Italy", verified=("GIULIA BELLINI", "1981-10-09", "Italy"))
    alert = f.alert("Marco Bellini", login=f.field("accounts", "customer_id", marco, "login_handle"))
    f.hit(alert, "Bellini, Marco", [], ["Italy"])

    # The listed person died before the customer was screened.
    erik = f.customer("Erik Lund", "1970-05-14", "Sweden")
    alert = f.alert("Erik Lund", account=account(erik))
    f.hit(alert, "Lund, Erik", [], ["Sweden"], deceased="2019-06")

    # Only the name can be compared: the hit gives no date of birth and no country.
    nadia = f.customer("Nadia Rahman", "1990-02-27", "Bangladesh")
    alert = f.alert("Nadia Rahman", account=account(nadia))
    f.hit(alert, "Nadia Rahman", [], [])

    # Nothing on file fits what was screened.
    alert = f.alert("Viktor Hale", dob="1962-07-07", country="Canada")
    f.hit(alert, "Hale, Viktor", ["1962"], ["Canada"], category="Sanctions")

    # A person screened against a company.
    mark = f.customer("Mark Baker", "1980-01-01", "Ireland")
    alert = f.alert("Mark Baker", account=account(mark))
    f.hit(alert, "Baker Mark Ltd", [], ["Ireland"], kind="Company")

    # The hit's age comes from a search result about the same listing.
    tunde = f.customer("Tunde Bakare", "1990-04-04", "Nigeria")
    alert = f.alert("Tunde Bakare", account=account(tunde))
    f.hit(alert, "Bakare, Tunde", [], ["Nigeria"], category="Enforcement")
    f.search("bakare tunde", "Tunde Bakare, 34, a university lecturer in Nigeria, was quoted in May 2024.")
    f.search("bakare tunde", "Tunde Bakare, 61, the subject of enforcement action in Nigeria, was named in May 2024.")
    return f


def read(path):
    with io.open(path, encoding="utf-8") as handle:
        return handle.read()


def build():
    """The scored file and the explain file for the invented folder, as text."""
    data = invented()
    folder = tempfile.mkdtemp(prefix="viewer-sample-")
    try:
        for name, rows in data.tables.items():
            with io.open(os.path.join(folder, name + ".jsonl"), "w", encoding="utf-8", newline="\n") as handle:
                for row in rows:
                    handle.write(json.dumps(row) + "\n")
        with io.open(os.path.join(folder, "name_variants.json"), "w", encoding="utf-8", newline="\n") as handle:
            json.dump(VARIANTS, handle)
        scored, explain = os.path.join(folder, "out.jsonl"), os.path.join(folder, "out.explain.jsonl")
        pipeline.run(folder, scored, explain, MODES)
        return read(scored), read(explain)
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def block(page, name):
    """Where the data block with this id starts and ends inside the page."""
    opening = '<script id="%s" type="application/x-ndjson">' % name
    start = page.index(opening) + len(opening)
    return start, page.index("</script>", start)


def embedded(page, name):
    start, end = block(page, name)
    return page[start:end]


def for_page(text):
    """A file's lines as they sit inside the page: `<` is escaped so no line can end the block."""
    return "\n" + text.replace("<", "\\u003c")


def main(argv):
    check = "--check" in argv[1:]
    texts = dict(zip((name for name, _ in BLOCKS), build()))
    page = read(PAGE)
    stale = []
    for name, filename in BLOCKS:
        path = os.path.join(SAMPLE, filename)
        on_disk = read(path) if os.path.isfile(path) else None
        if on_disk != texts[name]:
            stale.append("viewer/sample/" + filename)
            if not check:
                with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
                    handle.write(texts[name])
        if embedded(page, name) != for_page(texts[name]):
            stale.append("viewer/index.html, block " + name)
            start, end = block(page, name)
            page = page[:start] + for_page(texts[name]) + page[end:]
    if check:
        print("out of date: " + ", ".join(stale) if stale else "the sample is up to date")
        return 1 if stale else 0
    with io.open(PAGE, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(page)
    hits = [json.loads(line) for line in texts["sample-scored"].splitlines() if line.strip()]
    counts = {}
    for hit in hits:
        counts[hit["decision"]] = counts.get(hit["decision"], 0) + 1
    print("%d hits in %d alerts: %s" % (len(hits), len(set(hit["alert_id"] for hit in hits)),
                                         ", ".join("%s %d" % item for item in sorted(counts.items()))))
    print("rewrote: " + ", ".join(stale) if stale else "nothing to rewrite")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
