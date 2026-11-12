# Live Draft

Run `.\.venv\Scripts\python.exe -m streamlit run dashboard.py` after installing requirements. The Live Draft tab is integrated; do not run install_draft_tab.py.

## Rank and source selection

Stats rank defaults to Iron. Every individual rank from Iron through Challenger is selectable, along with Gold+, Platinum+, Emerald+, Diamond+, Master+, and All ranks. Automatic retrieval, source validation, cache keys, saved-evidence filtering and displayed builds use that selection. Different ranks never blend. A source that lacks a selected-rank matchup remains unavailable; it does not silently fall back to another rank.

OP.GG jungle counter tables and Lolalytics jungle matchup/build pages are fetched when you select an enemy jungler. Both use all regions, ranked Solo/Duo. Source HTML is cached in data/source_cache for six hours. OP.GG tables cover all listed opponents. Use Prepare pool cache before draft to warm those tables. Lolalytics retrieves exact matchup pages and the displayed core build. This may include boots and is not a full-team item optimizer.

Requests use at most six workers and bounded connect/read timeouts. Failures have a five-minute retry backoff; Refresh matchup data retries immediately. Prior cached pages survive refresh failures and older results are labeled. U.GG and Mobalytics returned HTTP 403 during direct verification and remain manual fallbacks. Access blocks are not bypassed.

## Scoring

The recommendation is a relative ranking, not a calibrated win probability. It uses the selected queue's personal JUNGLE games and external head-to-head WR from the candidate champion's perspective.

Defaults: 95% head-to-head share, 90% maximum external influence within that component, and 15% maximum personal-history influence. External share of the final score is head-to-head share × maximum external influence × min(1, external matchup games / 1000). With at least 1,000 outside games, the default external share is 85.5%. Personal history does not reduce that external share.

All personal WR paths share one budget, including personal champion WR and head-to-head WR. The sample factor is (min(n,10)/10)^2 / 3 + (2/3) × min(max(n-10,0)/20,1). Effective personal share is the chosen personal maximum × this factor, limited to the remaining score budget. With the default 15% maximum:

| Personal games | Maximum personal share |
| --- | --- |
| 0 | 0% |
| 1 | 0.05% |
| 5 | 1.25% |
| 9 | 4.05% |
| 10 | 5% |
| 30+ | up to 15% (14.5% when external share is 85.5%) |

Personal champion WR is smoothed with ten neutral pseudo-games. Personal matchup WR is smoothed with eight games of that baseline. The personal signal blends these using the head-to-head share. Final score = 50 + external share × (external WR percent - 50) + personal share × (smoothed personal signal percent - 50). The remaining share is neutral uncertainty, not reassigned to personal history. Small personal samples therefore cannot overwhelm external evidence. With no external data, the personal budget stays limited.

The table displays actual external, personal and neutral shares and the score change from external data. A top score without outside evidence is marked as uncertain; neutral does not mean favorable. Other visible team picks are for reference; composition and bans are not scored.

## Manual fallback and provenance

Use Add or update a source matchup inside the evidence expander to save WR, matchup games, patch, rank, region, source URL and check date to local data/matchup_priors.csv. Optional expected matchup WR supports a reported percentage-point difference; it is not inferred from overall champion WR. Sources blend only within the selected patch/rank/region/queue/role cohort. Sample weights are capped at 1,000 per site, and overlapping source samples are not summed. Latest dated snapshot wins for repeated source/cohort entries.

Bundled historical Emerald+ snapshots in riftmetrics/resources/matchup_snapshots.csv are available only when that rank is selected. They are not Iron data or automatic live feeds. Source disagreement and expected-WR differences are displayed for interpretation; scoring currently blends raw matchup WR.
