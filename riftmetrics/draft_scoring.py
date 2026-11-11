"""Transparent, sample-size-aware RiftMetrics jungle draft recommendations."""
import csv
from pathlib import Path

DEFAULT_POOL = ["Warwick", "Kayn", "Wukong", "Xin Zhao", "Lillia", "Master Yi", "Jax", "Ekko", "Diana", "Rammus"]


def norm(value):
    return str(value or "").strip().casefold().replace("'", "").replace(" ", "")


def load_external_priors(path):
    """Return {(champion, enemy_jungler): prior} from a user-supplied CSV; ignore bad rows."""
    result = {}
    path = Path(path)
    if not path.is_file():
        return result
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            try:
                champion, enemy = norm(row.get("champion")), norm(row.get("enemy_jungler"))
                pct = float(row["win_rate_pct"])
                sample = int(row["sample_size"])
                if not champion or not enemy or not 0 <= pct <= 100 or sample < 1:
                    continue
                result[(champion, enemy)] = {
                    "rate": pct / 100, "sample": sample,
                    "source": (row.get("source") or "Manual").strip(),
                    "patch": (row.get("patch") or "").strip(),
                    "updated_at": (row.get("updated_at") or "").strip(),
                }
            except (ValueError, TypeError, KeyError):
                continue
    return result


def score_pool(rows, pool, enemy_jungler=None, priors=None, queue_id=400):
    """Score historical JUNGLE performance only; does not imply global win rate.

    Personal champion win rate is smoothed toward 50% with 10 pseudo-games.
    Matchup is smoothed toward that champion's baseline with 8 pseudo-games.
    External prior can contribute up to 30% of the matchup component, only
    when explicitly supplied, and is not treated as a Riot API statistic.
    """
    priors = priors or {}
    enemy_key = norm(enemy_jungler)
    eligible = []
    for row in rows:
        role = str(row.get("role") or "").upper()
        if role != "JUNGLE" or int(row.get("queue_id") or 0) != queue_id:
            continue
        eligible.append(row)
    scores = []
    for champ in dict.fromkeys(pool):
        games = [r for r in eligible if norm(r.get("champion")) == norm(champ)]
        n = len(games)
        wins = sum(bool(r.get("win")) for r in games)
        personal_rate = wins / n if n else None
        baseline = (wins + 5) / (n + 10)
        matchups = [r for r in games if enemy_key and norm(r.get("enemy_jungler")) == enemy_key]
        mn = len(matchups)
        mw = sum(bool(r.get("win")) for r in matchups)
        estimated = (mw + 8 * baseline) / (mn + 8)
        prior = priors.get((norm(champ), enemy_key)) if enemy_key else None
        if prior:
            # External percentages are contextual third-party data; never overwhelm personal sample.
            weight = min(.30, .30 * (8 / (8 + mn)))
            estimated = (1 - weight) * estimated + weight * prior["rate"]
        # A weak uncertainty penalty favors champions with enough games to assess.
        confidence = min(1.0, n / 20)
        score = .65 * estimated + .35 * baseline - .02 * (1 - confidence)
        scores.append({
            "champion": champ, "games": n, "wins": wins,
            "personal_wr": personal_rate, "matchup_games": mn,
            "matchup_wins": mw, "matchup_wr": mw / mn if mn else None,
            "external": prior, "estimated_rate": estimated,
            "score": score, "confidence": confidence,
        })
    return sorted(scores, key=lambda s: (s["score"], s["games"]), reverse=True)
