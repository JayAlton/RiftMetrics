"""Import your latest ranked Solo/Duo games and export champion performance."""
import argparse
import csv
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from riftmetrics.api import RiotClient, RiotAPIError
from riftmetrics.storage import connect, stored_ids
from riftmetrics.champions import normalize_champion_name
from riftmetrics.detail_storage import backfill


def import_matches(client, db, puuid, max_games, queue):
    known = stored_ids(db)
    imported = 0
    # Riot's match ID endpoint returns up to 100 per page.
    for start in range(0, max_games, 100):
        ids = client.match_ids(puuid, start=start, count=min(100, max_games - start), queue=queue)
        if not ids:
            break
        for match_id in ids:
            if match_id in known:
                continue
            match = client.match(match_id)
            info = match['info']
            player = next((p for p in info['participants'] if p['puuid'] == puuid), None)
            if player is None:
                continue
            played = datetime.fromtimestamp(info['gameStartTimestamp'] / 1000, timezone.utc).isoformat()
            champion = normalize_champion_name(player['championName'])
            cs = player.get('totalMinionsKilled', 0) + player.get('neutralMinionsKilled', 0)
            duration = info.get('gameDuration', 0)
            db.execute('''INSERT OR IGNORE INTO matches
              (match_id, played_at, queue_id, champion, role, win, kills, deaths, assists, cs,
               gold, damage, vision, duration_seconds, raw_json)
              VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
              (match_id, played, info.get('queueId'), champion,
               player.get('teamPosition') or player.get('individualPosition'), int(player['win']),
               player['kills'], player['deaths'], player['assists'], cs, player['goldEarned'],
               player['totalDamageDealtToChampions'], player.get('visionScore', 0), duration,
               json.dumps(match)))
            db.commit()
            known.add(match_id)
            imported += 1
            print(f'Imported {match_id}: {champion} {"W" if player["win"] else "L"}')
            time.sleep(1.3)  # Conservative pacing under personal-key app limits.
        if len(ids) < min(100, max_games - start):
            break
    return imported


def export_champions(db, queue=400, output=None):
    if output is None:
        output = f'data/champion_stats_{queue}.csv'

    rows = db.execute('''SELECT champion, COUNT(*) games, SUM(win) wins,
        ROUND(100.0*AVG(win),1) win_rate,
        ROUND(AVG(kills),2) avg_kills, ROUND(AVG(deaths),2) avg_deaths,
        ROUND(AVG(assists),2) avg_assists, ROUND(AVG(gold),0) avg_gold,
        ROUND(AVG(damage),0) avg_damage, ROUND(AVG(cs),1) avg_cs,
        ROUND(AVG(vision),1) avg_vision
        FROM matches
        WHERE queue_id = ?
        GROUP BY champion
        ORDER BY games DESC, win_rate DESC
        ''', (queue,)).fetchall()
    
    columns = ['champion','games','wins','win_rate_pct','avg_kills','avg_deaths',
               'avg_assists','avg_gold','avg_damage','avg_cs','avg_vision']
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    with open(output, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)
    print(f'Exported {len(rows)} champions to {output}')
    return rows


def main():
    parser = argparse.ArgumentParser(description='RiftMetrics League of Legends tracker')
    parser.add_argument('--games', type=int, default=20, help='Max recent ranked matches to examine')
    parser.add_argument(
        '--queue',
        type=int,
        choices=[400, 420],
        default=400,
        help='400 = Normal Draft, 420 = Ranked Solo/Duo'
    )
    parser.add_argument('--export-only', action='store_true', help='Regenerate CSV without contacting Riot')
    args = parser.parse_args()
    if args.games < 1 or args.games > 1000:
        parser.error('--games must be between 1 and 1000')
    load_dotenv()
    with connect() as db:
        if not args.export_only:
            client = RiotClient(os.getenv('RIOT_API_KEY'), os.getenv('RIOT_REGION', 'americas'), os.getenv('RIOT_PLATFORM', 'na1'))
            name, tag = os.getenv('RIOT_GAME_NAME', 'Destro493'), os.getenv('RIOT_TAG_LINE', 'NA1')
            account = client.account(name, tag)
            print(f'Found {account["gameName"]}#{account["tagLine"]}')
            count = import_matches(client, db, account['puuid'], args.games, args.queue)
            print(f'New matches stored: {count}')
            detailed, failed = backfill(db, name, tag, puuid=account['puuid'])
            print(f'New detailed records: {detailed}')
            for match_id, reason in failed:
                print(f'Could not parse details for {match_id}: {reason}')
            ranked = client.ranked(account['puuid'])
            for entry in ranked:
                if entry.get('queueType') != 'RANKED_SOLO_5x5':
                    continue
                db.execute('''INSERT INTO rank_snapshots
                     (captured_at,queue,tier,division,lp,wins,losses) VALUES (?,?,?,?,?,?,?)''',
                     (datetime.now(timezone.utc).isoformat(), entry.get('queueType'), entry.get('tier'),
                      entry.get('rank'), entry.get('leaguePoints'), entry.get('wins'), entry.get('losses')))
                db.commit()
                print(f'Rank: {entry.get("tier")} {entry.get("rank")} {entry.get("leaguePoints")} LP')
        export_champions(db, args.queue)

if __name__ == '__main__':
    try:
        main()
    except (RiotAPIError, KeyError, ValueError) as error:
        raise SystemExit(f'Error: {error}') from error
