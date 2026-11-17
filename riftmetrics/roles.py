"""Role names and starter champion pools shared by draft pages."""
ROLES = {
    'TOP': ('Top', 'top', ['Garen', 'Jax', 'Warwick']),
    'JUNGLE': ('Jungle', 'jungle', ['Warwick', 'Kayn', 'Wukong', 'Xin Zhao', 'Lillia', 'Master Yi', 'Jax']),
    'MIDDLE': ('Mid', 'middle', ['Ahri', 'Annie', 'Lux', 'Sylas', 'Yone']),
    'BOTTOM': ('ADC', 'bottom', ['Caitlyn', 'Jinx', 'Ezreal', 'Draven', 'Twitch', 'Miss Fortune']),
    'UTILITY': ('Support', 'support', ['Leona', 'Nautilus', 'Lulu', 'Lux', 'Thresh']),
}


def source_lane(role, source='Lolalytics'):
    """Use the user's selected role; never infer a lane from a champion."""
    if role not in ROLES:
        raise ValueError(f'Choose a supported role before importing statistics: {role}')
    lane = ROLES[role][1]
    return {'MIDDLE': 'mid', 'BOTTOM': 'adc'}.get(role, lane) if source == 'OP.GG' else lane
