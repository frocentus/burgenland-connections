"""Höflicher HTTP-Client mit Datei-Cache, Retries und Rate-Limit."""

from __future__ import annotations

import gzip
import hashlib
import json
import random
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import config

_ssl_ctx = None


def _ssl_context():
    global _ssl_ctx
    if _ssl_ctx is None:
        import ssl

        _ssl_ctx = ssl.create_default_context()
    return _ssl_ctx


class FetchError(RuntimeError):
    pass


class Fetcher:
    """Kapselt alle Netzzugriffe. Nutzt einen On-Disk-Cache, damit
    Auswertungsläufe reproduzierbar und wiederholbar sind."""

    def __init__(
        self,
        cache_dir: Path | None = None,
        use_cache: bool = True,
        refresh: bool = False,
        min_interval: float | None = None,
        verbose: bool = False,
    ) -> None:
        config.ensure_dirs()
        self.cache_dir = Path(cache_dir) if cache_dir else config.CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.use_cache = use_cache
        self.refresh = refresh
        self.min_interval = config.MIN_REQUEST_INTERVAL if min_interval is None else min_interval
        self.verbose = verbose
        self._last_request = 0.0
        self.stats = {"cache": 0, "net": 0, "errors": 0}

    # -- Cache ---------------------------------------------------------
    def _cache_path(self, url: str) -> Path:
        digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}.html"

    def _gone_path(self, url: str) -> Path:
        """Marker für endgültig verschwundene Seiten (404/410).

        Ohne Marker würde jeder Lauf die toten URLs erneut abfragen – bei
        mehreren hundert Archiv-URLs kostet das Minuten und Network-Retries.
        """
        return self._cache_path(url).with_suffix(".gone")

    def _read_cache(self, url: str) -> str | None:
        p = self._cache_path(url)
        if p.exists():
            raw = p.read_bytes()
            if raw.startswith(b"\x1f\x8b"):
                raw = gzip.decompress(raw)
            return raw.decode("utf-8", "replace")
        return None

    def _write_cache(self, url: str, text: str) -> None:
        p = self._cache_path(url)
        tmp = p.with_suffix(".tmp")
        tmp.write_bytes(text.encode("utf-8"))
        tmp.replace(p)

    # -- Netz ----------------------------------------------------------
    def _throttle(self) -> None:
        wait = self.min_interval - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()

    def get(self, url: str, *, timeout: int | None = None) -> str:
        if self.use_cache and not self.refresh:
            cached = self._read_cache(url)
            if cached is not None:
                self.stats["cache"] += 1
                return cached
            if self._gone_path(url).exists():
                self.stats["cache"] += 1
                raise FetchError(f"404 (gemerkt) {url}")

        last_err: Exception | None = None
        for attempt in range(1, config.MAX_RETRIES + 1):
            self._throttle()
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": config.USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "de-AT,de;q=0.9,en;q=0.5",
                    "Accept-Encoding": "identity",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout or config.REQUEST_TIMEOUT) as resp:
                    raw = resp.read()
                    if resp.headers.get("Content-Encoding") == "gzip":
                        raw = gzip.decompress(raw)
                    text = raw.decode(resp.headers.get_content_charset() or "utf-8", "replace")
                self.stats["net"] += 1
                self._write_cache(url, text)
                return text
            except urllib.error.HTTPError as exc:
                last_err = exc
                if exc.code in (404, 410):
                    try:
                        self._gone_path(url).write_text(
                            f"{exc.code} {url}", encoding="utf-8")
                    except OSError:
                        pass
                    raise FetchError(f"{exc.code} {url}") from exc
                if exc.code in (429, 500, 502, 503, 504):
                    time.sleep(2 ** attempt + random.random())
                    continue
                raise FetchError(f"{exc.code} {url}") from exc
            except Exception as exc:  # noqa: BLE001 - Netzfehler breit abfangen
                last_err = exc
                time.sleep(1.5 * attempt + random.random())
        self.stats["errors"] += 1
        raise FetchError(f"{url}: {last_err}")

    def get_json(self, url: str) -> dict:
        return json.loads(self.get(url))
