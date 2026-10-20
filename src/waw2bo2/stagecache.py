"""Content-addressed cache for the whole map-staging step (per-map build speedup).

The build pipeline runs staging (the ``stage-bridge`` CLI) as a *child process*
that writes all of its output to disk under the build's ``stage`` directory; the
later link/audit steps read only those files. Because nothing crosses that
process boundary in memory, staging can be treated as a pure function of its
inputs: snapshot ``stage`` before the step, run it, and remember the files the
step added or changed. An identical rebuild -- same map, same tools, same
options -- then restores those files and skips the step entirely. This is the
expensive part (weapons + effects staging, measured ~5-10 min), so re-importing
the same map goes from minutes to seconds.

SAFETY. This cache is DISABLED unless ``WAW2BO2_STAGE_CACHE`` is set, because its
correctness depends entirely on the ``inputs`` key naming *every* thing the
staging output depends on. An incomplete key would restore stale files and
produce a silently-wrong map, so the feature must be proven with a timed build
plus an in-game load before it is relied on or turned on by default. ``SCHEMA``
(or deleting the cache directory) invalidates every entry; bump it whenever the
staging code changes in a way that changes its output -- the key cannot see the
Python package's own version.

Restores and stores COPY rather than hardlink, so the live build can never
mutate a cached file in place (correctness over the extra I/O); hardlinking is a
possible optimisation once the feature is validated.
"""
from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path

from .all2raw import cache_lock, key, publish, stamp, write_json

# Bump to invalidate every cached entry when staging output changes shape.
SCHEMA = 1

_FALSEY = {'', '0', 'false', 'no', 'off'}


def enabled() -> bool:
    """True only when the operator explicitly opts in via the environment."""
    return os.environ.get('WAW2BO2_STAGE_CACHE', '').strip().lower() not in _FALSEY


def snapshot(base: Path) -> dict[str, list[int]]:
    """``relpath -> [size, mtime_ns]`` for every file under ``base``.

    A missing directory yields ``{}`` so a first build (nothing staged yet) and
    a cache restore use the same code path.
    """
    base = Path(base)
    if not base.is_dir():
        return {}
    out: dict[str, list[int]] = {}
    for path in base.rglob('*'):
        if path.is_file():
            out[path.relative_to(base).as_posix()] = stamp(path)
    return out


def changed(before: dict[str, list[int]], after: dict[str, list[int]]) -> list[str]:
    """Files present in ``after`` that are new or whose stamp differs."""
    return sorted(name for name, st in after.items() if before.get(name) != st)


class StageCache:
    """A directory of entries, each a staged-output diff under a content key."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def token(self, inputs) -> str:
        """Stable key for an input description (schema-folded)."""
        return key({'schema': SCHEMA, 'inputs': inputs})

    def _entry(self, token: str) -> Path:
        return self.root / token

    def lookup(self, token: str) -> dict | None:
        """The stored manifest iff the entry is present and every file is on disk."""
        entry = self._entry(token)
        try:
            manifest = json.loads((entry / 'manifest.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return None
        files = manifest.get('files', [])
        tree = entry / 'tree'
        # An entry with no files is not a valid skip of an expensive step.
        if files and all((tree / name).is_file() for name in files):
            return manifest
        return None

    def restore(self, token: str, base: Path) -> dict:
        """Copy every cached file into ``base``; returns the manifest."""
        manifest = self.lookup(token)
        if manifest is None:
            raise KeyError(token)
        tree = self._entry(token) / 'tree'
        base = Path(base)
        for name in manifest['files']:
            dst = base / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists() or dst.is_symlink():
                dst.unlink()
            shutil.copy2(tree / name, dst)
        return manifest

    def store(self, token: str, base: Path, files: list[str], meta: dict | None = None) -> bool:
        """Snapshot ``files`` (relative to ``base``) under ``token``.

        Returns True when this call published the entry, False when a complete
        entry already existed (another build won the race, or a re-store).
        Publishing is atomic: a partial ``tree`` is never visible under the key.
        """
        if not files:
            return False
        self.root.mkdir(parents=True, exist_ok=True)
        with cache_lock(self.root):
            if self.lookup(token) is not None:
                return False
            staging = self.root / ('x-' + uuid.uuid4().hex[:12])
            tree = staging / 'tree'
            tree.mkdir(parents=True)
            try:
                for name in sorted(files):
                    src = Path(base) / name
                    dst = tree / name
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                write_json(staging / 'manifest.json',
                           {'schema': SCHEMA, 'files': sorted(files), 'meta': meta or {}})
                entry = self._entry(token)
                if entry.exists():
                    return False
                publish(staging, entry)
                staging = None
            finally:
                if staging is not None and staging.exists():
                    shutil.rmtree(staging, ignore_errors=True)
        return True
