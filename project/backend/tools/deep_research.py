"""
Deep Research (MVP): несколько веб-поисков → контекст для LLM.
"""
import asyncio

from .web_search import web_search

_MAX_TOTAL_CHARS = 10_000


async def _one_search(label: str, q: str) -> str:
    try:
        chunk = await web_search(q, max_results=3)
        return f"### {label}: {q}\n{chunk}"
    except Exception as e:
        return f"### {label}: {q}\n(ошибка поиска: {e})"


async def gather_research_context(topic: str) -> str:
    t = (topic or "").strip()
    if not t:
        return ""

    queries = [
        ("Запрос 1", t[:200]),
        ("Запрос 2", f"{t[:120]} обзор перспективы"),
        ("Запрос 3", f"{t[:120]} проблемы ограничения"),
    ]
    blocks = await asyncio.gather(*[_one_search(lbl, q) for lbl, q in queries])
    full = "\n\n".join(blocks)
    if len(full) > _MAX_TOTAL_CHARS:
        full = full[:_MAX_TOTAL_CHARS] + "\n\n[фрагменты поиска обрезаны по длине]"

    return (
        "Материалы веб-поиска (могут быть неполными и устаревшими):\n\n" + full
    )
