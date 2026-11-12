"""Transparent, sample-size-aware RiftMetrics jungle draft recommendations."""

DEFAULT_POOL = ["Briar", "Darius", "Warwick", "Kayn", "Wukong", "Xin Zhao", "Lillia", "Master Yi", "Jax", "Ekko", "Diana", "Rammus"]


def norm(value):
    return str(value or "").strip().casefold().replace("'", "").replace(" ", "")


def load_external_priors(path, context=None):
    """Blend comparable source snapshots; never combine patches or ranked cohorts."""
    from riftmetrics.external_stats import read_records, blend_records
    return blend_records(read_records(path), context)


def score_pool(rows, pool, enemy_jungler=None, priors=None, queue_id=400, external_weight=.90, matchup_weight=.95, personal_max_weight=.15):
    """Blend external matchup evidence, limited personal history and neutral uncertainty.

    Personal history has a sample-scaled budget: at the default 15% maximum,
    fewer than 10 games contributes under 5%, 10 games contributes 5%, and
    30+ games contributes at most 15%. Missing evidence stays neutral.
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
        personal_matchup = (mw + 8 * baseline) / (mn + 8)
        weight = 0.0
        prior = priors.get((norm(champ), enemy_key)) if enemy_key else None
        if prior:
            weight = max(0.0, min(.90, external_weight)) * min(1.0, prior["sample"] / 1000)
        matchup_share = max(0.0, min(1.0, matchup_weight)) if enemy_key else 0.0
        external_share = matchup_share * weight
        # Limit all personal-WR paths, including head-to-head history, to one budget.
        sample_factor = (min(n, 10) / 10) ** 2 / 3 + 2 * min(max(n - 10, 0) / 20, 1) / 3
        personal_share = min(1 - external_share, max(0.0, min(.30, personal_max_weight)) * sample_factor)
        personal_signal = matchup_share * personal_matchup + (1 - matchup_share) * baseline
        estimated = .5 + weight * (prior["rate"] - .5) if prior else .5
        score_without_external = .5 + personal_share * (personal_signal - .5)
        score = score_without_external + external_share * (prior["rate"] - .5) if prior else score_without_external
        confidence = min(1.0, n / 30)
        scores.append({
            "champion": champ, "games": n, "wins": wins,
            "personal_wr": personal_rate, "matchup_games": mn,
            "matchup_wins": mw, "matchup_wr": mw / mn if mn else None,
            "external": prior, "external_weight": weight, "estimated_rate": estimated,
            "score": score, "confidence": confidence,
            "external_score_change": score - score_without_external,
            "overall_external_weight": external_share,
            "personal_weight": personal_share,
            "neutral_weight": 1 - external_share - personal_share,
        })
    return sorted(scores, key=lambda s: (s["score"], s["games"]), reverse=True)
