from __future__ import annotations

import os
import re
from html import unescape
from typing import List, Dict, Optional, Any
from abc import ABC, abstractmethod

import requests

try:
    from bs4 import BeautifulSoup  # type: ignore
except Exception:
    BeautifulSoup = None


class WikiClient(ABC):
    """Abstract base class for wiki clients"""

    @abstractmethod
    def fetch_page(self, page_id: str) -> Dict[str, Any]:
        """Fetch a single page by ID"""
        raise NotImplementedError

    @abstractmethod
    def fetch_pages(self, space_key: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Fetch multiple pages"""
        raise NotImplementedError

    @abstractmethod
    def extract_text(self, page_data: Dict[str, Any]) -> str:
        """Extract plain text from page data"""
        raise NotImplementedError


class ConfluenceClient(WikiClient):
    """
    Atlassian Confluence wiki client
    """

    def __init__(
        self,
        base_url: str,
        username: Optional[str] = None,
        api_token: Optional[str] = None,
        password: Optional[str] = None,
        timeout_sec: int = 30,
    ):
        self.base_url = (base_url or "").rstrip("/")
        if not self.base_url:
            raise ValueError("Confluence base_url is required")

        self.username = username or os.getenv("CONFLUENCE_USERNAME")
        self.api_token = api_token or os.getenv("CONFLUENCE_API_TOKEN")
        self.password = password or os.getenv("CONFLUENCE_PASSWORD")
        self.timeout_sec = int(timeout_sec)

        if not self.username:
            raise ValueError("Confluence username required (env: CONFLUENCE_USERNAME)")
        if not (self.api_token or self.password):
            raise ValueError(
                "Confluence API token or password required (env: CONFLUENCE_API_TOKEN or CONFLUENCE_PASSWORD)"
            )

        # Ensure both username and password/token are not None
        if self.api_token:
            auth_password = self.api_token
        elif self.password:
            auth_password = self.password
        else:
            raise ValueError("Confluence API token or password required (env: CONFLUENCE_API_TOKEN or CONFLUENCE_PASSWORD)")

        self.auth = (self.username, auth_password)
        self.session = requests.Session()
        self.session.auth = self.auth

        print(f"ConfluenceClient initialized for {self.base_url} as {self.api_token}")

    def fetch_page(self, page_id: str) -> Dict[str, Any]:
        """Fetch a single Confluence page by ID"""
        url = f"{self.base_url}/rest/api/content/{page_id}"
        params = {"expand": "body.storage,version,space,_links"}
        r = self.session.get(url, params=params, timeout=self.timeout_sec)
        r.raise_for_status()
        return r.json()

    def fetch_pages(
        self,
        space_key: Optional[str] = None,
        limit: int = 100,
        cql: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch multiple Confluence pages
        """
        url = f"{self.base_url}/rest/api/content/search"
        limit = max(1, int(limit))

        params = {"expand": "body.storage,version,space,_links", "limit": min(limit, 50)}

        if cql:
            params["cql"] = cql
        elif space_key:
            params["cql"] = f"type=page AND space={space_key}"
        else:
            params["cql"] = "type=page"

        all_pages: List[Dict[str, Any]] = []
        start = 0

        while len(all_pages) < limit:
            params["start"] = start
            r = self.session.get(url, params=params, timeout=self.timeout_sec)
            r.raise_for_status()
            data = r.json()

            pages = data.get("results", []) or []
            if not pages:
                break

            all_pages.extend(pages)

            # Confluence "next" link exists when more data
            if not (data.get("_links") or {}).get("next"):
                break

            start += len(pages)

        return all_pages[:limit]

    def extract_text(self, page_data: Dict[str, Any]) -> str:
        """Extract plain text from Confluence page"""
        body = page_data.get("body") or {}
        storage = body.get("storage") or {}
        html_content = storage.get("value") or ""

        if not html_content:
            return ""

        if BeautifulSoup is not None:
            soup = BeautifulSoup(html_content, "html.parser")
            text = soup.get_text("\n")  # satır kırılımları daha iyi
        else:
            # fallback: tag strip + basic breaks
            text = re.sub(r"</(p|div|br|li|tr|h\d)>", "\n", html_content, flags=re.I)
            text = re.sub(r"<[^>]+>", " ", text)

        text = unescape(text)
        # whitespace normalize
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def create_wiki_client(**kwargs) -> ConfluenceClient:
    """
    Factory: ignore unknown keys safely (demo-safe)
    """
    allowed = {"base_url", "username", "api_token", "password", "timeout_sec"}
    filtered = {k: v for k, v in kwargs.items() if k in allowed}
    return ConfluenceClient(**filtered)
