"""Bounded public-page retrieval with persistent cache; no browser or private APIs."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
import requests
from riftmetrics.draft_scoring import norm
from riftmetrics.rank_groups import resolve_ranks

CACHE = Path(__file__).resolve().parents[1] / 'data' / 'source_cache'
TTL = 6 * 3600
SOURCES = ('OP.GG', 'Lolalytics')
RANKS = {
    'Iron': 'iron', 'Bronze': 'bronze', 'Silver': 'silver', 'Gold': 'gold',
    'Platinum': 'platinum', 'Emerald': 'emerald', 'Diamond': 'diamond',
    'Master': 'master', 'Grandmaster': 'grandmaster', 'Challenger': 'challenger',
    'Gold+': 'gold_plus', 'Platinum+': 'platinum_plus', 'Emerald+': 'emerald_plus',
    'Diamond+': 'diamond_plus', 'Master+': 'master_plus', 'All ranks': 'all',
}
LOL_RANK_LABELS = {'Grandmaster': 'G.MASTER', 'All ranks': 'ALL RANKS'}


def slug(champion):
    aliases = {'monkeyking': 'wukong', 'nunu&willump': 'nunu', 'renataglasc': 'renata'}
    key = norm(champion).replace('.', '')
    return re.sub('[^a-z0-9]', '', aliases.get(key, key))


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.hidden = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def text(html):
    parser = VisibleText()
    parser.feed(html)
    return re.sub(r'\s+', ' ', ' '.join(parser.parts)).strip()


def page(source, champion, enemy, rank='Iron'):
    c, e = slug(champion), slug(enemy)
    tier = RANKS[rank]
    if source == 'OP.GG':
        return f'https://op.gg/lol/champions/{c}/counters/jungle?region=global&tier={tier}'
    return f'https://lolalytics.com/lol/{c}/vs/{e}/build/?lane=jungle&tier={tier}'


def record(champion, enemy, rate, games, patch, source, url, rank='Iron'):
    if not 0 <= rate <= 100 or games < 1:
        raise ValueError('Invalid matchup rate/sample')
    return dict(champion=champion, enemy_jungler=enemy, win_rate_pct=rate,
                sample_size=games, source=source, patch=patch, rank=rank,
                region='All regions', queue='420', role='JUNGLE',
                updated_at=datetime.now(timezone.utc).date().isoformat(),
                expected_win_rate_pct='', source_url=url)


def parse_opgg(html, champion, enemy, url, rank='Iron'):
    visible = text(html)
    heading = re.search(r'([\w\s\'&.]+) Counters for Jungle, Patch (\d+\.\d+)', visible)
    if not heading or not slug(heading[1]).endswith(slug(champion)):
        raise ValueError('Jungle counter heading missing or wrong champion')
    selected = re.search(r'<select\b[^>]*id="selectTier"[^>]*>(.*?)</select>', html, re.S)
    if not selected:
        raise ValueError('Source rank selector missing')
    options = re.findall(r'<option\b([^>]*)>', selected[1])
    chosen = [dict(re.findall(r'(\w+)="([^"]*)"', attrs)).get('value') for attrs in options if re.search(r'\bselected(?:=|\s|$)', attrs)]
    if chosen != [RANKS[rank]]:
        raise ValueError(f'Source did not return requested rank: {rank}')
    # This table is the current champion's WR, not the opponent's WR.
    table = visible.split('Search a champion Win rate Games', 1)
    if len(table) != 2:
        raise ValueError('Counter table missing')
    for name, rate, games in re.findall(r"([A-Za-z'’&. ]+?)\s+(\d+(?:\.\d+)?)%\s+([\d,]+)", table[1]):
        if slug(name.strip()) == slug(enemy):
            return record(champion, enemy, float(rate), int(games.replace(',', '')), heading[2], 'OP.GG', url, rank), []
    raise ValueError('Enemy matchup absent from counter table')


class Images(HTMLParser):
    def __init__(self): super().__init__(); self.items = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        item = re.search(r'/item64/(\d+)\.', attrs.get('src', ''))
        if tag == 'img' and item and attrs.get('alt'):
            self.items.append(dict(id=int(item[1]), name=attrs['alt']))


class RuneImages(HTMLParser):
    """Only highlighted choices from the source rune summary."""
    def __init__(self): super().__init__(); self.runes = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        match = re.search(r'/(rune68|statmod32)/(\d+)\.', attrs.get('src', ''))
        if tag != 'img' or not match or 'grayscale' in attrs.get('class', ''):
            return
        shards = {5001: 'Health scaling', 5002: 'Armor', 5003: 'Magic resist',
                  5005: 'Attack speed', 5007: 'Ability haste', 5008: 'Adaptive force',
                  5010: 'Move speed', 5011: 'Health', 5013: 'Tenacity and slow resist'}
        ident = int(match[2])
        name = shards.get(ident, f'Stat shard {ident}') if match[1] == 'statmod32' else attrs.get('alt')
        if name:
            self.runes.append(dict(id=ident, name=name, image=attrs['src']))


def parse_item_options(section):
    matches = list(re.finditer(r'<img\b[^>]*>', section))
    items = []
    for index, match in enumerate(matches):
        images = Images(); images.feed(match[0])
        if not images.items:
            continue
        item = images.items[0]
        end = matches[index + 1].start() if index + 1 < len(matches) else len(section)
        stats = re.search(r'(\d+(?:\.\d+)?)\s*%\s*(?:Win Rate\s*)?([\d,]+)', text(section[match.end():end]))
        if stats:
            rate, games = float(stats[1]), int(stats[2].replace(',', ''))
            if 0 <= rate <= 100 and games > 0:
                item.update(win_rate_pct=rate, games=games)
        items.append(item)
    return items


def parse_build(html):
    """Parse the visible matchup summary, excluding scripts and unrelated tables."""
    html = re.sub(r'<(script|style)\b[^>]*>.*?</\1>', '', html, flags=re.S | re.I)
    html = re.sub(r'<!--.*?-->', '', html, flags=re.S)
    build = dict(core=[], item_options={}, runes={'primary': [], 'secondary': [], 'shards': []})
    boundaries = [('Core Build', 'Item 4'), ('Item 4', 'Item 5'),
                  ('Item 5', 'Item 6'), ('Item 6', 'Summoner Spells')]
    for label, end in boundaries:
        end_pattern = r'Summoner(?:\s|<[^>]*>)*Spells' if end == 'Summoner Spells' else re.escape(end)
        section = re.search(re.escape(label) + r'(.*?)' + end_pattern, html, re.S)
        if section:
            items = parse_item_options(section[1])
            if label == 'Core Build':
                build['core'] = items[:3]
            else:
                build['item_options'][label] = items
    for name, start, end in [('primary', 'Primary Runes', 'Secondary'),
                             ('secondary', 'Secondary', 'Stat Mods'),
                             ('shards', 'Stat Mods', 'Starting Items')]:
        section = re.search(re.escape(start) + r'(.*?)' + re.escape(end), html, re.S)
        if section:
            parser = RuneImages(); parser.feed(section[1])
            build['runes'][name] = parser.runes
    # An incomplete highlight set is unavailable, rather than a guessed rune page.
    for name, count in [('primary', 4), ('secondary', 2), ('shards', 3)]:
        if len(build['runes'][name]) != count:
            build['runes'][name] = []
    return build


def parse_lolalytics(html, champion, enemy, url, rank='Iron'):
    visible = text(html)
    heading = re.search(r'([\w\s\'&.]+) jungle vs ([\w\s\'&.]+) jungle Build & Runes', visible)
    patch = re.search(r'\bPatch\s+(\d+\.\d+)', visible)
    if not heading or not patch or not slug(heading[1]).endswith(slug(champion)) or slug(heading[2]) != slug(enemy):
        raise ValueError('Jungle matchup identity missing')
    if not re.search(r'\b' + re.escape(LOL_RANK_LABELS.get(rank, rank.upper())) + r'\s+Patch\s+\d+\.\d+', visible):
        raise ValueError(f'Source did not return requested rank: {rank}')
    matchup = re.search(r'wins against\s+.+?\s+(\d+(?:\.\d+)?)% of the time', visible)
    sample = re.search(r'(\d+(?:\.\d+)?)\s*%\s+Win Rate\s+([\d,]+)\s+Games', visible)
    if not matchup or not sample or float(matchup[1]) != float(sample[1]):
        raise ValueError('Matchup summary missing or inconsistent')
    # Only the source's core-build section, never unrelated item tables.
    section = re.search(r'Core Build(.*?)Item 4', html, re.S)
    items = []
    if section:
        images = Images(); images.feed(section[1]); items = images.items
    row = record(champion, enemy, float(matchup[1]), int(sample[2].replace(',', '')), patch[1], 'Lolalytics', url, rank)
    return row, items[:3]


def fetch_one(source, champion, enemy, cache_dir=CACHE, force=False, rank='Iron'):
    url = page(source, champion, enemy, rank)
    cache_dir = Path(cache_dir)
    path = cache_dir / (sha256(url.encode()).hexdigest() + '.json')
    cached = None
    try:
        cached = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        pass
    now = time.time()
    fresh = cached and now - cached.get('fetched_at', 0) < TTL
    retry_due = not cached or now - cached.get('attempted_at', 0) > 300
    result = cached or {}
    if force or (not fresh and retry_due):
        try:
            response = requests.get(url, timeout=(3, 5), headers={'User-Agent': 'RiftMetrics/0.1 (personal League analytics)'})
            response.raise_for_status()
            # Store public HTML too: OP.GG contains every enemy matchup for this champion.
            parser = parse_opgg if source == 'OP.GG' else parse_lolalytics
            parser(response.text, champion, enemy, url, rank)
            result = dict(html=response.text, fetched_at=now, attempted_at=now)
        except (requests.RequestException, ValueError) as exc:
            result = dict(result, attempted_at=now, error=f'{source}: {type(exc).__name__}: {str(exc)[:160]}')
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix('.tmp')
            temporary.write_text(json.dumps(result), encoding='utf-8')
            temporary.replace(path)
        except OSError:
            pass
    if not result.get('html'):
        return dict(source=source, champion=champion, requested_rank=rank, error=result.get('error', 'No source data'), record=None, items=[])
    try:
        parser = parse_opgg if source == 'OP.GG' else parse_lolalytics
        row, items = parser(result['html'], champion, enemy, url, rank)
        row['updated_at'] = datetime.fromtimestamp(result['fetched_at'], timezone.utc).date().isoformat()
        stale = now - result['fetched_at'] >= TTL
        build = parse_build(result['html']) if source == 'Lolalytics' else None
        return dict(source=source, champion=champion, requested_rank=rank, record=row, items=items, build=build,
                    fetched_at=result['fetched_at'], stale=stale,
                    error=result.get('error'))
    except ValueError as exc:
        return dict(source=source, champion=champion, requested_rank=rank, error=f'{source}: {exc}', record=None, items=[])


def fetch_pool(pool, enemy, sources=SOURCES, cache_dir=CACHE, force=False, rank='Iron'):
    jobs = [(source, champion, tier) for champion in dict.fromkeys(pool)
            for source in sources for tier in resolve_ranks(rank)]
    def run(job): return fetch_one(job[0], job[1], enemy, cache_dir, force, job[2])
    with ThreadPoolExecutor(max_workers=6) as executor:
        return list(executor.map(run, jobs))
