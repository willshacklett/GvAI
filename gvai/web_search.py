from __future__ import annotations

import os
import re
import html
from typing import Any, Dict, List

import requests


USER_AGENT = "GvAI/1.0 (+https://gvai.io)"


def _safe_get(url: str, *, params: Dict[str, Any] | None = None, headers: Dict[str, str] | None = None, timeout: int = 20):
    merged_headers = {"User-Agent": USER_AGENT}
    if headers:
        merged_headers.update(headers)
    return requests.get(url, params=params, headers=merged_headers, timeout=timeout)


def tavily_search(query: str, max_results: int = 5) -> Dict[str, Any]:
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("TAVILY_API_KEY not configured")

    url = "https://api.tavily.com/search"
    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "advanced",
        "max_results": max_results,
        "include_answer": True,
        "include_raw_content": False,
    }
    res = requests.post(url, json=payload, timeout=30)
    res.raise_for_status()
    data = res.json()

    results = []
    for item in data.get("results", [])[:max_results]:
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": item.get("content", ""),
            "source": "tavily",
        })

    return {
        "provider": "tavily",
        "query": query,
        "answer": data.get("answer", ""),
        "results": results,
    }


def ddg_search(query: str, max_results: int = 5) -> Dict[str, Any]:
    # Lightweight fallback. Not as strong as Tavily, but useful when no key is set.
    url = "https://html.duckduckgo.com/html/"
    res = requests.post(
        url,
        data={"q": query},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=25,
    )
    res.raise_for_status()
    html_text = res.text

    # Extract basic results from DuckDuckGo HTML page
    blocks = re.findall(
        r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>(.*?)</div>',
        html_text,
        flags=re.S | re.I,
    )

    results: List[Dict[str, str]] = []
    for href, title_html, tail in blocks:
        title = re.sub(r"<.*?>", "", title_html)
        title = html.unescape(title).strip()

        snippet_match = re.search(r'result__snippet[^>]*>(.*?)<', tail, flags=re.S | re.I)
        snippet = ""
        if snippet_match:
            snippet = html.unescape(re.sub(r"<.*?>", "", snippet_match.group(1))).strip()

        results.append({
            "title": title,
            "url": html.unescape(href),
            "snippet": snippet,
            "source": "duckduckgo",
        })
        if len(results) >= max_results:
            break

    return {
        "provider": "duckduckgo",
        "query": query,
        "answer": "",
        "results": results,
    }


def search_web(query: str, max_results: int = 5) -> Dict[str, Any]:
    query = (query or "").strip()
    if not query:
        return {"provider": "none", "query": "", "answer": "", "results": []}

    if os.getenv("TAVILY_API_KEY", "").strip():
        try:
            return tavily_search(query, max_results=max_results)
        except Exception as e:
            return {
                "provider": "tavily_error",
                "query": query,
                "answer": "",
                "results": [],
                "error": str(e),
            }

    try:
        return ddg_search(query, max_results=max_results)
    except Exception as e:
        return {
            "provider": "duckduckgo_error",
            "query": query,
            "answer": "",
            "results": [],
            "error": str(e),
        }
