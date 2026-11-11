"""RiftMetrics visual, read-only dashboard. Run: python -m streamlit run dashboard.py"""
import json
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st
from riftmetrics.static_data import (
    QUEUE_NAMES, ROLE_NAMES, champion_image, get_version, item_image,
    readable_champion,
)

DB_PATH = Path(__file__).resolve().parent / "data" / "riftmetrics.db"

st.set_page_config(page_title="RiftMetrics | Match Analytics", page_icon="🎯", layout="wide")
st.markdown("""
<style>
.block-container {padding-top: 1.5rem; max-width: 1450px;}
[data-testid="stMetric"] {background: rgba(120,130,150,.09); border: 1px solid rgba(120,130,150,.15); padding: 14px; border-radius: 12px;}
[data-testid="stMetricLabel"] {font-weight: 600;}
</style>
""", unsafe_allow_html=True)
st.title("🎯 RiftMetrics")
st.caption("Your draft and ranked performance • Champion matchups • Stored locally in SQLite")


@st.cache_data(ttl=20)
def load_matches(path: str, modified: float):
    uri = Path(path).resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as db:
        rows = db.execute("""
            SELECT m.match_id, m.played_at, m.queue_id, m.champion, m.role,
                   m.win, m.kills, m.deaths, m.assists, m.cs, m.gold,
                   m.damage, m.vision, m.duration_seconds, d.details_json
            FROM matches m
            LEFT JOIN match_details d ON d.match_id = m.match_id
            ORDER BY m.played_at DESC
        """).fetchall()
    columns = ["match_id", "played_at", "queue_id", "champion", "role", "win",
               "kills", "deaths", "assists", "cs", "gold", "damage", "vision",
               "duration_seconds", "details_json"]
    df = pd.DataFrame(rows, columns=columns)
    if df.empty:
        return df
    df["details"] = df["details_json"].map(lambda x: json.loads(x) if x else {})
    df["minutes"] = df["duration_seconds"] / 60
    df["cs_per_min"] = df["cs"] / df["minutes"].replace(0, float("nan"))
    df["gold_per_min"] = df["gold"] / df["minutes"].replace(0, float("nan"))
    df["kda"] = (df["kills"] + df["assists"]) / df["deaths"].clip(lower=1)
    df["enemy_jungler"] = df["details"].map(lambda x: x.get("enemy_jungler") or "Unknown")
    df["team_dragons"] = df["details"].map(lambda x: (x.get("team_objectives") or {}).get("dragon"))
    df["team_barons"] = df["details"].map(lambda x: (x.get("team_objectives") or {}).get("baron"))
    df["date"] = pd.to_datetime(df["played_at"], utc=True).dt.strftime("%b %d, %Y")
    return df


def roster(label, draft, version):
    st.markdown(f"**{label}**")
    roles = (draft or {}).get("by_role") or {}
    labels = [("TOP", "Top"), ("JUNGLE", "Jungle"), ("MIDDLE", "Mid"),
              ("BOTTOM", "ADC"), ("UTILITY", "Support")]
    cols = st.columns(5)
    for col, (role, role_label) in zip(cols, labels):
        with col:
            name = roles.get(role)
            if name:
                st.image(champion_image(name, version), width=54)
                st.caption(f"{role_label}: {readable_champion(name)}")
            else:
                st.caption(f"{role_label}: —")
    extras = (draft or {}).get("unassigned") or []
    if extras:
        st.caption("Unassigned/duplicate roles: " + ", ".join(
            readable_champion(x.get("champion")) for x in extras))


def show_match(row, version):
    details = row["details"] or {}
    if not details:
        st.info("Detailed data unavailable for this game. Run the backfill first.")
        return
    header, stats = st.columns([1, 4])
    with header:
        st.image(champion_image(row["champion"], version), width=110)
    with stats:
        result = "Victory" if row["win"] else "Defeat"
        st.subheader(f"{readable_champion(row['champion'])} — {result}")
        st.caption(f"{row['date']} • {row['match_id']} • {row['role'] or 'Unknown role'}")
        st.write(f"**{row['kills']}/{row['deaths']}/{row['assists']}** KDA  ·  "
                 f"**{row['cs_per_min']:.2f}** CS/min  ·  "
                 f"**{row['damage']:,}** champion damage  ·  "
                 f"**{row['minutes']:.1f}** minutes")
    st.divider()
    ally_col, enemy_col = st.columns(2)
    with ally_col:
        roster("Your team", details.get("ally_draft"), version)
    with enemy_col:
        roster("Enemy team", details.get("enemy_draft"), version)
    st.divider()
    st.markdown("**Final items**")
    items = [x for x in details.get("items_at_game_end", []) if item_image(x, version)]
    if items:
        cols = st.columns(7)
        for col, item in zip(cols, items):
            with col:
                st.image(item_image(item, version), width=56)
                st.caption(f"ID {item}")
    else:
        st.caption("No final items reported.")
    left, right = st.columns(2)
    with left:
        st.markdown("**Team objectives**")
        obj = details.get("team_objectives") or {}
        st.write(f"Dragons: **{obj.get('dragon', '—')}**  ·  Barons: **{obj.get('baron', '—')}**  ·  "
                 f"Heralds: **{obj.get('riftHerald', '—')}**  ·  Horde: **{obj.get('horde', '—')}**")
        st.caption("Horde is Riot's raw objective count; not yet validated as individual Void Grubs.")
    with right:
        st.markdown("**Enemy objectives**")
        obj = details.get("enemy_team_objectives") or {}
        st.write(f"Dragons: **{obj.get('dragon', '—')}**  ·  Barons: **{obj.get('baron', '—')}**  ·  "
                 f"Heralds: **{obj.get('riftHerald', '—')}**  ·  Horde: **{obj.get('horde', '—')}**")
    with st.expander("Runes, summoner spells and personal objective data"):
        st.json({key: details.get(key) for key in
                 ("runes", "summoner_spell_ids", "personal_objectives")})


if not DB_PATH.exists():
    st.error("No database found at data/riftmetrics.db. Run the importer first.")
    st.stop()
try:
    matches = load_matches(str(DB_PATH), DB_PATH.stat().st_mtime)
except (sqlite3.Error, ValueError, json.JSONDecodeError) as exc:
    st.error(f"Unable to read database: {exc}")
    st.stop()
if matches.empty:
    st.info("No matches have been imported yet.")
    st.stop()

version = get_version()
queues = sorted(int(x) for x in matches["queue_id"].dropna().unique())
queue = st.sidebar.selectbox("Game mode", queues, format_func=lambda x: QUEUE_NAMES.get(x, str(x)),
                             index=queues.index(400) if 400 in queues else 0)
filtered = matches[matches["queue_id"] == queue].copy()
roles = sorted(str(x) for x in filtered["role"].dropna().unique() if x)
role = st.sidebar.selectbox("Role", ["All roles"] + roles,
                            format_func=lambda x: ROLE_NAMES.get(x, x))
if role != "All roles":
    filtered = filtered[filtered["role"] == role]
champions = sorted(filtered["champion"].dropna().unique())
selected = st.sidebar.multiselect("Champion", champions, default=champions)
filtered = filtered[filtered["champion"].isin(selected)]
result_filter = st.sidebar.selectbox("Result", ["All", "Wins", "Losses"])
if result_filter != "All":
    filtered = filtered[filtered["win"] == (1 if result_filter == "Wins" else 0)]
st.sidebar.caption(f"Data Dragon patch: {version} • Read-only SQLite")

if filtered.empty:
    st.warning("No matches match these filters.")
    st.stop()

# Keep the overview compact and the dense information in dedicated tabs.
overview, champions_tab, matches_tab, draft_tab = st.tabs(
    ["📊 Overview", "🏆 Champions", "🗂️ Matches", "🧩 Draft & Build"])
with overview:
    games = len(filtered)
    a, b, c, d = st.columns(4)
    a.metric("Games", f"{games}")
    b.metric("Win rate", f"{filtered['win'].mean():.1%}")
    c.metric("Average KDA", f"{filtered['kda'].mean():.2f}")
    d.metric("Average CS/min", f"{filtered['cs_per_min'].mean():.2f}")
    st.subheader("Recent performance")
    timeline = filtered.sort_values("played_at").copy()
    timeline["rolling_winrate"] = timeline["win"].rolling(10, min_periods=1).mean() * 100
    st.line_chart(timeline.set_index("played_at")["rolling_winrate"], y_label="Rolling win rate (%)")
    st.caption("Rolling last 10 matches (or fewer when your sample is small).")

with champions_tab:
    summary = filtered.groupby("champion", as_index=False).agg(
        games=("win", "size"), wins=("win", "sum"),
        avg_kda=("kda", "mean"), avg_cs_min=("cs_per_min", "mean"),
        avg_gold_min=("gold_per_min", "mean"), avg_damage=("damage", "mean"),
    )
    summary["win_rate"] = summary["wins"] / summary["games"] * 100
    summary["icon"] = summary["champion"].map(lambda x: champion_image(x, version))
    summary["champion"] = summary["champion"].map(readable_champion)
    summary = summary.sort_values(["games", "win_rate"], ascending=False)
    st.dataframe(summary[["icon", "champion", "games", "wins", "win_rate", "avg_kda", "avg_cs_min", "avg_gold_min", "avg_damage"]].round(2),
                 column_config={"icon": st.column_config.ImageColumn(""),
                                "champion": "Champion", "games": "Games", "wins": "Wins",
                                "win_rate": st.column_config.NumberColumn("WR %", format="%.1f%%"),
                                "avg_kda": st.column_config.NumberColumn("Avg KDA", format="%.2f"),
                                "avg_cs_min": st.column_config.NumberColumn("CS/min", format="%.2f"),
                                "avg_gold_min": st.column_config.NumberColumn("Gold/min", format="%.0f"),
                                "avg_damage": st.column_config.NumberColumn("Avg damage", format="%.0f")},
                 hide_index=True, use_container_width=True)
    st.caption("Win rates represent your recorded games only, not global champion statistics.")

with matches_tab:
    match_list = filtered[["date", "champion", "role", "win", "kills", "deaths", "assists",
                           "cs_per_min", "enemy_jungler", "match_id"]].copy()
    match_list.insert(0, "icon", match_list["champion"].map(lambda x: champion_image(x, version)))
    match_list["result"] = match_list["win"].map({1: "Win", 0: "Loss"})
    st.dataframe(match_list[["icon", "date", "champion", "role", "result", "kills", "deaths",
                             "assists", "cs_per_min", "enemy_jungler", "match_id"]].round(2),
                 column_config={"icon": st.column_config.ImageColumn(""),
                                "champion": "Champion", "cs_per_min": "CS/min",
                                "enemy_jungler": "Enemy jungle"},
                 hide_index=True, use_container_width=True)

with draft_tab:
    labels = {r.match_id: f"{r.date} • {readable_champion(r.champion)} • {'Win' if r.win else 'Loss'}" for r in filtered.itertuples()}
    selected_match_id = st.selectbox("Inspect a match", list(labels), format_func=lambda x: labels[x])
    row = filtered.loc[filtered["match_id"] == selected_match_id].iloc[0]
    show_match(row, version)
    st.caption("Draft view shows historical picks. Automated live draft recommendations are a future milestone.")
