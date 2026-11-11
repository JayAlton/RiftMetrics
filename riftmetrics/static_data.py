"""Public Riot Data Dragon assets for RiftMetrics (no Riot API key needed)."""
from functools import lru_cache
from urllib.parse import quote

import requests

BASE = "https://ddragon.leagueoflegends.com"
FALLBACK_VERSION = "16.22.1"
# Match-V5 championName doesn't always equal Data Dragon's image filename.
ALIASES = {
    "Wukong": "MonkeyKing", "MonkeyKing": "MonkeyKing",
    "Cho'Gath": "Chogath", "ChoGath": "Chogath", "Chogath": "Chogath",
    "Kha'Zix": "Khazix", "LeBlanc": "Leblanc", "Nunu & Willump": "Nunu",
    "Renata Glasc": "Renata", "Miss Fortune": "MissFortune",
    "Kai'Sa": "Kaisa", "Kog'Maw": "KogMaw", "Rek'Sai": "RekSai",
    "Vel'Koz": "Velkoz", "Dr. Mundo": "DrMundo", "Jarvan IV": "JarvanIV",
    "Twisted Fate": "TwistedFate", "Aurelion Sol": "AurelionSol",
}


@lru_cache(maxsize=1)
def get_version():
    """Latest Data Dragon version, or a safe fallback if offline."""
    try:
        response = requests.get(f"{BASE}/api/versions.json", timeout=4)
        response.raise_for_status()
        versions = response.json()
        if isinstance(versions, list) and versions:
            return versions[0]
    except (requests.RequestException, ValueError):
        pass
    return FALLBACK_VERSION


@lru_cache(maxsize=2)
def champion_catalog(version):
    """Map champion names and normalized aliases to the correct image ID."""
    try:
        response = requests.get(f"{BASE}/cdn/{version}/data/en_US/champion.json", timeout=5)
        response.raise_for_status()
        entries = response.json()["data"].values()
        catalog = {}
        for champion in entries:
            image_id = champion["image"]["full"].removesuffix(".png")
            for name in (champion["id"], champion["name"], image_id):
                catalog[name.casefold()] = image_id
        return catalog
    except (requests.RequestException, KeyError, TypeError, ValueError):
        return {}


def champion_image(name, version=None):
    """Return a Data Dragon champion image URL, or None for missing names."""
    if not name or not str(name).strip():
        return None
    version = version or get_version()
    name = str(name).strip()
    image_id = champion_catalog(version).get(name.casefold())
    image_id = image_id or ALIASES.get(name) or name.replace(" ", "")
    return f"{BASE}/cdn/{quote(version)}/img/champion/{quote(image_id)}.png"


def item_image(item_id, version=None):
    """Return image URL for an occupied item slot; empty slots are omitted."""
    try:
        item_id = int(item_id)
    except (TypeError, ValueError):
        return None
    if item_id <= 0:
        return None
    version = version or get_version()
    return f"{BASE}/cdn/{quote(version)}/img/item/{item_id}.png"


def readable_champion(name):
    names = {"MonkeyKing": "Wukong", "Chogath": "Cho'Gath", "Khazix": "Kha'Zix",
             "Leblanc": "LeBlanc", "MissFortune": "Miss Fortune", "Kaisa": "Kai'Sa"}
    return names.get(name, name or "Unknown")


QUEUE_NAMES = {400: "Normal Draft", 420: "Ranked Solo/Duo"}
ROLE_NAMES = {"TOP": "Top", "JUNGLE": "Jungle", "MIDDLE": "Mid", "BOTTOM": "ADC", "UTILITY": "Support"}
