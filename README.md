# RiftMetrics

Personal League of Legends PC ranked analytics for **Destro493#NA1** using Riot Games APIs.

## Quick start (Windows PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env in VS Code and put your *own* Riot key in RIOT_API_KEY
python main.py --games 20
```

The script creates `data/riftmetrics.db` (SQLite) and `data/champion_stats.csv`, which can be imported into Excel or Google Sheets. Re-run to fetch new matches; duplicate match IDs are skipped.

## Key handling

Never commit `.env`, API tokens, or your local `data/` directory. These paths are gitignored. Development keys expire periodically and may need renewal.

## Data sources

- Account-V1: Riot ID to PUUID (`americas`)
- Match-V5: ranked match ID list and match details (`americas`)
- League-V4: ranked snapshot (`na1`)

Queue `420` = Ranked Solo/Duo. Does not work for Wild Rift. Conservative request pacing is included, but heavy usage requires broader app-level rate limiting.

## Roadmap

- Match timeline objective analytics
- Match-by-match CSV / spreadsheet matching the existing custom champion tracker
- Local dashboard and polling/scheduled sync
- Unit tests and configurable multi-user support

RiftMetrics is not endorsed by Riot Games and is not affiliated with Riot Games.
