"""
Парсинг веб-страницы по URL — извлекает текст для передачи в LLM.
"""
import httpx
from bs4 import BeautifulSoup
import re


async def scrape_url(url: str, max_chars: int = 3000) -> str:
    """Парсит URL и возвращает текст страницы."""
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # Убираем скрипты и стили
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            
            text = soup.get_text(separator="\n", strip=True)
            # Убираем множественные пустые строки
            text = re.sub(r"\n{3,}", "\n\n", text)
            
            if len(text) > max_chars:
                text = text[:max_chars] + "\n\n[текст обрезан...]"
            
            return f"Содержимое страницы {url}:\n\n{text}"
    except Exception as e:
        return f"Ошибка при загрузке {url}: {str(e)}"
