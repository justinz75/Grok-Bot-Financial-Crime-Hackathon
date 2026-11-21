"""Working out who the listed person is (POLICY.md principle 5).

A hit's facts are gathered wherever they are: its fields first, then the opening
line of its profile notes, then the web search results that are about this hit and
not a namesake.
"""
from . import countries as C
from . import dates as D
from . import extract as X
from .decide import COMPANY, Hit
from .resolve import kind_of
from .store import key, text

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


def build_hit(row, store):
    kind = kind_of(row.get("entity_type"))
    name = text(row.get("name"))
    aliases = C.split_values(row.get("aliases"))
    best = text(row.get("best_matching_name"))
    if best and best != name:
        aliases.append(best)
    countries, unknown = hit_countries(row)
    notes = text(row.get("profile_notes"))

    dobs, origin, used = D.parse_dates(row.get("dobs")), None, []
    if dobs:
        origin = "listed"
    elif kind != COMPANY:  # for companies only the dobs field is an incorporation date
        dobs, how = X.profile_birth(notes)
        if dobs:
            origin = "notes"
        else:
            results = []
            for query in X.search_keys(name):
                if query in store.search_by_query:
                    results = [(text(r.get("result_id")), text(r.get("snippet"))) for r in store.search_by_query[query]]
                    break
            phrase = X.listing_phrase(row.get("primary_category"), row.get("categories"))
            dobs, used = X.search_birth(results, phrase, countries)
            if dobs:
                origin = "search"

    reports = X.dated_reports(notes)
    return Hit(text(row.get("hit_id")), kind, name, aliases, dobs, origin, used, countries, unknown,
               reports[0] if reports else None, D.parse_date(row.get("deceased_date")),
               unread_dobs=D.unread_dates(row.get("dobs")))
