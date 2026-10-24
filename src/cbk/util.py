"""Shared helpers: logging, HTTP sessions, streaming downloads, checksums."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import requests

log = logging.getLogger("cbk")

USER_AGENT = "crisis-baseline-kit/0.1 (open-source humanitarian baseline toolkit)"


def setup_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="[cbk] %(levelname)s %(message)s",
    )


def new_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT})
    return s


def sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def download(
    url: str,
    dest_dir: Path,
    session: requests.Session | None = None,
    timeout: tuple[int, int] = (20, 300),
) -> tuple[Path, str]:
    """Stream a file to dest_dir, computing its SHA-256 while writing.

    Returns (path, sha256).
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = url.split("/")[-1].split("?")[0] or "download"
    dest = dest_dir / name
    own_session = session is None
    s = new_session() if own_session else session
    try:
        with s.get(url, stream=True, timeout=timeout, allow_redirects=True) as r:
            r.raise_for_status()
            h = hashlib.sha256()
            done = 0
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    if chunk:
                        f.write(chunk)
                        h.update(chunk)
                        done += len(chunk)
                        if done % (50 << 20) < (1 << 20):
                            log.info("... %s: %.0f MB downloaded", dest.name, done / 1e6)
    finally:
        if own_session:
            s.close()
    log.info("Downloaded %s (%.1f MB)", dest.name, dest.stat().st_size / 1e6)
    return dest, h.hexdigest()
