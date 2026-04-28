import requests

def search_web(query: str, max_results: int = 5):
    try:
        url = "https://api.duckduckgo.com/"
        params = {
            "q": query,
            "format": "json",
            "no_html": "1",
            "skip_disambig": "1"
        }
        r = requests.get(url, params=params, timeout=8)
        data = r.json()

        results = []

        if data.get("AbstractText"):
            results.append({
                "title": data.get("Heading") or "DuckDuckGo result",
                "snippet": data.get("AbstractText"),
                "url": data.get("AbstractURL") or ""
            })

        for item in data.get("RelatedTopics", []):
            if isinstance(item, dict) and item.get("Text"):
                results.append({
                    "title": item.get("Text", "")[:80],
                    "snippet": item.get("Text", ""),
                    "url": item.get("FirstURL", "")
                })

        return results[:max_results]
    except Exception as e:
        return [{"title": "search_error", "snippet": str(e), "url": ""}]
