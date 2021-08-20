"""Dependency software version check logic"""
from __future__ import annotations

from tqdm import tqdm

from vpnmupd.core import Dependency


def start_dependency_download_thread(dependency: Dependency) -> None:
    if dependency.acrhive:
        filename = dependency.acrhive.filename
        location = dependency.acrhive.location
    else:
        filename = dependency.executable.filename
        location = dependency.executable.location

    with tqdm(
        total=dependency.content_length,
        desc=filename,
        postfix=dependency.github_release.version,
    ) as pbar:
        for _ in range(dependency.content_length):
            pbar.update(len(location.read_bytes()))

    for result in dependency.results:
        result.check_returncode()
