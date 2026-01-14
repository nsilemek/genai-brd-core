from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import requests

try:
    from bs4 import BeautifulSoup  # type: ignore
except Exception:
    BeautifulSoup = None


def _clean_html_to_text(html: str) -> str:
    html = html or ""
    if BeautifulSoup:
        soup = BeautifulSoup(html, "html.parser")
        txt = soup.get_text("\n")
    else:
        # fallback: very basic strip
        txt = re.sub(r"<[^>]+>", " ", html)
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    return txt.strip()


def fetch_confluence_pages(
    *,
    base_url: str,
    username: str,
    api_token: str,
    space_key: Optional[str] = None,
    limit: int = 50,
    page_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Returns list of docs:
      { "id": "...", "title": "...", "url": "...", "text": "...", "source": "confluence" }
    """
    if not base_url:
        raise ValueError("base_url is required")

    base_url = base_url.rstrip("/")
    auth = (username, api_token)

    docs: List[Dict[str, Any]] = []

    if page_ids:
        for pid in page_ids:
            url = f"{base_url}/rest/api/content/{pid}"
            params = {"expand": "body.storage,version,title"}
            r = requests.get(url, auth=auth, params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
            title = data.get("title", f"page_{pid}")
            storage = (((data.get("body") or {}).get("storage") or {}).get("value")) or ""
            text = _clean_html_to_text(storage)
            webui = (data.get("_links") or {}).get("webui", "")
            full_url = f"{base_url}{webui}" if webui else url
            docs.append(
                {"id": str(pid), "title": title, "url": full_url, "text": text, "source": "confluence"}
            )
        return docs

    # space mode
    if not space_key:
        raise ValueError("space_key is required if page_ids is not provided")

    start = 0
    remaining = max(1, int(limit))

    while remaining > 0:
        batch = min(remaining, 50)
        url = f"{base_url}/rest/api/content"
        params = {
            "type": "page",
            "spaceKey": space_key,
            "limit": batch,
            "start": start,
            "expand": "body.storage,version,title",
        }
        r = requests.get(url, auth=auth, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()

        results = data.get("results", []) or []
        if not results:
            break

        for item in results:
            pid = item.get("id")
            title = item.get("title", f"page_{pid}")
            storage = (((item.get("body") or {}).get("storage") or {}).get("value")) or ""
            text = _clean_html_to_text(storage)
            webui = (item.get("_links") or {}).get("webui", "")
            full_url = f"{base_url}{webui}" if webui else ""
            docs.append(
                {"id": str(pid), "title": title, "url": full_url, "text": text, "source": "confluence"}
            )

        fetched = len(results)
        start += fetched
        remaining -= fetched

        if fetched == 0:
            break

    return docs
