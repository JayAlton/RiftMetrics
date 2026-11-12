"""Source inspection and entry controls for jungle matchup evidence."""
from datetime import date
from pathlib import Path
from urllib.parse import quote
import pandas as pd
import streamlit as st
from riftmetrics.external_stats import read_records, blend_records, cohort, save_record, group_rank_records
from riftmetrics.draft_scoring import norm
from riftmetrics.live_stats import fetch_pool, SOURCES, RANKS
from riftmetrics.rank_ui import select_rank_scope
from riftmetrics.rank_groups import resolve_ranks, rank_label

SNAPSHOTS = Path(__file__).with_name('resources') / 'matchup_snapshots.csv'


def render_external_stats(path, catalog, enemy_jungler, pool, rank=None):
    if rank is None:
        rank = select_rank_scope()
    ranks = resolve_ranks(rank)
    if not ranks:
        st.info('Select at least one rank to retrieve matchup statistics.')
        return {}, []
    st.caption(f'Matchup win rates: {rank_label(rank)} · Ranked Solo/Duo · All regions')
    auto = st.toggle('Automatically fetch matchup stats', value=True)
    fetched = []
    sources = st.multiselect('Automatic sources', SOURCES, default=list(SOURCES))
    refresh = st.button('Refresh matchup data', disabled=not enemy_jungler)
    if not enemy_jungler and st.button('Prepare pool cache before draft'):
        with st.spinner('Caching OP.GG jungle counter tables for your pool…'):
            prepared = fetch_pool(pool, 'Lillia', ['OP.GG'], rank=rank)
        count = sum(bool(r.get('record')) for r in prepared)
        st.info(f'Cached {count}/{len(prepared)} rank-specific champion counter tables. Each table covers all listed enemy junglers; builds load when an enemy is selected.')
    if auto and enemy_jungler and sources:
        with st.spinner('Loading jungle matchup stats (cached results are reused)…'):
            fetched = fetch_pool(pool, enemy_jungler, sources, force=refresh, rank=rank)
        valid = [r for r in fetched if r.get('record')]
        fresh = [r for r in valid if not r.get('stale')]
        st.caption(f'{len(fresh)}/{len(fetched)} source lookups available within the 6-hour cache window. First lookup needs internet; repeat drafts reuse local data.')
        problems = [f"{r['champion']} ({r.get('requested_rank', '?')}): {r.get('error') or 'Using older cached data'}" for r in fetched if r.get('error') or r.get('stale')]
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
    if len(ranks) > 1 and enemy_jungler:
        covered = sum((norm(champ), norm(enemy_jungler)) in priors for champ in pool)
        st.caption(f'Complete selected-rank evidence: {covered}/{len(pool)} pool champions. Largest source sample is a reported count, not a verified unique-match total across sites.')
    return priors, fetched


def render_evidence(path, catalog, enemy_jungler, pool, live_records, rank='Iron'):
    ranks = resolve_ranks(rank)
    label = rank_label(rank)
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
            entry_rank = st.selectbox('Rank filter', ranks, key='manual_entry_rank')
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
    records = group_rank_records(records, rank)
    if len(ranks) > 1:
        st.caption('Rank rates are weighted by reported games within each source. All selected ranks must be available on the same patch for a source to contribute. Counts across websites are not added together.')
    contexts = sorted({cohort(r) for r in records}, key=lambda c: tuple(int(n) for n in c[0].split('.')) if all(n.isdigit() for n in c[0].split('.')) else (0,), reverse=True)
    if not contexts:
        st.info('No complete external matchup data for the selected ranks on a matching patch. Missing ranks are excluded from scoring; retry retrieval or choose a narrower group.')
        return {}
    context = st.selectbox('Saved patch and region (selected rank only)', contexts, format_func=lambda c: ' · '.join(c))
    sources = sorted({r.get('source') or 'Manual' for r in records if cohort(r) == context})
    enabled = st.multiselect('Sources included in scoring', sources, default=sources)
    priors = blend_records([r for r in records if (r.get('source') or 'Manual') in enabled], context)
    st.caption('Only the selected patch, rank, region, queue and jungle role are blended. External evidence is ranked Solo/Duo; personal history combines Normal Draft and Ranked Solo/Duo jungle games.')
    if not enemy_jungler:
        st.info('Select the enemy jungler to see head-to-head evidence.')
        return priors
    candidate = st.selectbox('Inspect matchup', pool)
    slug = lambda x: quote(norm(x).replace('&', '').replace('.', ''))
    c, e = slug(candidate), slug(enemy_jungler)
    link_rank = ranks[0]
    st.markdown(f'Check sources: [Mobalytics](https://mobalytics.gg/lol/champions/{c}/counters/jungle/vs-{e}) · '
                f'[Lolalytics](https://lolalytics.com/lol/{c}/vs/{e}/build/?lane=jungle&tier={RANKS[link_rank]}) · '
                f'[U.GG](https://u.gg/lol/champions/{c}/counter?role=jungle&rank={RANKS[link_rank]}) · '
                f'[OP.GG](https://op.gg/lol/champions/{c}/counters/jungle?tier={RANKS[link_rank]})')
    prior = priors.get((norm(candidate), norm(enemy_jungler)))
    if not prior:
        st.info(f'No saved evidence for {candidate} versus {enemy_jungler} in this cohort. Missing data is not treated as a favorable matchup.')
        return priors
    a, b, c = st.columns(3)
    a.metric('Blended matchup WR', f'{prior["rate"]:.1%}')
    b.metric('Vs source expected', f'{prior["delta"] * 100:+.1f} pp' if prior['delta'] is not None else 'Unavailable')
    c.metric('Source disagreement', f'{prior["spread"] * 100:.1f} pp')
    st.caption('Negative expected-rate difference means worse than the source expects for this matchup. It is reported where supplied, without guessing from overall win rate.')
    evidence = [part for r in prior['records'] for part in r.get('rank_details', [r])]
    if len(ranks) > 1:
        st.dataframe([{'Source': r['source'], 'Ranks': r['rank'], 'Pooled WR %': round(r['rate'] * 100, 2), 'Reported games': r['sample']} for r in prior['records']], hide_index=True)
    st.caption('Links below the table identify each rank-specific source page. The quick source links above open the first selected rank.')
    table = pd.DataFrame([{'Source': r['source'], 'WR %': r['rate'] * 100,
        'Rank': r['rank'], 'Games': r['sample'], 'Vs expected pp': (r['rate']-r['expected_rate'])*100 if r['expected_rate'] is not None else None,
        'Patch': r.get('patch'), 'Checked': r.get('updated_at'), 'Page': r.get('source_url')}
        for r in evidence])
    st.dataframe(table, hide_index=True, column_config={'Page': st.column_config.LinkColumn('Source page')})
    st.bar_chart(table.assign(Label=table['Source'] + ' · ' + table['Rank']).set_index('Label')[['WR %']], horizontal=True)
    if any(not r.get('updated_at') or (date.today()-date.fromisoformat(r['updated_at'])).days > 14 for r in prior['records']):
        st.warning('This matchup includes snapshots checked more than 14 days ago or without a check date. Refresh them before relying on the score.')
    return priors
