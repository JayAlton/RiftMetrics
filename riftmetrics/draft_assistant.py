"""Streamlit live-draft *manual input* tab. No unsupported client integration."""
from pathlib import Path
import streamlit as st
from riftmetrics.draft_scoring import DEFAULT_POOL, load_external_priors, score_pool, norm
from riftmetrics.static_data import champion_catalog, champion_image, readable_champion

PRIOR_PATH = Path(__file__).resolve().parents[1] / "data" / "matchup_priors.csv"
POSITIONS = [("TOP", "Top"), ("JUNGLE", "Jungle"), ("MIDDLE", "Mid"), ("BOTTOM", "ADC"), ("UTILITY", "Support")]


def render_live_draft(matches, version):
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
    st.markdown("#### Champion recommendations")
    st.caption("Uses your Normal Draft JUNGLE games (queue 400), plus any matchup win rates you enter locally. This is an experimental ranking, not a guaranteed win probability.")
    priors = load_external_priors(PRIOR_PATH)
    rows = matches.to_dict("records") if hasattr(matches, "to_dict") else list(matches)
    results = score_pool(rows, pool, enemy_jg, priors, queue_id=400)
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
        if winner["games"] < 5:
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
            "Score": round(r["score"] * 100, 1),
        })
    st.dataframe(table, column_config={"Icon": st.column_config.ImageColumn("Portrait")},
                 hide_index=True, use_container_width=True)
    st.caption("Relative scores use smoothed personal win rate and head-to-head results. External percentages are supplementary, manually supplied priors. Team-composition synergy and ban logic are not yet scored.")
    with st.expander("External matchup win rates — CSV setup"):
        st.write("Create `data/matchup_priors.csv` using the included template. Use one row per champion versus enemy jungler, recording **source, patch, sample size and date**. No scraping is performed.")
        st.code("champion,enemy_jungler,win_rate_pct,sample_size,source,patch,updated_at\nLillia,Taliyah,51.5,1200,Lolalytics,16.22,2026-11-11", language="csv")
        st.caption("The example above is **fabricated for format illustration only** — do not use it as a real matchup statistic.")
        st.write(f"Currently loaded: **{len(priors)}** matchup records.")
