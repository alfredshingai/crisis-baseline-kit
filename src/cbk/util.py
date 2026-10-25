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
    attempts: int = 4,
) -> tuple[Path, str]:
    """Stream a file to dest_dir, computing its SHA-256 while writing.

    Retries with backoff on connection errors — public data hosts
    (HDX, WorldPop) drop connections under load.

    Returns (path, sha256).
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = url.split("/")[-1].split("?")[0] or "download"
    dest = dest_dir / name
    own_session = session is None
    s = new_session() if own_session else session
    last_exc: Exception | None = None
    try:
        for attempt in range(1, attempts + 1):
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
                log.info("Downloaded %s (%.1f MB)", dest.name, dest.stat().st_size / 1e6)
                return dest, h.hexdigest()
            except (requests.ConnectionError, requests.Timeout) as exc:
                last_exc = exc
                if attempt < attempts:
                    wait = attempt * 15
                    log.warning("Download of %s failed (%s); retry %d/%d in %ds",
                                name, exc.__class__.__name__, attempt, attempts - 1, wait)
                    import time

                    time.sleep(wait)
        raise last_exc  # type: ignore[misc]
    finally:
        if own_session:
            s.close()


def get_json(session: requests.Session, url: str, params: dict | None = None,
             timeout: tuple[int, int] = (20, 60), attempts: int = 3) -> dict:
    """GET a JSON API endpoint with retries; returns parsed JSON."""
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            r = session.get(url, params=params, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except (requests.ConnectionError, requests.Timeout) as exc:
            last_exc = exc
            if attempt < attempts:
                import time

                time.sleep(attempt * 10)
    raise last_exc  # type: ignore[misc]
