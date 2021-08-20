from __future__ import annotations

import re
from datetime import datetime
from typing import Callable, List


def fromdate(func) -> Callable:
    """A decorator for extracting version power from date format"""

    def wrapper(string: str) -> datetime | int:
        try:
            version = datetime.strptime(string, "%Y.%m.%d")
        except ValueError:
            version = func(string)
        return version

    return wrapper


def extract_version(string: str) -> str:
    """Extract a string in format of <x.x.x> where x is numeric
    form any string

    Args:
        string (str): Any string

    Returns:
        int: calculate_version
    """
    version: str = ""
    match = re.search(r"[\d.][\d.][\d.]+", string)

    if match:
        version = match.group()

    return version


@fromdate
def get_version_power(string: str) -> int:
    """Calculate a version string by multiplexing values

    Args:
        string (str): a string in format of <x.x.x> where x is numeric

    Returns:
        int: a sum of multiplexed values
    """
    version: List[int] = []

    for index, part in enumerate(string.split("."), start=1):
        if index == 1:
            version.append(int(part) * 100)
        elif index == 2:
            version.append(int(part) * 10)
        else:
            version.append(int(part))

    return sum(version)
