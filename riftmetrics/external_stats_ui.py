"""Source inspection and entry controls for jungle matchup evidence."""
from datetime import date
from pathlib import Path
from urllib.parse import quote
import pandas as pd
import streamlit as st
from riftmetrics.external_stats import read_records, blend_records, cohort, save_record
from riftmetrics.draft_scoring import norm
from riftmetrics.live_stats import fetch_pool, SOURCES, RANKS

SNAPSHOTS = Path(__file__).with_name('resources') / 'matchup_snapshots.csv'


def render_external_stats(path, catalog, enemy_jungler, pool, rank=None):
    if rank is None:
        rank = st.sidebar.selectbox('External data rank', list(RANKS), key='draft_stats_rank')
    st.caption(f'Matchup win rates and builds: {rank} only · Ranked Solo/Duo · All regions')
    auto = st.toggle('Automatically fetch matchup stats', value=True)
    fetched = []
    sources = st.multiselect('Automatic sources', SOURCES, default=list(SOURCES))
    refresh = st.button('Refresh matchup data', disabled=not enemy_jungler)
    if not enemy_jungler and st.button('Prepare pool cache before draft'):
        with st.spinner('Caching OP.GG jungle counter tables for your pool…'):
            prepared = fetch_pool(pool, 'Lillia', ['OP.GG'], rank=rank)
        count = sum(bool(r.get('record')) for r in prepared)
        st.info(f'Cached {count}/{len(pool)} champion counter tables. Each table covers all listed enemy junglers; builds load when an enemy is selected.')
    if auto and enemy_jungler and sources:
        with st.spinner('Loading jungle matchup stats (cached results are reused)…'):
            fetched = fetch_pool(pool, enemy_jungler, sources, force=refresh, rank=rank)
        valid = [r for r in fetched if r.get('record')]
        fresh = [r for r in valid if not r.get('stale')]
        st.caption(f'{len(fresh)}/{len(fetched)} source lookups available within the 6-hour cache window. First lookup needs internet; repeat drafts reuse local data.')
        problems = [f"{r['champion']}: {r.get('error') or 'Using older cached data'}" for r in fetched if r.get('error') or r.get('stale')]
        if problems:
            with st.expander('Source availability / older cached results'):
                for problem in problems:
                    st.write(problem)
        if not valid:
            st.warning('Automatic sources are unavailable. Saved snapshots can still be used below; missing data is not a favorable matchup.')
    records = []
    for result in fetched:
        if result.get('record'):
            row = result['record']
            records.append(dict(row, rate=row['win_rate_pct'] / 100, sample=row['sample_size'], expected_rate=None))
    with st.expander('Matchup evidence and manual fallback'):
        priors = render_evidence(path, catalog, enemy_jungler, pool, records, rank)
    return priors, fetched


def render_evidence(path, catalog, enemy_jungler, pool, live_records, rank='Iron'):
    st.markdown('#### External jungle matchup evidence')
    st.caption('Win rates are from the candidate champion’s perspective against the enemy jungler. These measure game outcomes, not solo-duel odds. Automatic results refresh after six hours; manually saved snapshots stay as entered.')
    with st.expander('Add or update a source matchup'):
        with st.form('external_matchup_entry'):
            champion = st.selectbox('Your champion', catalog, key='entry_champion')
            enemy = st.selectbox('Enemy jungler', catalog, key='entry_enemy')
            source = st.selectbox('Stats source', ['U.GG', 'Mobalytics', 'OP.GG', 'Lolalytics'])
            wr = st.number_input('Matchup win rate (%)', 0.0, 100.0, 50.0, .1)
            sample = st.number_input('Matchup games (not overall champion games)', 1, value=100, step=1)
            patch = st.text_input('Patch as displayed on source (required)')
            entry_rank = st.text_input('Rank filter', rank)
            region = st.text_input('Region filter', 'All regions')
            has_expected = st.checkbox('Source provides an expected matchup win rate')
            expected = st.number_input('Expected matchup win rate (%)', 0.0, 100.0, 50.0, .1)
            url = st.text_input('Source page URL (required)')
            observed = st.date_input('Date checked', date.today(), max_value=date.today())
            if st.form_submit_button('Save matchup locally'):
                if not patch.strip() or not entry_rank.strip() or not region.strip() or not url.startswith('https://'):
                    st.error('Enter patch, rank, region and an HTTPS source URL.')
                elif norm(champion) == norm(enemy):
                    st.error('Choose two different champions.')
                else:
                    try:
                        save_record(path, dict(champion=champion, enemy_jungler=enemy,
                            win_rate_pct=wr, sample_size=sample, source=source,
                            patch=patch.strip(), rank=entry_rank.strip(), region=region.strip(),
                            queue='420', role='JUNGLE', updated_at=observed.isoformat(),
                            expected_win_rate_pct=expected if has_expected else '', source_url=url))
                        st.success('Saved. This snapshot is available below.')
                    except OSError as exc:
                        st.error(f'Unable to save snapshot: {exc}')
    records = read_records(SNAPSHOTS) + read_records(path) + live_records
    records = [r for r in records if (r.get('rank') or '').casefold() == rank.casefold()]
    contexts = sorted({cohort(r) for r in records}, key=lambda c: tuple(int(n) for n in c[0].split('.')) if all(n.isdigit() for n in c[0].split('.')) else (0,), reverse=True)
    if not contexts:
        st.info('No external matchup stats for this rank. Other ranks are excluded; add a matching source or retry retrieval.')
        return {}
    context = st.selectbox('Saved patch and region (selected rank only)', contexts, format_func=lambda c: ' · '.join(c))
    sources = sorted({r.get('source') or 'Manual' for r in records if cohort(r) == context})
    enabled = st.multiselect('Sources included in scoring', sources, default=sources)
    priors = blend_records([r for r in records if (r.get('source') or 'Manual') in enabled], context)
    st.caption('Only the selected patch, rank, region, queue and jungle role are blended. Ranked external evidence remains ranked even if you choose Normal Draft personal history.')
    if not enemy_jungler:
        st.info('Select the enemy jungler to see head-to-head evidence.')
        return priors
    candidate = st.selectbox('Inspect matchup', pool)
    slug = lambda x: quote(norm(x).replace('&', '').replace('.', ''))
    c, e = slug(candidate), slug(enemy_jungler)
    st.markdown(f'Check sources: [Mobalytics](https://mobalytics.gg/lol/champions/{c}/counters/jungle/vs-{e}) · '
                f'[Lolalytics](https://lolalytics.com/lol/{c}/vs/{e}/build/?lane=jungle&tier={RANKS[rank]}) · '
                f'[U.GG](https://u.gg/lol/champions/{c}/counter?role=jungle&rank={RANKS[rank]}) · '
                f'[OP.GG](https://op.gg/lol/champions/{c}/counters/jungle?tier={RANKS[rank]})')
    prior = priors.get((norm(candidate), norm(enemy_jungler)))
    if not prior:
        st.info(f'No saved evidence for {candidate} versus {enemy_jungler} in this cohort. Missing data is not treated as a favorable matchup.')
        return priors
    a, b, c = st.columns(3)
    a.metric('Blended matchup WR', f'{prior["rate"]:.1%}')
    b.metric('Vs source expected', f'{prior["delta"] * 100:+.1f} pp' if prior['delta'] is not None else 'Unavailable')
    c.metric('Source disagreement', f'{prior["spread"] * 100:.1f} pp')
    st.caption('Negative expected-rate difference means worse than the source expects for this matchup. It is reported where supplied, without guessing from overall win rate.')
    table = pd.DataFrame([{'Source': r['source'], 'WR %': r['rate'] * 100,
        'Games': r['sample'], 'Vs expected pp': (r['rate']-r['expected_rate'])*100 if r['expected_rate'] is not None else None,
        'Patch': r.get('patch'), 'Checked': r.get('updated_at'), 'Page': r.get('source_url')}
        for r in prior['records']])
    st.dataframe(table, hide_index=True, column_config={'Page': st.column_config.LinkColumn('Source page')})
    st.bar_chart(table.set_index('Source')[['WR %']], horizontal=True)
    if any(not r.get('updated_at') or (date.today()-date.fromisoformat(r['updated_at'])).days > 14 for r in prior['records']):
        st.warning('This matchup includes snapshots checked more than 14 days ago or without a check date. Refresh them before relying on the score.')
    return priors
