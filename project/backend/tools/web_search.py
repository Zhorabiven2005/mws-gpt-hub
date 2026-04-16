"""
Веб-поиск через DuckDuckGo (без API ключа).
"""
import httpx
from bs4 import BeautifulSoup


async def web_search(query: str, max_results: int = 5) -> str:
    """Поиск в интернете через DuckDuckGo."""
    url = "https://html.duckduckgo.com/html/"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, data={"q": query}, headers=headers)
            soup = BeautifulSoup(resp.text, "html.parser")
            
            results = []
            for r in soup.select(".result__body")[:max_results]:
                title_el = r.select_one(".result__title")
                snippet_el = r.select_one(".result__snippet")
                title = title_el.get_text(strip=True) if title_el else ""
                snippet = snippet_el.get_text(strip=True) if snippet_el else ""
                if title or snippet:
                    results.append(f"• {title}: {snippet}")
            
            if results:
                return "Результаты поиска:\n" + "\n".join(results)
            return "Результаты поиска не найдены."
    except Exception as e:
        return f"Ошибка поиска: {str(e)}"
