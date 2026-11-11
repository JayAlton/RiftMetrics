
"""Utilities for normalizing champion names."""

CHAMPION_NAMES = {
    "MonkeyKing": "Wukong",
}


def normalize_champion_name(name: str) -> str:
    """Convert Riot's internal champion names to display names."""
    return CHAMPION_NAMES.get(name, name)
