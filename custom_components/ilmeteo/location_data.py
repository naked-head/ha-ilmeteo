"""Lazy loader for the bundled iLMeteo location dataset.

The dataset is a gzipped JSON file shipped with the integration:
    data/locations.json.gz  ->  {"regions": {region: {province: {city: code}}}}

It is loaded once, off the event loop, and cached in memory.
"""
from __future__ import annotations

import gzip
import json
import os
from functools import lru_cache

_DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "locations.json.gz")


@lru_cache(maxsize=1)
def _load() -> dict:
    with gzip.open(_DATA_FILE, "rb") as f:
        return json.load(f)


def get_regions() -> list[str]:
    """Return the sorted list of region names."""
    return list(_load()["regions"].keys())


def get_provinces(region: str) -> list[str]:
    """Return the sorted province labels for a region."""
    return list(_load()["regions"].get(region, {}).keys())


def get_cities(region: str, province: str) -> dict[str, str]:
    """Return {city_name: code} for a region/province."""
    return _load()["regions"].get(region, {}).get(province, {})


def resolve_code(region: str, province: str, city: str) -> str | None:
    """Return the iLMeteo code for a given region/province/city."""
    return get_cities(region, province).get(city)
