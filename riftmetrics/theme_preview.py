"""Visual draft room with role-specific history, external evidence, and builds."""
from html import escape
from pathlib import Path
from urllib.parse import quote

import streamlit as st
import streamlit.components.v1 as components

from riftmetrics.draft_scoring import score_pool, norm
from riftmetrics.external_stats_ui import render_external_stats
from riftmetrics.build_ui import render_build_details, render_opgg_items
from riftmetrics.rank_groups import resolve_ranks
from riftmetrics.ban_assistant import render_ban_assistant
from riftmetrics.roles import ROLES
from riftmetrics.static_data import champion_image, readable_champion, champion_catalog


def render_theme_preview(matches, version, stats_rank="Iron", settings_container=None, stats_patch=None):
    st.subheader("Draft Room")
    st.caption(f"Statistics patch: {stats_patch or 'Latest available from source'}. Personal history includes your stored games across patches.")
    st.caption("Draft Room combines your role history with same-role matchup evidence. Select an opponent to retrieve matchup stats, items, and runes.")
    left, right = st.columns(2)
    with left:
        role = st.selectbox("Your role", list(ROLES), index=1,
                            format_func=lambda r: ROLES[r][0], key="theme_lab_role")
    label, _, default_pool = ROLES[role]
    st.caption(f"Import scope: {label} for your champion and the opponent. Champion defaults never override this role.")
    catalog = sorted(set(champion_catalog(version).values()) | set(default_pool), key=str.casefold)
    pool = st.multiselect("Your champion pool", catalog, default=default_pool, key=f"lab_pool_{role}")
    if pool:
        rows = matches.to_dict("records") if hasattr(matches, "to_dict") else list(matches)
        with st.expander("Ban recommendations", expanded=True):
            render_ban_assistant(rows, pool, role, stats_rank, version, patch=stats_patch)
    enemy_pick = st.selectbox(f"Enemy {label.lower()}", ["Unknown"] + catalog, key=f"lab_enemy_{role}")
    enemy = None if enemy_pick == "Unknown" else enemy_pick
    pool = [c for c in pool if not enemy or norm(c) != norm(enemy)]
    if not pool:
        if settings_container is not None:
            with settings_container:
                st.info("Choose a champion pool in Draft to configure its matchup sources and weights.")
        st.info("Choose at least one champion other than the enemy pick.")
        return
    settings_area = settings_container if settings_container is not None else st.expander("Weights and Settings", expanded=False)
    with settings_area:
        st.subheader("Weights and Settings")
        opgg_enabled = st.toggle("Import OP.GG item statistics", value=True, key="draft_opgg_enabled")
        st.caption(f"Applies to Draft Room · {label} · vs {enemy or 'Unknown'}. Choose your role, pool, and opponent in the Draft tab.")
        external_weight = st.slider("Maximum external matchup influence (%)", 0, 90, 90, 5, key="lab_external_weight")
        matchup_weight = st.slider("Head-to-head share of ranking (%)", 0, 100, 95, 5, key="lab_matchup_weight")
        personal_weight = st.slider("Maximum personal history influence (%)", 0, 30, 15, 1, key="lab_personal_weight")
        st.caption("External influence scales down below 1,000 source games. Personal influence scales with your role history; missing evidence stays neutral. Scores are relative rankings, not win probabilities.")
        priors, fetched = render_external_stats(
            Path(__file__).resolve().parents[1] / "data" / "matchup_priors.csv",
            catalog, enemy, pool, rank=stats_rank, role=role, namespace="lab_", patch=stats_patch)
    rows = matches.to_dict("records") if hasattr(matches, "to_dict") else list(matches)
    results = score_pool(rows, pool, enemy, priors, role=role, external_weight=external_weight / 100, matchup_weight=matchup_weight / 100, personal_max_weight=personal_weight / 100)
    with right:
        choice = st.selectbox("Inspect champion", ["Recommended pick"] + pool,
                              key=f"theme_lab_art_{role}")
    pick = results[0]["champion"] if choice == "Recommended pick" else choice
    result = next(r for r in results if r["champion"] == pick)
    # Data Dragon portraits use the same canonical champion IDs as splash art.
    image_id = champion_image(pick, version).rsplit("/", 1)[-1].removesuffix(".png")
    splash = f"https://ddragon.leagueoflegends.com/cdn/img/champion/splash/{quote(image_id)}_0.jpg"
    name = escape(readable_champion(pick))
    win_rate = f"{result['personal_wr']:.0%}" if result['personal_wr'] is not None else "—"
    heading = "Your recommended pick" if choice == "Recommended pick" else "Selected champion analysis"
    note = ("Limited personal sample · Explore this pick with care" if result["games"] < 10
            else "Based on your recorded games in this role")
    cards = "".join(
        f'<div class="pick"><img alt="" src="{escape(champion_image(r["champion"], version), quote=True)}">'
        f'<div><b>{escape(readable_champion(r["champion"]))}</b>'
        f'<span>{r["games"]} personal games · {r["matchup_games"]} vs opponent</span>'
        f'<span>Matchup WR: {format(r["external"]["rate"], ".1%") if r["external"] else "Unavailable"}</span></div>'
        f'<em>{r["score"] * 100:.1f}</em></div>' for r in results)
    external = result['external']
    external_rate = f"{external['rate']:.1%}" if external else "Unavailable"
    sample = f"{external['sample']:,}" if external else "—"
    opponent = escape(readable_champion(enemy)) if enemy else "Unknown"
    evidence = escape(f"{external['source']} · Patch {external['patch']} · Checked {external['updated_at']}") if external else "No external evidence for this matchup. Missing data stays neutral."
    extra_metrics = ''.join(f'<div class="metric"><strong>{escape(str(value))}</strong><span>{title}</span></div>' for value, title in [
        (external_rate, 'External matchup WR'), (sample, 'Largest source sample'),
        (f"{result['matchup_wins']}/{result['matchup_games']}", 'Personal head-to-head'),
        (f"{result['overall_external_weight']:.1%}", 'External score share'),
        (f"{result['personal_weight']:.1%}", 'Personal score share'),
        (f"{result['neutral_weight']:.1%}", 'Neutral uncertainty share')])
    components.html(f"""<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
    *{{box-sizing:border-box}} body{{margin:0;background:#080c10;color:#eee8d9;font:15px Georgia,serif}}
    .shell{{border:1px solid #66532f;background:radial-gradient(ellipse at top left,#182329,#0b1015 60%);padding:24px}}
    .mast{{display:flex;justify-content:space-between;gap:12px;color:#c5a568;font:11px Arial,sans-serif;letter-spacing:3px;margin-bottom:22px}}
    .hero{{min-height:390px;position:relative;overflow:hidden;border:1px solid #77613a;background:#142127}}
    .art{{position:absolute;width:100%;height:100%;object-fit:cover;object-position:65% 30%}}
    .shade{{position:absolute;inset:0;background:linear-gradient(90deg,rgba(6,12,16,.97),rgba(6,12,16,.65) 46%,rgba(6,12,16,.08)),linear-gradient(0deg,#080f16,transparent 65%)}}
    .content{{position:relative;padding:45px 32px;max-width:590px}}
    .eyebrow{{color:#d2b77b;text-transform:uppercase;font:11px Arial,sans-serif;letter-spacing:3px}}
    h1{{font-size:clamp(38px,7vw,70px);font-weight:400;margin:16px 0;color:#fff0cc;line-height:1.05}}
    .rule{{width:70px;height:2px;background:#c3a064;margin:22px 0}}
    .copy{{font:14px/1.8 Arial,sans-serif;color:#c1c8c7;max-width:310px}}
    .tag{{display:inline-block;border:1px solid #4a7273;color:#91d1c8;padding:8px 12px;font:10px Arial,sans-serif;letter-spacing:2px;margin-top:20px}}
    .metrics{{display:grid;grid-template-columns:repeat(3,1fr);border:1px solid #3d3a2b;border-top:0;background:#0d161c}}
    .metric{{padding:20px;border-right:1px solid #3d3a2b}} .metric:last-child{{border:0}}
    .metric strong{{display:block;color:#f0dab0;font-size:26px;font-weight:400}}
    .metric span{{display:block;margin-top:8px;color:#a6b1b2;font:10px Arial,sans-serif;letter-spacing:1.5px;text-transform:uppercase}}
    h2{{font-size:19px;font-weight:400;color:#dcc28b;margin:26px 0 14px}}
    .pool{{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}}
    .pick{{display:flex;align-items:center;gap:12px;background:#101b22;border:1px solid #2c3d40;padding:12px}}
    .pick img{{width:42px;height:42px;border:1px solid #a38750}} .pick b{{font-weight:400;font-size:17px}}
    .pick span{{display:block;color:#94a6aa;font:11px Arial,sans-serif;margin-top:6px}}
    .pick em{{margin-left:auto;font-style:normal;color:#8ac7bf}}
    .foot{{color:#8e9b9e;font:11px/1.7 Arial,sans-serif;margin-top:18px}}
    @media(max-width:600px){{.shell{{padding:14px}}.pool{{grid-template-columns:1fr}}.content{{padding:30px 20px}}.metric{{padding:14px 10px}}.mast{{letter-spacing:1px}}}}
    </style></head><body><main class="shell">
    <header class="mast"><span>RIFTMETRICS / DRAFT ROOM</span><span>{escape(label.upper())} · LIVE MATCHUP</span></header>
    <section class="hero"><img class="art" src="{splash}" alt="{name} splash art"><div class="shade"></div>
    <div class="content"><div class="eyebrow">{heading}</div><h1>{name}</h1><div class="rule"></div>
    <div class="copy">{escape(note)}. Compare your champion pool before locking in.</div><div class="tag">{escape(label.upper())} / NORMAL + RANKED</div></div></section>
    <section class="metrics"><div class="metric"><strong>{result['score'] * 100:.1f}</strong><span>Relative score</span></div>
    <div class="metric"><strong>{win_rate}</strong><span>Personal win rate</span></div>
    <div class="metric"><strong>{result['games']}</strong><span>Games in role</span></div></section>
    <h2>Matchup intelligence · vs {opponent}</h2>
    <section class="metrics">{extra_metrics}</section><p class="foot">{evidence}</p>
    <h2>Your shortlist</h2><section class="pool">{cards}</section>
    <footer class="foot">Scores are relative rankings, not win probabilities. External evidence uses the selected rank and role; personal history combines Normal Draft and Ranked Solo/Duo. Overlapping source samples are not added together.<br>
    Champion artwork: Riot Games / Data Dragon. Online access is needed to display splash art.</footer>
    </main></body></html>""", height=1150, scrolling=True)

    if enemy and not external:
        st.warning("No external matchup evidence for this champion in the selected cohort. A neutral score does not mean a favorable matchup.")
    st.subheader("Items and runes")
    ranks = resolve_ranks(stats_rank)
    build_rank = st.selectbox("Build rank", ranks, key="lab_build_rank") if ranks else None
    build = next((r for r in fetched if r['source'] == 'Lolalytics'
                  and r['champion'] == pick and (r.get('record') or {}).get('rank') == build_rank
                  and (r.get('items') or r.get('build'))), None)
    if build:
        st.caption(f"{pick} vs {enemy} · {build_rank} · Patch {build['record']['patch']}")
        render_build_details(build, version)
        if build.get('stale'):
            st.warning("Build is from an older cached response. Refresh matchup data when online.")
    else:
        st.info("Select an enemy and enable Lolalytics in Matchup sources to load items and runes when available.")
    if opgg_enabled and build_rank:
        render_opgg_items(pick, role, build_rank, version, patch=stats_patch)
    with st.expander("Full champion comparison"):
        st.dataframe([{
            'Champion': r['champion'], 'Score': round(r['score'] * 100, 1),
            'Personal games': r['games'], 'Personal WR': r['personal_wr'],
            'Head-to-head games': r['matchup_games'],
            'External WR': r['external']['rate'] if r['external'] else None,
            'Largest source sample': r['external']['sample'] if r['external'] else None,
            'Sources': r['external']['source'] if r['external'] else 'Unavailable',
            'Patch': r['external']['patch'] if r['external'] else '—',
        } for r in results], hide_index=True)
