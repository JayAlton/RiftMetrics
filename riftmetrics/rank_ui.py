import streamlit as st
from riftmetrics.live_stats import RANKS
from riftmetrics.rank_groups import INDIVIDUAL_RANKS, RANK_PRESETS


def select_rank_scope():
    selected = st.sidebar.selectbox('External data rank',
        list(RANKS) + list(RANK_PRESETS) + ['Custom rank group'], key='draft_stats_rank',
        help='Choose one rank, a preset group, or a custom group of individual ranks.')
    if selected == 'Custom rank group':
        return tuple(st.sidebar.multiselect('Ranks to combine', INDIVIDUAL_RANKS,
                     default=['Iron', 'Bronze'], key='draft_custom_ranks'))
    return RANK_PRESETS.get(selected, selected)
