"""Local, provenance-preserving jungle matchup snapshots."""
import csv
import math
from datetime import date
from pathlib import Path
from riftmetrics.draft_scoring import norm
from riftmetrics.rank_groups import resolve_ranks, rank_label

FIELDS = ['champion', 'enemy_jungler', 'win_rate_pct', 'sample_size', 'source',
          'patch', 'rank', 'region', 'queue', 'role', 'updated_at',
          'expected_win_rate_pct', 'source_url']


def cohort(row):
    return tuple(str(row.get(k) or 'Unspecified') for k in
                 ('patch', 'rank', 'region', 'queue', 'role'))


def read_records(path):
    path = Path(path)
    if not path.exists():
        return []
    records = []
    with path.open(newline='', encoding='utf-8-sig') as handle:
        for row in csv.DictReader(handle):
            try:
                rate, sample = float(row['win_rate_pct']), int(row['sample_size'])
                if not norm(row['champion']) or not norm(row['enemy_jungler']):
                    continue
                if not math.isfinite(rate) or not 0 <= rate <= 100 or sample < 1:
                    continue
                if row.get('role') and row['role'].upper() != 'JUNGLE':
                    continue
                if row.get('updated_at'):
                    date.fromisoformat(row['updated_at'])
                expected = row.get('expected_win_rate_pct')
                expected = float(expected) if expected else None
                if expected is not None and (not math.isfinite(expected) or not 0 <= expected <= 100):
                    continue
                records.append({**row, 'rate': rate / 100, 'sample': sample,
                                'expected_rate': expected / 100 if expected is not None else None})
            except (ValueError, TypeError, KeyError):
                continue
    return records


def group_rank_records(records, selection):
    """Pool reported observations within a source, never across sites or patches.

    Require every requested rank for that source/cohort. Missing ranks cannot
    silently turn an Iron+Bronze statistic into Iron-only evidence.
    """
    ranks = resolve_ranks(selection)
    if not ranks:
        return []
    if len(ranks) == 1:
        return [r for r in records if (r.get('rank') or '').casefold() == ranks[0].casefold()]
    groups = {}
    for row in sorted(records, key=lambda r: r.get('updated_at') or ''):
        if row.get('rank') not in ranks:
            continue
        key = (norm(row['champion']), norm(row['enemy_jungler']),
               (row.get('source') or 'Manual').casefold(),
               row.get('patch'), row.get('region'), row.get('queue'), row.get('role'))
        groups.setdefault(key, {})[row['rank']] = row
    pooled = []
    for by_rank in groups.values():
        if any(rank not in by_rank for rank in ranks):
            continue
        entries = [by_rank[rank] for rank in ranks]
        total = sum(r['sample'] for r in entries)
        rate = sum(r['rate'] * r['sample'] for r in entries) / total
        expected = (sum(r['expected_rate'] * r['sample'] for r in entries) / total
                    if all(r.get('expected_rate') is not None for r in entries) else None)
        pooled.append(dict(entries[0], rank=rank_label(ranks), rate=rate,
            win_rate_pct=rate * 100, sample=total, sample_size=total,
            expected_rate=expected, rank_details=entries,
            updated_at=min(r.get('updated_at') or '' for r in entries)))
    return pooled


def blend_records(records, context=None):
    groups = {}
    # Latest snapshot replaces an older row from the same source and cohort.
    for row in sorted(records, key=lambda r: r.get('updated_at') or ''):
        key = (norm(row['champion']), norm(row['enemy_jungler']))
        groups.setdefault(key, {})[(cohort(row), (row.get('source') or 'Manual').casefold())] = row
    result = {}
    for key, sources in groups.items():
        candidates = list(sources.values())
        selected_context = context or cohort(max(candidates, key=lambda r: r.get('updated_at') or ''))
        entries = [r for r in candidates if cohort(r) == selected_context]
        if not entries:
            continue
        weights = [min(r['sample'], 1000) for r in entries]
        rate = sum(r['rate'] * w for r, w in zip(entries, weights)) / sum(weights)
        deltas = [(r['rate'] - r['expected_rate'], w) for r, w in zip(entries, weights)
                  if r['expected_rate'] is not None]
        result[key] = dict(rate=rate, sample=max(r['sample'] for r in entries),
                           source=', '.join(r.get('source') or 'Manual' for r in entries),
                           patch=entries[0].get('patch') or '',
                           updated_at=', '.join(sorted({r.get('updated_at') or '' for r in entries})),
                           records=entries, delta=sum(d*w for d, w in deltas) / sum(w for _, w in deltas) if deltas else None,
                           spread=max(r['rate'] for r in entries)-min(r['rate'] for r in entries))
    return result


def save_record(path, record):
    """Upsert one source/cohort snapshot atomically, preserving other matchups."""
    path = Path(path)
    existing = read_records(path)
    key = lambda r: (norm(r['champion']), norm(r['enemy_jungler']),
                     (r.get('source') or '').casefold(), cohort(r))
    rows = [r for r in existing if key(r) != key(record)] + [record]
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    with temp.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, FIELDS, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
    temp.replace(path)
