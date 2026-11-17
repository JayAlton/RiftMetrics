"""Shared obsidian, antique gold, and teal dashboard presentation."""
from html import escape
from urllib.parse import quote

import streamlit as st

from riftmetrics.static_data import champion_image, readable_champion


def apply_theme():
    st.markdown("""<style>
    .stApp {background:radial-gradient(ellipse at top left,#182329 0%,#0b1015 55%,#080c10 100%);color:#eee8d9;}
    .block-container {padding-top:1.5rem;max-width:1450px;}
    h1,h2,h3,h4 {font-family:Georgia,'Times New Roman',serif!important;font-weight:400!important;color:#e6c991!important;}
    h1 {letter-spacing:1px;}
    [data-testid="stSidebar"] {background:linear-gradient(180deg,#111c22,#080e13);border-right:1px solid #51452e;}
    [data-testid="stHeader"] {background:transparent;}
    [data-testid="stMetric"] {background:linear-gradient(135deg,#16232a,#0c141a);border:1px solid #51452e;border-radius:2px;padding:18px;}
    [data-testid="stMetricLabel"] {color:#b8c1be;font-size:.8rem;letter-spacing:.6px;}
    [data-testid="stMetricValue"] {color:#efd8a7;font-family:Georgia,serif;}
    [data-testid="stCaptionContainer"] {color:#a9b5b5;}
    [data-baseweb="tab-list"] {gap:6px;border-bottom:1px solid #51452e;}
    button[data-baseweb="tab"] {color:#b9c5c4;border-radius:0;padding:12px 18px;}
    button[data-baseweb="tab"][aria-selected="true"] {color:#f1d7a0;background:#1c2527;}
    [data-baseweb="tab-highlight"] {background:#c5a568;}
    div.stButton>button,div.stFormSubmitButton>button {border-radius:2px;border:1px solid #88703f;}
    div.stButton>button[kind="primary"],div.stFormSubmitButton>button[kind="primary"] {background:linear-gradient(135deg,#c5a568,#e1c58b);color:#101619;}
    div.stButton>button:hover {border-color:#e5c98e;box-shadow:0 0 14px #c5a56825;}
    div.stButton>button:focus-visible,button[data-baseweb="tab"]:focus-visible {outline:2px solid #8ac7bf;outline-offset:3px;}
    [data-testid="stExpander"] {border:1px solid #3c4946;border-radius:2px;background:#0d171ddd;}
    [data-testid="stDataFrame"], [data-testid="stVegaLiteChart"] {border:1px solid #384440;border-radius:2px;}
    hr {border-color:#51452e!important;}
    .rm-reveal {position:relative;overflow:hidden;border:1px solid #8a7143;margin:12px 0 20px;background:#101c22;min-height:290px;}
    .rm-reveal img {position:absolute;width:100%;height:100%;object-fit:cover;object-position:65% 30%;}
    .rm-reveal-shade {position:absolute;inset:0;background:linear-gradient(90deg,rgba(6,12,16,.98),rgba(6,12,16,.72) 48%,rgba(6,12,16,.12)),linear-gradient(0deg,#080f16,transparent 75%);}
    .rm-reveal-copy {position:relative;padding:36px;max-width:650px;}
    .rm-reveal .rm-kicker {font:11px Arial,sans-serif;letter-spacing:3px;color:#e0c58b;text-transform:uppercase;}
    .rm-reveal h3 {font-size:clamp(34px,5vw,60px)!important;color:#fff0cc!important;margin:12px 0!important;padding:0!important;}
    .rm-reveal p {color:#c4cfcd;font:14px/1.8 Arial,sans-serif;}
    .rm-reveal .rm-chip {display:inline-block;border:1px solid #4a7273;color:#a0ddd3;padding:7px 10px;font:10px Arial,sans-serif;letter-spacing:1.5px;}
    @media(max-width:600px) {.rm-reveal-copy {padding:24px;} button[data-baseweb="tab"] {padding:10px;} }
    </style>""", unsafe_allow_html=True)


def render_champion_reveal(winner, version, role_label, enemy=None):
    """Present the scored recommendation without changing ranking or evidence."""
    image_id = champion_image(winner['champion'], version).rsplit('/', 1)[-1].removesuffix('.png')
    url = f"https://ddragon.leagueoflegends.com/cdn/img/champion/splash/{quote(image_id)}_0.jpg"
    name = escape(readable_champion(winner['champion']))
    opponent = f" · vs {escape(readable_champion(enemy))}" if enemy else " · Opponent unknown"
    st.markdown(f"""<section class="rm-reveal" aria-label="Recommended champion">
    <img src="{escape(url, quote=True)}" alt="{name} splash art">
    <div class="rm-reveal-shade"></div><div class="rm-reveal-copy">
    <div class="rm-kicker">Your recommended pick / {escape(role_label)}</div>
    <h3>Recommended: {name}</h3>
    <p>{winner['games']} personal games · {winner['matchup_games']} vs selected opponent<br>
    {winner['score'] * 100:.1f} relative ranking score{opponent}</p>
    <span class="rm-chip">NORMAL DRAFT + RANKED SOLO/DUO</span>
    </div></section>""", unsafe_allow_html=True)
