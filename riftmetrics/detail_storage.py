"""Backfill parsed match details from locally cached Riot match responses.

Run: python -m riftmetrics.detail_storage
This module never contacts Riot and never modifies the existing matches table.
"""
import json
import os

from dotenv import load_dotenv
from riftmetrics.match_parser import parse_match
from riftmetrics.storage import connect


DETAILS_SCHEMA = """
CREATE TABLE IF NOT EXISTS match_details (
    match_id TEXT PRIMARY KEY,
    details_json TEXT NOT NULL,
    FOREIGN KEY (match_id) REFERENCES matches(match_id)
);
"""


def backfill(db, game_name, tag_line, *, puuid=None):
    db.execute(DETAILS_SCHEMA)
    rows = db.execute("""
        SELECT m.match_id, m.raw_json
        FROM matches AS m
        LEFT JOIN match_details AS d ON d.match_id = m.match_id
        WHERE d.match_id IS NULL
        ORDER BY m.played_at
    """).fetchall()
    imported = 0
    failed = []
    for match_id, raw_json in rows:
        try:
            details = parse_match(json.loads(raw_json), puuid=puuid,
                                  game_name=game_name, tag_line=tag_line)
            if details['match_id'] != match_id:
                raise ValueError('Match ID mismatch')
            db.execute(
                'INSERT INTO match_details (match_id, details_json) VALUES (?, ?)',
                (match_id, json.dumps(details, ensure_ascii=False))
            )
            imported += 1
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            failed.append((match_id, str(exc)))
    db.commit()
    return imported, failed


def main():
    load_dotenv()
    name = os.getenv('RIOT_GAME_NAME', 'Destro493')
    tag = os.getenv('RIOT_TAG_LINE', 'NA1')
    with connect() as db:
        imported, failed = backfill(db, name, tag)
        total = db.execute('SELECT COUNT(*) FROM match_details').fetchone()[0]
    print(f'New detailed records: {imported}')
    print(f'Total detailed records: {total}')
    for match_id, reason in failed:
        print(f'Could not parse {match_id}: {reason}')
    if failed:
        raise SystemExit(f'{len(failed)} match(es) need review; existing match data is unchanged.')


if __name__ == '__main__':
    main()
