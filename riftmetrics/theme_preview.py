"""Self-contained theme experiment. Remove its dashboard tab to disable it."""
from html import escape
from urllib.parse import quote

import streamlit as st
import streamlit.components.v1 as components

from riftmetrics.draft_scoring import score_pool
from riftmetrics.roles import ROLES
from riftmetrics.static_data import champion_image, readable_champion


def render_theme_preview(matches, version):
    st.subheader("Theme Lab · The champion reveal")
    st.caption("Experimental Live Draft design. Rankings here use personal history only; the main Live Draft retains its full matchup sources.")
    left, right = st.columns(2)
    with left:
        role = st.selectbox("Preview role", list(ROLES), index=1,
                            format_func=lambda r: ROLES[r][0], key="theme_lab_role")
    label, _, pool = ROLES[role]
    rows = matches.to_dict("records") if hasattr(matches, "to_dict") else list(matches)
    results = score_pool(rows, pool, role=role)
    with right:
        choice = st.selectbox("Champion artwork", ["Recommended pick"] + pool,
                              key=f"theme_lab_art_{role}")
    pick = results[0]["champion"] if choice == "Recommended pick" else choice
    result = next(r for r in results if r["champion"] == pick)
    # Data Dragon portraits use the same canonical champion IDs as splash art.
    image_id = champion_image(pick, version).rsplit("/", 1)[-1].removesuffix(".png")
    splash = f"https://ddragon.leagueoflegends.com/cdn/img/champion/splash/{quote(image_id)}_0.jpg"
    name = escape(readable_champion(pick))
    win_rate = f"{result['personal_wr']:.0%}" if result['personal_wr'] is not None else "—"
    heading = "Your recommended pick" if choice == "Recommended pick" else "Champion art preview"
    note = ("Limited personal sample · Explore this pick with care" if result["games"] < 10
            else "Based on your recorded games in this role")
    cards = "".join(
        f'<div class="pick"><img alt="" src="{escape(champion_image(r["champion"], version), quote=True)}">'
        f'<div><b>{escape(readable_champion(r["champion"]))}</b>'
        f'<span>{r["games"]} personal games</span></div>'
        f'<em>{r["score"] * 100:.1f}</em></div>' for r in results[:4])
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
    <header class="mast"><span>RIFTMETRICS / DRAFT ROOM</span><span>{escape(label.upper())} · THEME PREVIEW</span></header>
    <section class="hero"><img class="art" src="{splash}" alt="{name} splash art"><div class="shade"></div>
    <div class="content"><div class="eyebrow">{heading}</div><h1>{name}</h1><div class="rule"></div>
    <div class="copy">{escape(note)}. Compare your champion pool before locking in.</div><div class="tag">{escape(label.upper())} / NORMAL + RANKED</div></div></section>
    <section class="metrics"><div class="metric"><strong>{result['score'] * 100:.1f}</strong><span>Relative score</span></div>
    <div class="metric"><strong>{win_rate}</strong><span>Personal win rate</span></div>
    <div class="metric"><strong>{result['games']}</strong><span>Games in role</span></div></section>
    <h2>Your shortlist</h2><section class="pool">{cards}</section>
    <footer class="foot">Personal history preview · Scores are not win probabilities. No enemy matchup is selected in this preview.<br>
    Champion artwork: Riot Games / Data Dragon. Online access is needed to display splash art.</footer>
    </main></body></html>""", height=920, scrolling=True)
