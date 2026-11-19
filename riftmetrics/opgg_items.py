"""Validated public OP.GG item tables with a bounded disk cache."""
from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time

import requests

from riftmetrics.live_stats import CACHE, TTL, RANKS, page, slug, text, validate_patch
from riftmetrics.roles import ROLES


class ItemTables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.section = None
        self.rows = []
        self.cells = None
        self.cell = None
        self.items = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ('script', 'style'):
            self.hidden += 1
        if self.hidden:
            return
        if tag == 'tr':
            self.cells, self.items = [], []
        elif tag == 'td' and self.cells is not None:
            self.cell = []
        elif tag == 'img' and self.cell is not None:
            match = re.search(r'/item/(\d+)\.png', attrs.get('src', ''))
            if match:
                self.items.append(dict(id=int(match[1]), name=attrs.get('alt', '')))

    def handle_data(self, data):
        if self.hidden:
            return
        if data.strip() in ('Core builds', 'Boots', 'Starter items', 'Items') and self.cells is None:
            self.section = data.strip()
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)
        if self.hidden:
            return
        if tag == 'td' and self.cell is not None:
            self.cells.append(' '.join(self.cell))
            self.cell = None
        elif tag == 'tr':
            if self.section and self.cells and len(self.cells) == 3 and self.items:
                if len(self.items) == 1 and not self.items[0]['name']:
                    self.items[0]['name'] = self.cells[0].strip()
                pick = re.search(r'(\d+(?:\.\d+)?)\s*%', self.cells[1])
                games = re.search(r'([\d,]+)\s*Games', self.cells[1])
                win = re.search(r'(\d+(?:\.\d+)?)\s*%', self.cells[2])
                if pick and games and win:
                    rate, popularity, count = float(win[1]), float(pick[1]), int(games[1].replace(',', ''))
                    if 0 <= rate <= 100 and 0 <= popularity <= 100 and count > 0:
                        self.rows.append(dict(section=self.section, items=self.items,
                                              win_rate_pct=rate, pick_rate_pct=popularity, games=count))
            self.cells, self.cell = None, None


def parse_items(html, champion, role, rank):
    heading = re.search(r'<h1\b[^>]*>(.*?)</h1>', html, re.S)
    identity = text(heading[1]) if heading else ''
    match = re.fullmatch(r'(.+?) Items for (.+?), Patch (\d+\.\d+)', identity, re.I)
    lanes = {'MIDDLE': ('mid', 'middle'), 'BOTTOM': ('adc', 'bottom')}
    if not match or slug(match[1]) != slug(champion) or match[2].lower() not in lanes.get(role, (ROLES[role][1],)):
        raise ValueError('OP.GG item champion or role does not match the request.')
    selector = re.search(r'<select\b[^>]*id="selectTier"[^>]*>(.*?)</select>', html, re.S)
    chosen = re.findall(r'<option\b([^>]*)>', selector[1]) if selector else []
    selected = [dict(re.findall(r'(\w+)="([^"]*)"', a)).get('value') for a in chosen if re.search(r'\bselected(?:=|\s|$)', a)]
    if selected != [RANKS[rank]]:
        raise ValueError('OP.GG did not return the requested item rank.')
    parser = ItemTables()
    parser.feed(html)
    if not parser.rows:
        raise ValueError('OP.GG item tables unavailable in this response.')
    return dict(champion=champion, role=role, rank=rank, patch=match[3], rows=parser.rows)


def fetch_items(champion, role='JUNGLE', rank='Iron', force=False, cache_dir=CACHE, patch=None):
    url = page('OP.GG', champion, '', rank, role, patch).replace('/counters/', '/items/')
    path = Path(cache_dir) / ('items_' + sha256(url.encode()).hexdigest() + '.json')
    try:
        cached = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        cached = {}
    data = cached.get('data') or {}
    if (data.get('role') != role or data.get('rank') != rank
            or slug(data.get('champion', '')) != slug(champion)
            or (patch and data.get('patch') != patch)):
        cached = {}
    now = time.time()
    error = None
    if force or now - cached.get('fetched_at', 0) >= TTL:
        try:
            response = requests.get(url, timeout=(3, 8), headers={'User-Agent': 'RiftMetrics/0.1 (personal League analytics)'})
            response.raise_for_status()
            parsed = parse_items(response.text, champion, role, rank)
            validate_patch(parsed, patch)
            cached = dict(data=parsed, fetched_at=now)
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                temporary = path.with_suffix('.tmp')
                temporary.write_text(json.dumps(cached), encoding='utf-8')
                temporary.replace(path)
            except OSError:
                pass
        except (requests.RequestException, ValueError) as exc:
            error = str(exc)
    return dict(data=cached.get('data'), source_url=url, error=error,
                stale=bool(cached) and now - cached.get('fetched_at', 0) >= TTL,
                checked_at=datetime.fromtimestamp(cached['fetched_at'], timezone.utc).isoformat() if cached.get('fetched_at') else None)
