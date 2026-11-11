"""Read-only analytics for historical RiftMetrics matches.

All analytics derive from the existing matches and match_details tables.
No network requests, database mutations, or external matchup assumptions.
"""
import json
from collections import defaultdict

OBJECTIVES = {
    'dragon': 'Dragons',
    'horde': 'Horde (Riot count)',
    'riftHerald': 'Heralds',
    'baron': 'Barons',
    'tower': 'Towers',
}


def objective_count(detail, side, objective):
    """Missing data stays missing, not a zero objective count."""
    val = (detail or {}).get(side, {}).get(objective)
    if isinstance(val, bool) or not isinstance(val, (float, int)):
        return None
    return max(0, int(val))


def objective_table(rows):
    """Aggregated objectives with separately reported number of available matches."""
    result = []
    for key, label in OBJECTIVES.items():
        values = []
        for detail in rows:
            own = objective_count(detail, 'team_objectives', key)
            enemy = objective_count(detail, 'enemy_team_objectives', key)
            if own is not None and enemy is not None:
                values.append((own, enemy))
        ally_total = sum(a for a, _ in values)
        enemy_total = sum(b for _, b in values)
        result.append({
            'key': key, 'objective': label, 'games_reported': len(values),
            'ally': ally_total, 'enemy': enemy_total,
            'control_pct': 100 * ally_total / (ally_total + enemy_total)
            if ally_total + enemy_total else None,
            'games_ahead': sum(a > b for a, b in values),
            'games_tied': sum(a == b for a, b in values),
            'games_behind': sum(a < b for a, b in values),
        })
    return result


def damage_to_objectives(raw_json, game_name, tag_line, champion=None):
    """Riot participant.damageDealtToObjectives, from saved raw Match-V5 JSON.

    This is *all objectives combined*, not just epic monsters. The Riot ID
    is preferred to avoid misattributing damage to a teammate.
    """
    try:
        match = json.loads(raw_json) if isinstance(raw_json, str) else raw_json
        players = match['info']['participants']
    except (ValueError, TypeError, KeyError):
        return None
    candidates = [p for p in players if
                  str(p.get('riotIdGameName') or '').casefold() == game_name.casefold()
                  and str(p.get('riotIdTagline') or '').casefold() == tag_line.casefold()]
    if len(candidates) != 1:
        # Refuse ambiguous identification rather than assigning somebody else's damage.
        return None
    value = candidates[0].get('damageDealtToObjectives')
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def matchup_table(records, prior_wins=5, prior_games=10):
    """Group by own champion AND enemy jungler with conservative WR estimates.

    Laplace-style prior: 50% win rate over prior_games equivalent games.
    Suitable for comparison, not calibrated win probabilities.
    """
    groups = defaultdict(list)
    for record in records:
        enemy = (record.get('details') or {}).get('enemy_jungler')
        if not enemy or enemy == 'Unknown':
            continue
        groups[(record['champion'], enemy)].append(bool(record['win']))
    output = []
    for (champion, enemy), wins_list in groups.items():
        games = len(wins_list)
        wins = sum(wins_list)
        output.append({
            'champion': champion,
            'enemy_jungler': enemy,
            'games': games,
            'wins': wins,
            'win_rate_pct': round(100 * wins / games, 1),
            'adjusted_pct': round(100 * (wins + prior_wins) / (games + prior_games), 1),
            'sample': 'Small sample' if games < 10 else '10+ games',
        })
    return sorted(output, key=lambda x: (-x['games'], -x['adjusted_pct'], x['champion']))


def champion_recommendations(records, enemy_jungler, role='JUNGLE', min_games=1):
    """Personal-history recommendations, shrunk toward a neutral 50% prior.

    Matchups with zero games contribute no advantage. No invented public-site stats.
    """
    eligible = [r for r in records if r.get('role') == role]
    per_champ = defaultdict(list)
    for row in eligible:
        per_champ[row['champion']].append(row)
    results = []
    for champion, games in per_champ.items():
        n = len(games)
        if n < min_games:
            continue
        wins = sum(bool(r['win']) for r in games)
        baseline = (wins + 5) / (n + 10)
        opposing = [r for r in games if (r.get('details') or {}).get('enemy_jungler') == enemy_jungler]
        matchup_n = len(opposing)
        matchup_wins = sum(bool(r['win']) for r in opposing)
        matchup_est = (matchup_wins + 5) / (matchup_n + 10)
        # More matchup-specific influence only when it has observations.
        influence = min(0.45, matchup_n / (matchup_n + 12))
        score = 100 * ((1 - influence) * baseline + influence * matchup_est)
        results.append({
            'champion': champion, 'games': n, 'wins': wins,
            'win_rate_pct': round(100 * wins / n, 1),
            'matchup_games': matchup_n,
            'matchup_wins': matchup_wins,
            'score': round(score, 1),
        })
    return sorted(results, key=lambda x: (-x['score'], -x['games']))
