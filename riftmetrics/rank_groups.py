"""Non-overlapping rank selections for within-source aggregation."""
INDIVIDUAL_RANKS = ('Iron', 'Bronze', 'Silver', 'Gold', 'Platinum', 'Emerald',
                    'Diamond', 'Master', 'Grandmaster', 'Challenger')
RANK_PRESETS = {'Iron–Bronze': ('Iron', 'Bronze'),
                'Iron–Silver': ('Iron', 'Bronze', 'Silver'),
                'Bronze–Gold': ('Bronze', 'Silver', 'Gold'),
                'Gold–Platinum': ('Gold', 'Platinum'),
                'Emerald–Diamond': ('Emerald', 'Diamond')}


def resolve_ranks(selection):
    if isinstance(selection, str):
        return RANK_PRESETS.get(selection, (selection,))
    ranks = tuple(dict.fromkeys(selection))
    if len(ranks) > 1 and any(r not in INDIVIDUAL_RANKS for r in ranks):
        raise ValueError('Custom groups must contain individual ranks, not overlapping rank-and-above filters.')
    return tuple(r for r in INDIVIDUAL_RANKS if r in ranks) if len(ranks) > 1 else ranks


def rank_label(selection):
    return ' + '.join(resolve_ranks(selection))
