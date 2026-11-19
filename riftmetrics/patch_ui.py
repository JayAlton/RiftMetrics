"""Select an external-statistics patch independently of portrait assets."""
import re

import requests
import streamlit as st

from riftmetrics.static_data import BASE, FALLBACK_VERSION


@st.cache_data(ttl=3600, show_spinner=False)
def available_patches():
    try:
        response = requests.get(f'{BASE}/api/versions.json', timeout=4)
        response.raise_for_status()
        versions = response.json()
        if not isinstance(versions, list):
            raise ValueError('Invalid version list')
    except (requests.RequestException, ValueError):
        versions = [FALLBACK_VERSION]
    patches = list(dict.fromkeys('.'.join(v.split('.')[:2]) for v in versions
                                if isinstance(v, str) and re.fullmatch(r'\d+\.\d+\.\d+', v)))
    return patches[:12] or ['.'.join(FALLBACK_VERSION.split('.')[:2])]


def select_stats_patch():
    options = ['Latest'] + available_patches()
    # A saved choice remains selectable if the version feed changes or is offline.
    previous = st.session_state.get('stats_patch')
    if previous and previous not in options:
        options.append(previous)
    selected = st.sidebar.selectbox('Statistics patch', options, key='stats_patch',
                                   help='Used for draft matchups, items, runes, and bans. Select the previous patch when a new patch has too few games.')
    st.sidebar.caption('Choose an older patch for more data. Sources may only retain a limited patch history.')
    return None if selected == 'Latest' else selected
