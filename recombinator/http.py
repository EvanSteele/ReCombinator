from __future__ import annotations

import gzip
import zlib
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


DEFAULT_USER_AGENT = (
    "ReCombinator/0.1 (+https://news.ycombinator.com/; "
    "brief personal technology digest)"
)


@dataclass(slots=True)
class FetchResult:
    url: str
    status: int | None
    content_type: str
    text: str


def fetch_text(url: str, timeout: float = 15.0) -> FetchResult:
    """Fetch a URL and decode likely textual content."""
    request = Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "User-Agent": DEFAULT_USER_AGENT,
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
            headers = response.headers
            encoding = headers.get("Content-Encoding", "").lower()
            content_type = headers.get("Content-Type", "")
            raw = _decompress(raw, encoding)
            charset = headers.get_content_charset() or "utf-8"
            return FetchResult(
                url=response.geturl(),
                status=getattr(response, "status", None),
                content_type=content_type,
                text=raw.decode(charset, errors="replace"),
            )
    except HTTPError as error:
        body = error.read()
        body = _decompress(body, error.headers.get("Content-Encoding", "").lower())
        charset = error.headers.get_content_charset() or "utf-8"
        return FetchResult(
            url=error.geturl(),
            status=error.code,
            content_type=error.headers.get("Content-Type", ""),
            text=body.decode(charset, errors="replace"),
        )
    except URLError as error:
        reason = getattr(error, "reason", error)
        raise RuntimeError(f"Could not fetch {url}: {reason}") from error


def is_http_url(url: str) -> bool:
    return urlparse(url).scheme in {"http", "https"}


def _decompress(raw: bytes, encoding: str) -> bytes:
    if encoding == "gzip":
        return gzip.decompress(raw)
    if encoding == "deflate":
        try:
            return zlib.decompress(raw)
        except zlib.error:
            return zlib.decompress(raw, -zlib.MAX_WBITS)
    return raw

