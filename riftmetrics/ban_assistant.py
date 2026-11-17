"""Intent-based bans with sample-smoothed personal and OP.GG evidence."""
from concurrent.futures import ThreadPoolExecutor
import re

import requests
import streamlit as st

from riftmetrics.draft_scoring import norm
from riftmetrics.external_stats import group_rank_records, blend_records
from riftmetrics.live_stats import page, text, parse_opgg, record
from riftmetrics.rank_groups import resolve_ranks
from riftmetrics.static_data import champion_image, readable_champion


def personal_pool(rows, pool, role):
    eligible = [r for r in rows if r.get('role') == role and r.get('queue_id') in (400, 420)]
    stats = {}
    for champion in pool:
        games = [r for r in eligible if norm(r.get('champion')) == norm(champion)]
        wins = sum(bool(r.get('win')) for r in games)
        stats[champion] = dict(games=len(games), wins=wins, rate=(wins + 5) / (len(games) + 10))
    return eligible, stats


def recommend_bans(rows, pool, planned, role, priors=None):
    priors = priors or {}
    eligible, stats = personal_pool(rows, pool, role)
    backups = sorted((c for c in pool if c != planned), key=lambda c: (stats[c]['rate'], stats[c]['games']), reverse=True)[:2]
    champions = [planned] + backups
    weights = [1.] if not backups else [.8] + [.2 / len(backups)] * len(backups)

    def opponent(row):
        return ((row.get('details') or {}).get('enemy_draft') or {}).get('by_role', {}).get(role) or (row.get('enemy_jungler') if role == 'JUNGLE' else None)

    enemies = {opponent(r) for r in eligible if opponent(r)}
    for prior in priors.values():
        enemies.update(r['enemy_jungler'] for r in prior.get('records', []))
    # Riot IDs and source display names can identify the same opponent.
    enemies = {norm(enemy): readable_champion(enemy) for enemy in sorted(enemies)}
    results = []
    for enemy in enemies.values():
        if norm(enemy) in {norm(c) for c in pool} or norm(enemy) == 'unknown':
            continue
        signals = []
        for champion in champions:
            games = [r for r in eligible if norm(r.get('champion')) == norm(champion) and norm(opponent(r)) == norm(enemy)]
            wins = sum(bool(r.get('win')) for r in games)
            baseline = stats[champion]['rate']
            personal = (wins + 8 * baseline) / (len(games) + 8)
            prior = priors.get((norm(champion), norm(enemy)))
            # Unobserved matchups remain neutral. Personal evidence shrinks to baseline.
            external_share = .8 * min(1, prior['sample'] / 1000) if prior else 0
            difficulty = (1 - external_share) * (baseline - personal)
            if prior:
                difficulty += external_share * (.5 - prior['rate'])
            signals.append(dict(difficulty=difficulty, games=len(games), wins=wins, prior=prior))
        primary = signals[0]
        if not primary['games'] and not primary['prior']:
            continue
        pressure = sum(w * max(0, s['difficulty']) for w, s in zip(weights, signals))
        if pressure <= 0:
            continue
        results.append(dict(enemy=enemy, pressure=pressure, **primary,
                            encounters=sum(norm(opponent(r)) == norm(enemy) for r in eligible),
                            backup_threats=sum(s['difficulty'] > 0 for s in signals[1:])))
    return sorted(results, key=lambda r: (r['pressure'], r['encounters']), reverse=True), backups, stats


def parse_counter_table(html, champion, role, rank):
    table = text(html).split('Search a champion Win rate Games', 1)
    if len(table) != 2:
        raise ValueError('OP.GG counter table unavailable.')
    entries = re.findall(r"([A-Za-z'’&. ]+?)\s+(\d+(?:\.\d+)?)%\s+([\d,]+)", table[1])
    if not entries:
        raise ValueError('OP.GG counter rows unavailable.')
    url = page('OP.GG', champion, '', rank, role)
    # Reuse the existing champion, role and rank validation before accepting rows.
    validated, _ = parse_opgg(html, champion, entries[0][0].strip(), url, rank, role)
    return [record(champion, name.strip(), float(rate), int(games.replace(',', '')),
                   validated['patch'], 'OP.GG', url, rank, role)
            for name, rate, games in entries]


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def load_ban_evidence(champions, role, ranks):
    def retrieve(job):
        champion, rank = job
        try:
            response = requests.get(page('OP.GG', champion, '', rank, role), timeout=(3, 8),
                                    headers={'User-Agent': 'RiftMetrics/0.1 (personal League analytics)'})
            response.raise_for_status()
            return parse_counter_table(response.text, champion, role, rank), None
        except (requests.RequestException, ValueError) as exc:
            return [], f'{champion} / {rank}: {exc}'
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(retrieve, [(c, r) for c in champions for r in ranks]))
    return [r for rows, _ in results for r in rows], [error for _, error in results if error]


def render_ban_assistant(rows, pool, role, rank, version):
    st.markdown('### Who should I ban?')
    _, stats = personal_pool(rows, pool, role)
    strongest = sorted(pool, key=lambda c: (stats[c]['rate'], stats[c]['games']), reverse=True)
    planned = st.selectbox('Who do you feel like playing?', strongest, key=f'ban_planned_{role}')
    st.caption('Defaults to your strongest champion by smoothed role win rate. Bans prioritize your intended pick (80%) and your two strongest backups (20%); pool champions are protected from bans.')
    _, backups, _ = recommend_bans(rows, pool, planned, role)
    evidence_key = (planned, tuple(backups), role, tuple(resolve_ranks(rank)))
    if st.button('Load OP.GG ban matchups', key='load_ban_matchups'):
        with st.spinner('Checking counters to your intended pick and strongest backups…'):
            records, errors = load_ban_evidence((planned, *backups), role, evidence_key[-1])
        st.session_state['ban_evidence'] = (evidence_key, records, errors)
    saved = st.session_state.get('ban_evidence')
    records, errors = (saved[1], saved[2]) if saved and saved[0] == evidence_key else ([], [])
    if errors:
        with st.expander('Unavailable ban matchup sources'):
            for error in errors:
                st.write(error)
    normalized = [dict(r, rate=r['win_rate_pct'] / 100, sample=r['sample_size'], expected_rate=None) for r in records]
    priors = blend_records(group_rank_records(normalized, rank))
    bans, backups, stats = recommend_bans(rows, pool, planned, role, priors)
    personal = stats[planned]
    wr = f"{personal['wins'] / personal['games']:.1%}" if personal['games'] else 'No games'
    st.caption(f"Planning {planned}: {wr} across {personal['games']} role games. Backups: {', '.join(backups) or 'None'}.")
    if not records:
        st.info('Using your personal history only. Load OP.GG ban matchups for broader counter evidence.')
    if not bans:
        st.info('Not enough unfavorable matchup evidence to recommend a ban for this pick yet.')
        return
    top = bans[0]
    st.markdown(f"**Suggested ban: {top['enemy']}** — an unfavorable matchup for {planned}" if top['difficulty'] > 0 else f"**Suggested ban: {top['enemy']}** — protects your backup pool")
    if top['games'] < 5 and not top['prior']:
        st.warning('Limited personal head-to-head sample. Treat this as a tentative ban, not a reliable counter ranking.')
    st.dataframe([{
        'Portrait': champion_image(b['enemy'], version), 'Ban': b['enemy'],
        'Ban priority': round(b['pressure'] * 100, 2),
        'Your wins / games vs opponent': f"{b['wins']}/{b['games']}",
        'OP.GG WR for your pick': f"{b['prior']['rate']:.1%}" if b['prior'] else 'Unavailable',
        'Source games': b['prior']['sample'] if b['prior'] else None,
        'Patch': b['prior']['patch'] if b['prior'] else '—',
        'Checked': b['prior']['updated_at'] if b['prior'] else '—',
        'Also difficult for backups': b['backup_threats'],
        'Seen in your role games': b['encounters'],
    } for b in bans[:10]], hide_index=True, column_config={'Portrait': st.column_config.ImageColumn('')})
    st.caption('Priority measures estimated matchup difficulty, not ban win-rate gain. Personal matchups shrink toward your champion baseline. OP.GG WR is from your pick’s perspective. Enemy pick frequency is unavailable; your encounter counts are personal history only. Selected ranks require matching-patch evidence; samples across sites are not added.')
