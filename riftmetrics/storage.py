import sqlite3
from pathlib import Path

SCHEMA = '''
CREATE TABLE IF NOT EXISTS matches (
 match_id TEXT PRIMARY KEY, played_at TEXT NOT NULL, queue_id INTEGER,
 champion TEXT NOT NULL, role TEXT, win INTEGER NOT NULL,
 kills INTEGER, deaths INTEGER, assists INTEGER, cs INTEGER, gold INTEGER,
 damage INTEGER, vision INTEGER, duration_seconds INTEGER, raw_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rank_snapshots (
 id INTEGER PRIMARY KEY AUTOINCREMENT, captured_at TEXT NOT NULL,
 queue TEXT, tier TEXT, division TEXT, lp INTEGER, wins INTEGER, losses INTEGER
);
'''

def connect(path='data/riftmetrics.db'):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)

    # Normalize champion names in existing records
    db.execute(
        "UPDATE matches SET champion = ? WHERE champion = ?",
        ("Wukong", "MonkeyKing")
    )
    db.commit()

    return db


def stored_ids(db):
    return {row[0] for row in db.execute('SELECT match_id FROM matches')}
