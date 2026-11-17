"""Refresh personal ranked and normal draft history for the dashboard."""
import os
from contextlib import closing
from pathlib import Path

from dotenv import load_dotenv

from main import import_matches, export_champions
from riftmetrics.api import RiotClient
from riftmetrics.detail_storage import backfill
from riftmetrics.storage import connect


def sync_recent_games(db_path, games=20):
    """Examine the latest games per queue, skipping matches already stored."""
    if not 1 <= games <= 1000:
        raise ValueError('Games per mode must be between 1 and 1000.')
    db_path = Path(db_path)
    load_dotenv(db_path.parent.parent / '.env')
    client = RiotClient(os.getenv('RIOT_API_KEY'), os.getenv('RIOT_REGION', 'americas'),
                        os.getenv('RIOT_PLATFORM', 'na1'))
    try:
        name = os.getenv('RIOT_GAME_NAME', 'Destro493')
        tag = os.getenv('RIOT_TAG_LINE', 'NA1')
        account = client.account(name, tag)
        with closing(connect(db_path)) as db:
            counts = {}
            for queue in (420, 400):
                counts[queue] = import_matches(client, db, account['puuid'], games, queue)
            detailed, failed = backfill(db, name, tag, puuid=account['puuid'])
            for queue in counts:
                export_champions(db, queue, db_path.parent / f'champion_stats_{queue}.csv')
        return counts, detailed, failed
    finally:
        client.session.close()
