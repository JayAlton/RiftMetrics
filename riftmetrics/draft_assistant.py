"""Streamlit live-draft *manual input* tab. No unsupported client integration."""
from pathlib import Path
import streamlit as st
import pandas as pd
from riftmetrics.external_stats_ui import render_external_stats
from riftmetrics.draft_scoring import DEFAULT_POOL, score_pool, norm
from riftmetrics.static_data import champion_catalog, champion_image, readable_champion

PRIOR_PATH = Path(__file__).resolve().parents[1] / "data" / "matchup_priors.csv"
POSITIONS = [("TOP", "Top"), ("JUNGLE", "Jungle"), ("MIDDLE", "Mid"), ("BOTTOM", "ADC"), ("UTILITY", "Support")]


def render_live_draft(matches, version, stats_rank=None):
    st.subheader("Live Draft · Jungle Pick Assistant")
    st.caption("Enter only visible picks. Recommendations update automatically; nothing is sent to Riot or your database.")
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
    a, b = st.columns(2)
    ally, enemy = {}, {}
    with a:
        st.markdown("#### Your team")
        for role, label in POSITIONS:
            if role == "JUNGLE":
                st.caption("Jungle: your recommended pick will appear below")
                continue
            ally[role] = st.selectbox(label, options, key=f"draft_ally_{role}")
    with b:
        st.markdown("#### Enemy team")
        for role, label in POSITIONS:
            enemy[role] = st.selectbox(label, options, key=f"draft_enemy_{role}")
    enemy_jg = enemy["JUNGLE"] if enemy["JUNGLE"] != "Unknown" else None
    st.divider()
    st.markdown("#### Visible draft")
    left, right = st.columns(2)
    for side, data, parent in (("Allies", ally, left), ("Enemies", enemy, right)):
        with parent:
            st.caption(side)
            names = [x for x in data.values() if x != "Unknown"]
            if names:
                cols = st.columns(min(len(names), 5))
                for c, name in zip(cols, names):
                    with c:
                        st.image(champion_image(name, version), width=54)
                        st.caption(readable_champion(name))
            else:
                st.caption("No picks entered yet")
    picked = {norm(c) for c in list(ally.values()) + list(enemy.values()) if c != "Unknown"}
    pool = [c for c in pool if norm(c) not in picked]
    if not pool:
        st.info("All champions in your pool are already picked. Add another available champion.")
        return
    st.markdown("#### Champion recommendations")
    st.caption("Uses your selected queue’s JUNGLE history, plus automatically fetched matchup statistics and saved fallbacks. This is an experimental ranking, not a guaranteed win probability.")
    queue = st.selectbox("Personal game history", [420, 400],
                         format_func=lambda x: "Ranked Solo/Duo" if x == 420 else "Normal Draft")
    external_weight = st.slider("Maximum external matchup influence (%)", 0, 90, 90, 5)
    st.caption("External influence is reduced for samples below 1,000 games. It applies to the matchup component.")
    matchup_weight = st.slider("Head-to-head share of ranking (%)", 0, 100, 95, 5)
    personal_max = st.slider("Maximum personal history influence (%)", 0, 30, 15, 1)
    st.caption("At the default: fewer than 10 personal games gets under 5% influence, 10 games gets 5%, and 30+ games gets up to 15%. Missing evidence stays neutral; your WR never takes over when outside data is missing.")
    priors, fetched = render_external_stats(PRIOR_PATH, catalog, enemy_jg, pool, rank=stats_rank)
    rows = matches.to_dict("records") if hasattr(matches, "to_dict") else list(matches)
    results = score_pool(rows, pool, enemy_jg, priors, queue_id=queue, external_weight=external_weight / 100, matchup_weight=matchup_weight / 100, personal_max_weight=personal_max / 100)
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
    st.markdown("#### Build for your pick")
    pick = st.selectbox("Champion to build", [r["champion"] for r in results])
    build = next((r for r in fetched if r['source'] == 'Lolalytics' and r['champion'] == pick and r.get('items')), None)
    if build:
        st.write(f"{readable_champion(pick)} vs {readable_champion(enemy_jg)} · {build['record']['rank']} · Patch {build['record']['patch']}")
        cols = st.columns(len(build['items']))
        for col, item in zip(cols, build['items']):
            with col:
                from riftmetrics.static_data import item_image
                st.image(item_image(item['id'], version), width=48)
                st.write(item['name'])
        st.caption("Source core build for this specific jungle matchup, including boots when shown. This is the site's displayed build, not a calculated response to the full enemy team. Item WR is not the same as matchup WR.")
        if build.get('stale'):
            st.warning('Build is from an older cached source response; refresh when online.')
    elif enemy_jg:
        st.info("Build data unavailable for this pick. Enable Lolalytics in Automatic sources to retrieve its matchup core build.")
    else:
        st.caption("Select an enemy jungler to load a matchup build.")

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
            "External sample": external["sample"] if external else 0,
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
    st.caption("Relative scores use smoothed personal win rate and head-to-head results. External percentages come from automatic sources or saved fallback snapshots. Team-composition synergy and ban logic are not yet scored.")
