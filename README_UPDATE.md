# RiftMetrics visual analytics update

Copy `dashboard.py` over the existing dashboard and add `riftmetrics/analytics.py` and `tests/test_analytics.py`.

This update uses the existing `riftmetrics/static_data.py` from the previous visual-dashboard update. It never edits SQLite or calls Riot's match APIs.

Install if needed: `python -m pip install streamlit pandas requests python-dotenv`

Run: `python -m unittest discover -s tests -p test_analytics.py -v`

Launch: `python -m streamlit run dashboard.py`

## Important interpretation
- Objective damage is Riot's `damageDealtToObjectives`, which **includes more than epic monsters**. It is not per-dragon/per-Baron damage.
- Horde counts use Riot's raw objective key, not verified individual Void Grub counts.
- Objective control uses total objectives secured by your team divided by total objectives secured by both teams. Games without reported values are excluded.
- Win rate estimates and champion shortlists use **only your historical data**, with a neutral 50% prior worth 10 games. No third-party matchup stats are ingested.
- The dashboard is read-only. Keep your existing `data/riftmetrics.db` and `.env` unchanged.
