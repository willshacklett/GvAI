import requests

def search_web(query: str):
    try:
        url = "https://duckduckgo.com/?q=" + query.replace(" ", "+")
        return {
            "source": "web",
            "query": query,
            "result": f"Search results available: {url}"
        }
    except Exception as e:
        return {"error": str(e)}
