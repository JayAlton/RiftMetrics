"""Small Riot API client. Keeps API secrets out of logs and URLs."""
import time
from urllib.parse import quote
import requests

class RiotAPIError(Exception):
    pass

class RiotClient:
    def __init__(self, key, region='americas', platform='na1'):
        if not key or key == 'RGAPI_REPLACE_ME':
            raise RiotAPIError('Set RIOT_API_KEY in your local .env file first.')
        self.region = region
        self.platform = platform
        self.session = requests.Session()
        self.session.headers.update({'X-Riot-Token': key, 'User-Agent': 'RiftMetrics/0.1 (personal tracker)'})

    def get(self, routing, path, params=None):
        url = f'https://{routing}.api.riotgames.com{path}'
        for attempt in range(5):
            try:
                response = self.session.get(url, params=params, timeout=20)
            except requests.RequestException as exc:
                if attempt == 4:
                    raise RiotAPIError(f'Network request failed: {exc}') from exc
                time.sleep(2 ** attempt)
                continue
            if response.status_code == 429 or response.status_code >= 500:
                if attempt == 4:
                    raise RiotAPIError(f'Riot API returned HTTP {response.status_code}: {response.text[:200]}')
                retry = response.headers.get('Retry-After', '')
                delay = min(120, max(1, int(retry))) if retry.isdigit() else min(60, 2 ** attempt)
                time.sleep(delay)
                continue
            if not response.ok:
                if response.status_code == 403:
                    raise RiotAPIError('HTTP 403: API key missing, expired, or not authorized. Check Riot Developer Portal.')
                if response.status_code == 404:
                    raise RiotAPIError(f'HTTP 404: Resource not found: {path}')
                raise RiotAPIError(f'Riot API HTTP {response.status_code}: {response.text[:200]}')
            return response.json()
        raise RiotAPIError('Riot API retries exhausted')

    def account(self, name, tag):
        return self.get(self.region, f'/riot/account/v1/accounts/by-riot-id/{quote(name, safe="")}/{quote(tag, safe="")}')

    def match_ids(self, puuid, start=0, count=100, queue=420):
        return self.get(self.region, f'/lol/match/v5/matches/by-puuid/{quote(puuid, safe="")}/ids',
                        {'start': start, 'count': count, 'queue': queue})

    def match(self, match_id):
        return self.get(self.region, f'/lol/match/v5/matches/{quote(match_id, safe="")}')

    def ranked(self, puuid):
        return self.get(self.platform, f'/lol/league/v4/entries/by-puuid/{quote(puuid, safe="")}')
