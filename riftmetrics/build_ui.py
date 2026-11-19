"""In-draft item paths and rune choices from the validated matchup page."""
import pandas as pd
import streamlit as st
from riftmetrics.static_data import item_image


def render_opgg_items(champion, role, rank, version, patch=None):
    from riftmetrics.opgg_items import fetch_items

    st.markdown('#### OP.GG item explorer')
    refresh = st.button('Refresh OP.GG items', key='draft_opgg_refresh')
    with st.spinner('Loading OP.GG item statistics…'):
        result = fetch_items(champion, role, rank, force=refresh, patch=patch)
    if result['error']:
        st.warning(f"OP.GG item retrieval: {result['error']}")
    data = result['data']
    if not data:
        st.info('No validated OP.GG item data available. Try refreshing later.')
        return
    if result['stale']:
        st.warning('Showing older cached OP.GG item data.')
    st.caption(f"{champion} · {role} · {rank} · All regions · Patch {data['patch']} · Retrieved {result['checked_at']}")
    st.markdown(f"[Open OP.GG item source]({result['source_url']})")
    st.caption('Champion-and-role totals across opponents. These are not enemy-specific matchup builds or purchase-position statistics. Core-build WR belongs to the entire combination.')
    left, right = st.columns(2)
    with left:
        minimum = st.number_input('Minimum item games', min_value=1, value=100, step=25, key='draft_opgg_min_games')
    with right:
        order = st.selectbox('Sort OP.GG items', ['Pick rate', 'Win rate', 'Games'], key='draft_opgg_sort')
    sort_key = {'Pick rate': 'pick_rate_pct', 'Win rate': 'win_rate_pct', 'Games': 'games'}[order]
    for section in ('Core builds', 'Boots', 'Starter items', 'Items'):
        with st.expander(section, expanded=section == 'Items'):
            rows = sorted((r for r in data['rows'] if r['section'] == section and r['games'] >= minimum), key=lambda r: r[sort_key], reverse=True)
            if not rows:
                st.caption('No rows meet the minimum game count.')
                continue
            st.dataframe([{
                'Icon': item_image(r['items'][0]['id'], version),
                'Item / combination': ' → '.join(i['name'] or str(i['id']) for i in r['items']),
                'Win rate %': r['win_rate_pct'], 'Pick rate %': r['pick_rate_pct'], 'Games': r['games'],
            } for r in rows], hide_index=True, column_config={'Icon': st.column_config.ImageColumn('')})
    st.caption('Item win rates reflect the games in which an item was acquired. Game length and being ahead affect those rates; the highest WR alone does not identify the best purchase.')


def show_item(item, version):
    st.image(item_image(item['id'], version), width=40)
    st.markdown(f"**{item['name']}**")
    if 'win_rate_pct' in item and 'games' in item:
        small = ' · small sample' if item['games'] < 30 else ''
        st.caption(f"{item['win_rate_pct']:.1f}% item WR · {item['games']:,} games{small}")


def render_build_details(result, version):
    build = result.get('build') or {}
    core = build.get('core') or result.get('items') or []
    st.markdown('##### Runes')
    for col, key, label in zip(st.columns(3), ['primary', 'secondary', 'shards'],
                               ['Primary runes', 'Secondary runes', 'Stat shards']):
        with col:
            st.markdown(f'**{label}**')
            choices = build.get('runes', {}).get(key, [])
            if choices:
                st.dataframe(pd.DataFrame([{'Icon': r['image'], 'Choice': r['name']} for r in choices]),
                             column_config={'Icon': st.column_config.ImageColumn('')}, hide_index=True)
            else:
                st.caption('Selected choices unavailable in this source response.')
    st.caption('Highlighted rune choices from the same matchup page. These are the source’s displayed choices, not a separately optimized full-team rune page.')

    st.markdown('##### Core build')
    if core:
        for col, item in zip(st.columns(len(core)), core):
            with col:
                show_item(item, version)
    else:
        st.caption('Core build unavailable in this source response.')
    st.markdown('##### Finish your build')
    for col, label in zip(st.columns(3), ['Item 4', 'Item 5', 'Item 6']):
        with col:
            st.markdown(f'**{label} options**')
            options = build.get('item_options', {}).get(label, [])
            if not options:
                st.caption('No options reported for this matchup and rank.')
            for item in options:
                show_item(item, version)
    st.caption('Alternatives follow the source’s item slots, including boots. Choose an option per slot; these are not three extra items to buy together. Item WR reflects games reaching that purchase and is not the matchup win rate.')
