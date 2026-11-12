"""Streamlit live-draft *manual input* tab. No unsupported client integration."""
from pathlib import Path
import streamlit as st
import pandas as pd
from riftmetrics.rank_groups import resolve_ranks
from riftmetrics.build_ui import render_build_details
from riftmetrics.external_stats_ui import render_external_stats
from riftmetrics.draft_scoring import DEFAULT_POOL, score_pool, norm
from riftmetrics.static_data import champion_catalog, champion_image, readable_champion

PRIOR_PATH = Path(__file__).resolve().parents[1] / "data" / "matchup_priors.csv"


def render_live_draft(matches, version, stats_rank=None):
    st.subheader("Live Draft · Jungle Pick Assistant")
    st.caption("Select the enemy jungler to compare your jungle pool. Recommendations use jungle-versus-jungle matchup data.")
    catalog = sorted(set(champion_catalog(version).values()) | set(DEFAULT_POOL), key=str.casefold)
    if not catalog:
        catalog = sorted(set(DEFAULT_POOL))
    options = ["Unknown"] + catalog
    pool = st.multiselect("Your jungle champion pool", catalog,
                          default=[c for c in DEFAULT_POOL if c in catalog],
                          key="live_draft_pool")
    if not pool:
        st.info("Select at least one jungle champion to compare.")
        return
    enemy_pick = st.selectbox("Enemy jungler", options, key="draft_enemy_JUNGLE")
    enemy_jg = enemy_pick if enemy_pick != "Unknown" else None
    pool = [c for c in pool if not enemy_jg or norm(c) != norm(enemy_jg)]
    if not pool:
        st.info("Your only pool champion is the enemy pick. Add another champion to compare.")
        return
    st.markdown("#### Champion recommendations")
    st.caption("Uses your combined Normal Draft + Ranked Solo/Duo JUNGLE history, plus automatically fetched matchup statistics and saved fallbacks. This is an experimental ranking, not a guaranteed win probability.")
    external_weight = st.slider("Maximum external matchup influence (%)", 0, 90, 90, 5)
    st.caption("External influence is reduced for samples below 1,000 games. It applies to the matchup component.")
    matchup_weight = st.slider("Head-to-head share of ranking (%)", 0, 100, 95, 5)
    personal_max = st.slider("Maximum personal history influence (%)", 0, 30, 15, 1)
    st.caption("At the default: fewer than 10 personal games gets under 5% influence, 10 games gets 5%, and 30+ games gets up to 15%. Missing evidence stays neutral; your WR never takes over when outside data is missing.")
    priors, fetched = render_external_stats(PRIOR_PATH, catalog, enemy_jg, pool, rank=stats_rank)
    rows = matches.to_dict("records") if hasattr(matches, "to_dict") else list(matches)
    results = score_pool(rows, pool, enemy_jg, priors, external_weight=external_weight / 100, matchup_weight=matchup_weight / 100, personal_max_weight=personal_max / 100)
    if not results:
        return
    winner = results[0]
    pic, why = st.columns([1, 6])
    with pic:
        st.image(champion_image(winner["champion"], version), width=80)
    with why:
        st.markdown(f"### Recommended: {readable_champion(winner['champion'])}")
        st.write(f"**{winner['games']}** personal jungle games · "
                 f"**{winner['matchup_games']}** vs selected jungler · "
                 f"**{winner['score']*100:.1f}** relative ranking score")
        if enemy_jg and not winner["external"]:
            st.warning("This top-ranked pick has no external matchup evidence in the selected cohort. A neutral score does not mean a favorable matchup.")
        if winner["games"] < 10:
            st.warning("Limited personal sample — recommendation is uncertain.")
    table = []
    for rank, r in enumerate(results, 1):
        external = r["external"]
        table.append({
            "Rank": rank, "Icon": champion_image(r["champion"], version),
            "Champion": readable_champion(r["champion"]), "Jungle games": r["games"],
            "Personal WR": f"{r['personal_wr']:.1%}" if r["personal_wr"] is not None else "No games",
            "Vs enemy JG": f"{r['matchup_wins']}/{r['matchup_games']}" if enemy_jg else "Unknown",
            "External WR": f"{external['rate']:.1%}" if external else "—",
            "Sources": external["source"] if external else "—",
            "Largest source sample": external["sample"] if external else 0,
            "Patch": external["patch"] if external else "—",
            "Updated": external["updated_at"] if external else "—",
            "Score change from external (points)": round(r["external_score_change"] * 100, 2),
            "Personal history share %": round(r["personal_weight"] * 100, 2),
            "Neutral uncertainty share %": round(r["neutral_weight"] * 100, 2),
            "Overall external share %": round(r["overall_external_weight"] * 100, 1),
            "Matchup influence %": round(r["external_weight"] * 100, 1),
            "Score": round(r["score"] * 100, 1),
        })
    st.dataframe(table, column_config={"Icon": st.column_config.ImageColumn("Portrait")},
                 hide_index=True, use_container_width=True)
    st.bar_chart(pd.DataFrame({"Champion": [r["champion"] for r in results], "Score": [r["score"] * 100 for r in results]}).set_index("Champion"), horizontal=True)
    st.caption("External evidence is restricted to the selected cohort. Patch and date are displayed for review; snapshots require updates. Each source is capped at 1,000 games for blending; overlapping samples are not added together.")
    st.caption("Relative scores use smoothed personal win rate and head-to-head results. External percentages come from automatic sources or saved fallback snapshots. Only the jungle matchup is evaluated; team composition is outside this view.")

    st.markdown("#### Build for your pick")
    pick = st.selectbox("Champion to build", [r["champion"] for r in results])
    build_ranks = resolve_ranks(stats_rank if stats_rank is not None else (st.session_state.get('draft_custom_ranks', []) if st.session_state.get('draft_stats_rank') == 'Custom rank group' else st.session_state.get('draft_stats_rank', 'Iron')))
    build_rank = st.selectbox('Build and rune rank', build_ranks) if len(build_ranks) > 1 else (build_ranks[0] if build_ranks else None)
    if len(build_ranks) > 1:
        st.caption('Matchup scores pool your selected ranks. Items and runes are shown for one rank at a time; separate rune pages are not mixed.')
    build = next((r for r in fetched if r['source'] == 'Lolalytics' and r['champion'] == pick and (r.get('record') or {}).get('rank') == build_rank and (r.get('items') or r.get('build'))), None)
    if build:
        st.write(f"{readable_champion(pick)} vs {readable_champion(enemy_jg)} · {build['record']['rank']} · Patch {build['record']['patch']}")
        render_build_details(build, version)
        st.caption("Lolalytics matchup build for the selected rank and patch. This is the site's displayed build, not a calculated response to the full enemy team.")
        if build.get('stale'):
            st.warning('Build is from an older cached source response; refresh when online.')
    elif enemy_jg:
        st.info("Build data unavailable for this pick. Enable Lolalytics in Automatic sources to retrieve its matchup items and runes.")
    else:
        st.caption("Select an enemy jungler to load a matchup build.")
