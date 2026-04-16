"""
Презентация в PPTX: JSON от LLM → python-pptx.
"""
import json
import re
import uuid
from pathlib import Path

import httpx


SLIDES_JSON_SYSTEM = """Ты возвращаешь ТОЛЬКО один JSON-объект. Первый символ ответа — «{», последний — «}».
Никакого текста, markdown и ``` до или после JSON.

Схема:
{"title":"Заголовок презентации","slides":[{"title":"Заголовок слайда","bullets":["короткий тезис"]}]}

Правила: 8–14 слайдов; 3–5 тезисов на слайд; последний слайд — итоги или «Вопросы?».
Используй обычные двойные кавычки ASCII. Не ставь запятую после последнего элемента массива/объекта.
Язык — как в запросе пользователя."""

REPAIR_SYSTEM = """Ниже фрагмент ответа модели (может быть с ошибками или лишним текстом).
Извлеки или восстанови ОДИН валидный JSON по схеме:
{"title":"строка","slides":[{"title":"строка","bullets":["строка",...]}, ...]}

Ответ — только JSON, первый символ «{», последний «}», без ``` и без пояснений."""


def _strip_fences(text: str) -> str:
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*```\s*$", "", t)
    return t.strip()


def parse_slides_json_loose(raw: str) -> dict:
    """Разбор JSON даже если до/после есть мусор или обёртка ```."""
    text = _strip_fences(raw)

    candidates = [text]
    if "{" in text:
        i = text.find("{")
        if i > 0:
            candidates.append(text[i:])

    for candidate in candidates:
        c = candidate.strip()
        if not c.startswith("{"):
            continue
        try:
            obj, _ = json.JSONDecoder().raw_decode(c)
            if isinstance(obj, dict):
                return normalize_slides_data(obj)
        except json.JSONDecodeError:
            continue

    raise ValueError("cannot parse slides json")


def normalize_slides_data(data: dict) -> dict:
    """Поддержка альтернативных ключей от разных моделей."""
    out = {"title": data.get("title") or "Презентация", "slides": []}
    slides = data.get("slides")
    if not isinstance(slides, list):
        return out
    for s in slides:
        if not isinstance(s, dict):
            continue
        title = (
            s.get("title")
            or s.get("heading")
            or s.get("name")
            or s.get("slide_title")
            or "Слайд"
        )
        bullets = (
            s.get("bullets")
            or s.get("points")
            or s.get("items")
            or s.get("content")
        )
        if isinstance(bullets, str):
            bullets = [b.strip() for b in re.split(r"[\n•;]+", bullets) if b.strip()]
        if not isinstance(bullets, list):
            bullets = []
        bullets = [str(b).strip() for b in bullets if str(b).strip()]
        out["slides"].append({"title": str(title).strip(), "bullets": bullets})
    return out


def json_to_markdown(data: dict) -> str:
    title = (data.get("title") or "Презентация").strip()
    lines = [f"# {title}", ""]
    slides = data.get("slides") or []
    if not isinstance(slides, list):
        slides = []
    for i, s in enumerate(slides, 1):
        if not isinstance(s, dict):
            continue
        st = (s.get("title") or f"Слайд {i}").strip()
        lines.append(f"## Слайд {i}: {st}")
        bullets = s.get("bullets") or []
        if isinstance(bullets, list):
            for b in bullets:
                lines.append(f"- {str(b).strip()}")
        lines.append("")
    return "\n".join(lines).strip()


def build_pptx_file(data: dict, out_path: Path) -> None:
    from pptx import Presentation

    out_path.parent.mkdir(parents=True, exist_ok=True)
    prs = Presentation()
    title_main = (data.get("title") or "Презентация").strip()[:200]

    slide_layout = prs.slide_layouts[0]
    slide = prs.slides.add_slide(slide_layout)
    slide.shapes.title.text = title_main

    slides = data.get("slides") or []
    if not isinstance(slides, list):
        slides = []

    bullet_layout = prs.slide_layouts[1]
    for item in slides[:20]:
        if not isinstance(item, dict):
            continue
        st = str(item.get("title", "Слайд"))[:200]
        bullets = item.get("bullets") or []
        if not isinstance(bullets, list):
            bullets = []
        bullets = [str(b).strip()[:500] for b in bullets[:8] if str(b).strip()]

        slide = prs.slides.add_slide(bullet_layout)
        slide.shapes.title.text = st
        body = slide.placeholders[1]
        tf = body.text_frame
        if bullets:
            tf.text = bullets[0]
            for b in bullets[1:]:
                p = tf.add_paragraph()
                p.text = b
                p.level = 0

    prs.save(str(out_path))


async def _chat_plain(
    api_base: str,
    headers: dict,
    model: str,
    system: str,
    user: str,
    timeout: float,
    temperature: float = 0.2,
) -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user[:14000]},
        ],
        "temperature": temperature,
        "max_tokens": 4096,
        "stream": False,
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            f"{api_base.rstrip('/')}/chat/completions",
            json=payload,
            headers=headers,
        )
    if resp.status_code != 200:
        raise RuntimeError(resp.text[:800])
    body = resp.json()
    return (
        body.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )


async def generate_slides_structure(
    api_base: str,
    headers: dict,
    model: str,
    user_message: str,
    memory_fragment: str,
    timeout: float = 120.0,
) -> dict:
    sys = SLIDES_JSON_SYSTEM
    if memory_fragment:
        sys += "\n\nУчитывай факты о пользователе, если уместно:\n" + memory_fragment[:1500]

    content = await _chat_plain(
        api_base, headers, model, sys, user_message, timeout, temperature=0.25
    )

    try:
        data = parse_slides_json_loose(content)
        if data.get("slides"):
            return data
    except (ValueError, json.JSONDecodeError, TypeError):
        pass

    repair_user = f"Исправь в валидный JSON:\n\n{content[:12000]}"
    try:
        fixed = await _chat_plain(
            api_base,
            headers,
            model,
            REPAIR_SYSTEM,
            repair_user,
            timeout,
            temperature=0.1,
        )
        data = parse_slides_json_loose(fixed)
        if data.get("slides"):
            return data
    except (ValueError, json.JSONDecodeError, TypeError, RuntimeError):
        pass

    raise ValueError("slides json failed after repair")


def fallback_structure(topic: str) -> dict:
    return {
        "title": topic[:120] or "Презентация",
        "slides": [
            {
                "title": "Ошибка генерации",
                "bullets": [
                    "Не удалось разобрать JSON от модели.",
                    "Попробуйте упростить запрос или повторить.",
                ],
            }
        ],
    }


def new_export_id() -> str:
    return str(uuid.uuid4())
