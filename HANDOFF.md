# RiftMetrics continuation notes

Repository: https://github.com/JayAlton/RiftMetrics
Working branch: `codex/ui-and-draft-stats`

## Current app

Python / Streamlit dashboard, with local SQLite storage. Run `dashboard.py`.
The visual Draft Room is the main Draft tab. Weights and Settings controls
its scoring and matchup sources. Historical Draft & Build is a separate view.

Implemented: ranked + normal draft update button; all five roles; obsidian/gold
theme and champion splash art; OP.GG item explorer with win rate, pick rate,
sample counts and cache; intended-champion ban recommendations; champion-name
deduplication; explicit role imports for off-meta champions.

Selected role must control both champions' lanes (`lane` and `vslane` for
Lolalytics), OP.GG role paths, personal history and cached data. Never substitute
a champion's usual role when selected-role data is missing. Small samples stay
visible and carry reduced influence. Sources can omit off-meta matchups.

Latest completed verification: 52 unit/UI tests passed. Live checks included
Morgana and Ambessa jungle. External sites may change their page markup.

## Resume on a Linux home server

Clone the working branch into a new folder:

```sh
git clone --branch codex/ui-and-draft-stats https://github.com/JayAlton/RiftMetrics.git
cd RiftMetrics
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
# Edit .env locally with your own Riot API key.
python -m streamlit run dashboard.py --server.address 0.0.0.0 --server.port 8501
```

For an existing checkout, preserve local changes, fetch the working branch and
fast-forward it rather than resetting files. Access the app through your existing
LAN/VPN or authenticated proxy; the development command above does not add login.

To run checks: `python -m unittest discover -s tests`.

## Local data to transfer privately

The repository and source ZIP do not include `.env`, `.venv`, `.vscode`, or local
`data/` contents. Existing personal history is in `data/riftmetrics.db` and saved
manual evidence in `data/matchup_priors.csv`, if present. Stop the app before
copying SQLite. Transfer these privately to the corresponding paths to preserve
your history; otherwise use the update button to import recent games again.
Source caches and exported CSVs can be recreated.

## Publishing status

The working branch is the handoff source. A previous attempt to push to `main`
was rejected by automatic approval review; do not assume `main` has this version.
No home-server deployment has been performed from this local workspace.
