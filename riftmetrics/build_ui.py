"""In-draft item paths and rune choices from the validated matchup page."""
import pandas as pd
import streamlit as st
from riftmetrics.static_data import item_image


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
