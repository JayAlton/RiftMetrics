"""Read detailed match statistics from Riot Match-V5 JSON (no API calls)."""
import json
import os
from datetime import datetime, timezone

from riftmetrics.champions import normalize_champion_name

POSITIONS = ('TOP', 'JUNGLE', 'MIDDLE', 'BOTTOM', 'UTILITY')


def _name(participant):
    return normalize_champion_name(participant.get('championName', 'Unknown'))


def _position(participant):
    return (participant.get('teamPosition') or participant.get('individualPosition') or 'UNKNOWN').upper()


def _team_roster(participants):
    """Preserve unknown/duplicate positions rather than silently discarding picks."""
    roster = {role: None for role in POSITIONS}
    unassigned = []
    for p in participants:
        role = _position(p)
        name = _name(p)
        if role in roster and roster[role] is None:
            roster[role] = name
        else:
            unassigned.append({'champion': name, 'reported_position': role})
    return {'by_role': roster, 'unassigned': unassigned,
            'all_champions': [_name(p) for p in participants]}


def _objective_count(team, name):
    data = team.get('objectives', {}).get(name)
    return data.get('kills') if isinstance(data, dict) else None


def parse_match(match, *, puuid=None, game_name=None, tag_line=None):
    """Return parsed data for a player. Supply PUUID or Riot ID for identification."""
    info = match['info']
    participants = info['participants']
    if puuid:
        own = [p for p in participants if p.get('puuid') == puuid]
    else:
        if not game_name or not tag_line:
            raise ValueError('Provide puuid or both game_name and tag_line.')
        own = [p for p in participants
               if (p.get('riotIdGameName') or '').casefold() == game_name.casefold()
               and (p.get('riotIdTagline') or '').casefold() == tag_line.casefold()]
    if len(own) != 1:
        raise ValueError('Could not uniquely identify your participant in match JSON; use your PUUID.')
    player = own[0]
    team_id = player['teamId']
    allies = [p for p in participants if p['teamId'] == team_id]
    enemies = [p for p in participants if p['teamId'] != team_id]
    team = next((t for t in info.get('teams', []) if t.get('teamId') == team_id), {})
    opponent_team = next((t for t in info.get('teams', []) if t.get('teamId') != team_id), {})
    duration = info.get('gameDuration', 0)
    minutes = duration / 60 if duration else 0
    cs = player.get('totalMinionsKilled', 0) + player.get('neutralMinionsKilled', 0)
    kills = player.get('kills', 0)
    deaths = player.get('deaths', 0)
    assists = player.get('assists', 0)
    styles = player.get('perks', {}).get('styles', [])
    primary = styles[0] if styles else {}
    secondary = styles[1] if len(styles) > 1 else {}
    challenges = player.get('challenges', {})
    enemy_roster = _team_roster(enemies)
    ally_roster = _team_roster(allies)
    start = info.get('gameStartTimestamp')
    return {
        'match_id': match.get('metadata', {}).get('matchId'),
        'queue_id': info.get('queueId'),
        'played_at_utc': datetime.fromtimestamp(start / 1000, timezone.utc).isoformat() if start else None,
        'champion': _name(player),
        'position': _position(player),
        'win': bool(player.get('win', False)),
        'duration_seconds': duration,
        'duration_minutes': round(minutes, 2),
        'kills': kills, 'deaths': deaths, 'assists': assists,
        'kda': round((kills + assists) / max(1, deaths), 2),
        'cs': cs, 'cs_per_min': round(cs / minutes, 2) if minutes else None,
        'gold': player.get('goldEarned'),
        'gold_per_min': round(player['goldEarned'] / minutes, 2) if minutes and 'goldEarned' in player else None,
        'damage_to_champions': player.get('totalDamageDealtToChampions'),
        'damage_per_min': round(player['totalDamageDealtToChampions'] / minutes, 2) if minutes and 'totalDamageDealtToChampions' in player else None,
        'vision_score': player.get('visionScore'),
        'vision_per_min': round(player['visionScore'] / minutes, 2) if minutes and 'visionScore' in player else None,
        'wards_placed': player.get('wardsPlaced'),
        'wards_killed': player.get('wardsKilled'),
        'control_wards_purchased': player.get('visionWardsBoughtInGame'),
        'ally_draft': ally_roster,
        'enemy_draft': enemy_roster,
        'enemy_jungler': enemy_roster['by_role']['JUNGLE'],
        'items_at_game_end': [player.get(f'item{i}', 0) for i in range(7)],
        'summoner_spell_ids': [player.get('summoner1Id'), player.get('summoner2Id')],
        'runes': {
            'keystone_id': (primary.get('selections') or [{}])[0].get('perk'),
            'primary_style_id': primary.get('style'),
            'primary_perk_ids': [s.get('perk') for s in primary.get('selections', [])],
            'secondary_style_id': secondary.get('style'),
            'secondary_perk_ids': [s.get('perk') for s in secondary.get('selections', [])],
            'stat_shards': player.get('perks', {}).get('statPerks', {}),
        },
        'team_objectives': {k: _objective_count(team, k) for k in ('dragon', 'horde', 'riftHerald', 'baron', 'atakhan', 'tower')},
        'enemy_team_objectives': {k: _objective_count(opponent_team, k) for k in ('dragon', 'horde', 'riftHerald', 'baron', 'atakhan', 'tower')},
        'personal_objectives': {
            'dragon_kills': player.get('dragonKills'),
            'baron_kills': player.get('baronKills'),
            'dragon_takedowns': challenges.get('dragonTakedowns'),
            'baron_takedowns': challenges.get('baronTakedowns'),
            'rift_herald_takedowns': challenges.get('riftHeraldTakedowns'),
        },
        'missing_manual_fields': ['enemy_comp_style', 'ally_comp_style', 'jungle_matchup_rating',
                                  'team_matchup_rating', 'build_notes', 'what_worked_and_mistakes'],
    }


def main():
    """Inspect one existing draft match without modifying SQLite."""
    from dotenv import load_dotenv
    from riftmetrics.storage import connect
    load_dotenv()
    with connect() as db:
        row = db.execute('SELECT raw_json FROM matches WHERE queue_id=400 ORDER BY played_at DESC LIMIT 1').fetchone()
    if not row:
        raise SystemExit('No normal draft matches found. Import queue 400 first.')
    result = parse_match(json.loads(row[0]),
                         game_name=os.getenv('RIOT_GAME_NAME', 'Destro493'),
                         tag_line=os.getenv('RIOT_TAG_LINE', 'NA1'))
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
