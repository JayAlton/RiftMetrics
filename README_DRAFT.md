# RiftMetrics Live Draft — manual input patch

1. Copy `riftmetrics/draft_assistant.py`, `riftmetrics/draft_scoring.py`, `install_draft_tab.py`, `tests/test_draft_scoring.py` and `data/matchup_priors.example.csv` into the matching paths in your existing RiftMetrics repository.
2. Stop Streamlit (Ctrl+C), then run `\.venv\Scripts\python.exe install_draft_tab.py` in PowerShell from the repository root. This patches **only** the `st.tabs` assignment and appends a new section; it backs up your dashboard to `dashboard.before_live_draft.py.bak`.
3. Run `\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_draft_scoring.py" -v`.
4. Run `\.venv\Scripts\python.exe -m streamlit run dashboard.py` and open the **Live Draft** tab.
5. To add external stats, run `Copy-Item data\matchup_priors.example.csv data\matchup_priors.csv`, then open it with `code data\matchup_priors.csv`. Enter real stats (not the UI's illustrative example). The CSV is local, not required for the tab to work.
6. Add `data/matchup_priors.csv` to `.gitignore` if you prefer the manually curated data to stay private. The example CSV is safe to commit.

The recommendation uses only **Normal Draft (queue 400) jungle-role games**, regardless of sidebar filters, and can evaluate champions with zero games using neutral priors. It does not auto-detect your current draft, make champion picks, or assert third-party win rates.
