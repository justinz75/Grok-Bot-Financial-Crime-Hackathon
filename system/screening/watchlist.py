"""Working out who the listed person is (POLICY.md principle 5).

A hit's facts are gathered wherever they are: its fields first, then the opening
paragraph of its profile notes, then the web search results that are about this hit and
not a namesake.
"""
from . import countries as C
from . import dates as D
from . import extract as X
from .decide import COMPANY, Hit
from .resolve import kind_of
from .store import text

PLACE_FIELDS = ("countries", "nationality", "citizenship", "addresses", "place_of_birth")


def hit_countries(row):
    """Countries tied to a hit: its countries, nationality, citizenship, addresses
    (the last part of each) and place of birth."""
    codes, unknown = set(), []
    for field in PLACE_FIELDS:
        for value in C.split_values(row.get(field)):
            code = C.resolve_place(value)
            if code is None:
                unknown.append(value)
            elif code != C.IGNORED:
                codes.add(code)
    return codes, unknown


def _search_dobs(name, store, phrase, countries):
    """Recover DOBs in key order and retain the original first bucket for clearance."""
    dates, used, seen = {}, [], set()
    first_bucket = None
    for query in X.search_keys(name):
        bucket = store.search_by_query.get(query)
        if bucket is None:
            continue
        results = [(text(row.get("result_id")), text(row.get("snippet"))) for row in bucket]
        if first_bucket is None:
            first_bucket = results
        for result_id, snippet in results:
            identity = (result_id, snippet if not result_id else "")
            if identity in seen:
                continue
            seen.add(identity)
            # Extract one result at a time so different date precisions can coexist.
            found, sources = X.search_birth([(result_id, snippet)], phrase, countries)
            used.extend(sources)
            for date in found:
                dates.setdefault(D.readings(date), date)
    return sorted(dates.values(), key=D.show), used, first_bucket or ()


def build_hit(row, store):
    kind = kind_of(row.get("entity_type"))
    name = text(row.get("name"))
    aliases = C.split_values(row.get("aliases"))
    best = text(row.get("best_matching_name"))
    if best and best != name:
        aliases.append(best)
    countries, unknown = hit_countries(row)
    notes = text(row.get("profile_notes"))
    hit_id = text(row.get("hit_id"))

    dobs, origin, used = D.parse_dates(row.get("dobs")), None, []
    clearance_dobs = None
    if dobs:
        origin = "listed"
    elif kind != COMPANY:  # for companies only the dobs field is an incorporation date
        dobs, _ = X.profile_birth(notes)
        clearance_dobs, _ = X.profile_birth(notes, opening_line_only=True)
        if dobs:
            origin = "notes"
            if not clearance_dobs:  # cite the exact field when the wider reading supplied the date
                used = ["%s#profile_notes" % hit_id]
        if not dobs or not clearance_dobs:
            phrase = X.listing_phrase(row.get("primary_category"), row.get("categories"))
            search_dobs, search_sources, first_bucket = _search_dobs(name, store, phrase, countries)
            if not clearance_dobs:
                clearance_dobs, _ = X.search_birth(first_bucket, phrase, countries)
            if not dobs and search_dobs:
                dobs, used, origin = search_dobs, search_sources, "search"

    reports = X.dated_reports(notes)
    return Hit(hit_id, kind, name, aliases, dobs, origin, used, countries, unknown,
               reports[0] if reports else None, D.parse_date(row.get("deceased_date")), clearance_dobs)
