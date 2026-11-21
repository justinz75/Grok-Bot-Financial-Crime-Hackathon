#!/usr/bin/env python3
"""Aggregate research indicators, not decisions or a runtime policy layer.

See docs/context/policy-gaps.md. Output never includes participant records/IDs.
Python 3.8 standard library; all optional runtime layers explicitly disabled.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'system'))
from screening import dates as D
from screening.pipeline import Run
from screening.resolve import is_approved
from screening.store import TABLES, find_folder, text

MEASURED = ('R01', 'R02', 'R03', 'R04', 'R05', 'R06', 'R07', 'R08',
            'R09', 'R10', 'R11', 'R16')
UNKNOWN = ('R12', 'R13', 'R14', 'R15')
DECISIONS = ('DIFFERENT_ENTITY', 'REVIEW', 'SAME_ENTITY')


def checked_folder(folder):
    """Reject incomplete/invalid input instead of silently undercounting rows."""
    folder = Path(find_folder(str(folder)))
    digest = hashlib.sha256()
    for table in TABLES:
        path = folder / (table + '.jsonl')
        raw = path.read_bytes()
        digest.update(path.name.encode('ascii') + b'\0' + raw + b'\0')
        rows = [json.loads(line) for line in raw.decode('utf-8').splitlines() if line.strip()]
        if not all(isinstance(row, dict) for row in rows):
            raise ValueError('expected objects')
        id_field = {'alerts': 'alert_id', 'hits': 'hit_id', 'customers': 'record_id'}.get(table)
        if id_field:
            ids = [text(row.get(id_field)) for row in rows]
            if any(not value for value in ids) or len(ids) != len(set(ids)):
                raise ValueError('missing or duplicate key')
        if table in ('alerts', 'hits', 'customers') and not rows:
            raise ValueError('empty primary table')
    variants = folder / 'name_variants.json'
    if not variants.is_file():
        variants = folder.parent / 'name_variants.json'
    raw = variants.read_bytes()
    if not isinstance(json.loads(raw.decode('utf-8')), dict):
        raise ValueError('invalid name variants')
    digest.update(b'name_variants.json\0' + raw)
    return folder, digest.hexdigest()


def structured_check_flags(checks, screened_at):
    """Proxies only: structured approved checks; notes deliberately not included."""
    approved = [c for c in checks if is_approved(c)]
    dated = [(D.parse_date(c.get('checked_at')), c) for c in approved]
    dated = [(d, c) for d, c in dated if d]
    tie = False
    if dated:
        latest = max((d.year, d.month or 0, d.day or 0) for d, _ in dated)
        peers = [c for d, c in dated if (d.year, d.month or 0, d.day or 0) == latest]
        signatures = {(text(c.get('verified_name')), text(c.get('verified_dob')),
                       text(c.get('document_country'))) for c in peers}
        tie = len(signatures) > 1
    future = bool(screened_at and any(D.surely_before(screened_at, d) for d, _ in dated))
    return tie, future


def count_gaps(folder):
    folder, fingerprint = checked_folder(folder)
    # Explicit off modes prevent inherited environment settings or API keys being used.
    run = Run(str(folder), modes={n: 'off' for n in ('score', 'briefing', 'reviewer', 'reader')})
    counts = {key: Counter({d: 0 for d in DECISIONS}) for key in MEASURED}
    totals = Counter({d: 0 for d in DECISIONS})
    flagged_hits = 0
    for row in run.store.hits:
        alert = run.store.alert.get(text(row.get('alert_id')))
        if alert is None:
            raise ValueError('hit has no primary alert')
        if text(row.get('hit_id')) not in (alert.get('hit_ids') or []):
            raise ValueError('hit is absent from alert')
        _, pictures, people_count = run.customers_of(alert)
        hit = run._hit(row)
        decision = run.decide_hit(row)['decision']
        totals[decision] += 1
        records = sorted({rid for c in pictures for rid in c.record_ids})
        checks = [ch for rid in records for ch in run.store.checks(rid)]
        _, future = structured_check_flags(checks, pictures[0].screened_at)
        # Test ties within each candidate picture, never between unrelated people.
        tie = any(structured_check_flags(
            [ch for rid in c.record_ids for ch in run.store.checks(rid)], c.screened_at)[0]
                  for c in pictures)
        disagreement = any(len({D.show(D.parse_date(run.store.customer[rid].get('dob')))
                               for rid in c.record_ids
                               if D.parse_date(run.store.customer[rid].get('dob'))}) > 1
                           for c in pictures)
        raw_dobs = row.get('dobs') or []
        if not isinstance(raw_dobs, list):
            raw_dobs = [raw_dobs]
        flags = {
            'R01': tie,
            'R02': future,
            'R03': disagreement,
            'R04': any(text(v) and D.parse_date(v) is None for v in raw_dobs),
            'R05': bool(hit.unknown_countries or any(c.unknown_countries for c in pictures)),
            'R06': people_count == 0,
            'R07': people_count > 1,
            'R08': hit.dob_origin in ('notes', 'search'),
            'R09': not hit.dobs,
            'R10': hit.death is not None,
            'R11': hit.earliest_report is not None,
            'R16': bool(row.get('identifiers')),
        }
        flagged_hits += bool(any(flags.values()))
        for key, present in flags.items():
            if present:
                counts[key][decision] += 1
    runtime = hashlib.sha256()
    for path in sorted((ROOT / 'system' / 'screening').rglob('*.py')):
        runtime.update(str(path.relative_to(ROOT)).encode('utf-8') + b'\0' + path.read_bytes())
    return {
        'schema': 'reconstructed-policy-gaps-v1',
        'data_sha256': fingerprint,
        'runtime_sha256': runtime.hexdigest(),
        'tool_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'unit': 'hits; each flag at most once per hit; flags overlap',
        'alerts': len(run.store.alerts), 'hits': len(run.store.hits),
        'baseline_decisions': dict(totals), 'hits_with_measured_indicator': flagged_hits,
        'gaps': {key: {'status': 'proxy', 'hits': sum(counts[key].values()),
                       'by_decision': dict(counts[key])} for key in MEASURED},
        'unknown': {key: {'status': 'not_measurable', 'hits': None} for key in UNKNOWN},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', help='read-only DATA or ROOM; emits aggregate JSON to stdout')
    args = parser.parse_args()
    try:
        report = count_gaps(args.folder)
    except Exception as error:
        # Do not leak a failing row, identifier or path through exception messages.
        print('gap_counts: input/analysis failed (%s); no report emitted' % type(error).__name__, file=sys.stderr)
        return 1
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
