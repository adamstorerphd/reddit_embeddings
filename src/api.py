import time
from typing import Any, Dict, Generator, List, Optional, Tuple

try:
    import requests
except ImportError:
    requests = None

BASE_URL = "https://arctic-shift.photon-reddit.com/api"


def api_get(
    path: str,
    params: Optional[dict] = None,
    tries: int = 5,
    timeout: int = 60,
    base_url: str = BASE_URL,
    logger=None
) -> Any:
    """GET request with exponential backoff for rate limits and server errors."""
    if requests is None:
        raise ImportError("The 'requests' package is required. Install via pip install requests.")
        
    if path.startswith("http://") or path.startswith("https://"):
        url = path
    else:
        url = base_url.rstrip("/") + "/" + path.lstrip("/")
    backoff = 3.0
    for attempt in range(1, tries + 1):
        try:
            r = requests.get(url, params=params, timeout=timeout)
            if r.status_code == 422 and "Timeout" in r.text:
                raise TimeoutError("Upstream aggregate timeout")
            if r.status_code in (429, 500, 502, 503):
                msg = f"API retry {attempt}/{tries} (status {r.status_code}) on {path}"
                if logger:
                    logger.warning(msg)
                time.sleep(backoff)
                backoff *= 2.0
                continue
            r.raise_for_status()
            return r
        except (requests.Timeout, requests.ConnectionError) as e:
            msg = f"API retry {attempt}/{tries} (network: {str(e)[:80]}) on {path}"
            if logger:
                logger.warning(msg)
            time.sleep(backoff)
            backoff *= 2.0

    raise RuntimeError(f"GET failed after {tries} attempts: {path} with {params}")


# Alias for backward compatibility
retry_get = api_get


def parse_agg(payload: Any) -> List[Tuple[Any, int]]:
    """Defensively parse aggregate response looking for timestamp and count keys."""
    data = payload.get("data", payload) if isinstance(payload, dict) else payload
    assert isinstance(data, list) and data, f"Unexpected aggregate shape: {str(payload)[:200]}"
    rows: List[Tuple[Any, int]] = []
    for d in data:
        if not isinstance(d, dict):
            continue
        ts_k = next((k for k in d if any(s in k.lower() for s in ("utc", "date", "time", "key", "bucket"))), None)
        c_k = next((k for k in d if any(s in k.lower() for s in ("count", "total", "n", "value", "doc"))), None)
        if ts_k is not None and c_k is not None:
            try:
                rows.append((d[ts_k], int(d[c_k])))
            except (ValueError, TypeError):
                continue
    assert rows, f"No timestamp/count pairs found in aggregate data: {str(data[:2])[:300]}"
    return rows


def api_pages(
    sub: str,
    ctype: str,
    after_u: int,
    before_u: int,
    fields: str,
    page_size: int = 100,
    max_pages: Optional[int] = None,
    base_url: str = BASE_URL,
    logger=None
) -> Generator[List[dict], None, None]:
    """Yield batches of records oldest-first via Arctic Shift search endpoint."""
    ep = "/posts/search" if ctype == "submissions" else "/comments/search"
    after = after_u
    pages = 0
    while True:
        if max_pages is not None and pages >= max_pages:
            break
        r = api_get(
            ep,
            params={
                "subreddit": sub,
                "after": after,
                "before": before_u,
                "limit": page_size,
                "sort": "asc",
                "fields": fields
            },
            base_url=base_url,
            logger=logger
        )
        data = r.json()
        batch = data.get("data", data if isinstance(data, list) else [])
        if not batch:
            break
        pages += 1
        yield batch
        after = int(batch[-1].get("created_utc", after)) + 1
        if len(batch) < page_size:
            break
