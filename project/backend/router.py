"""
Автоматический выбор модели под задачу пользователя.
"""
import os

CODING_KEYWORDS = [
    "код", "code", "функция", "function", "python", "javascript",
    "typescript", "java", "баг", "bug", "ошибка в коде", "debug",
    "программа", "алгоритм", "напиши скрипт",
]

IMAGE_GEN_KEYWORDS = [
    "картинк", "изображен", "сгенерируй фото", "сделай фото", "image", "picture", "нарисуй",
    "сгенерируй изображение", "покажи как выглядит", "сделай иллюстрац",
    "draw ", "generate image", "dall-e",
]

SEARCH_KEYWORDS = [
    "найди в интернете", "погугли", "поищи", "актуальн", "последние новости",
    "веб поиск", "web search", "найди информацию",
]

SEMANTIC_KEYWORDS = [
    "похожие", "семантическ", "embedding", "similarity", "сравни тексты",
]

DEEP_RESEARCH_KEYWORDS = [
    "deep research",
    "глубокое исследование",
    "глубокий анализ",
    "исследуй тему",
    "режим исследования",
    "research mode",
    "подробно исследуй",
    "сделай исследование",
    "развернутое исследование",
]

SLIDES_KEYWORDS = [
    "презентац",
    "слайды",
    "слайдов",
    "слайд ",
    "presentation",
    "оформи как презентацию",
    "сделай доклад со слайдами",
]

ROUTER_AUTO_MODEL_ID = os.getenv("ROUTER_AUTO_MODEL_ID", "mws-router-auto")

DEFAULT_CHAT = os.getenv("MWS_DEFAULT_CHAT_MODEL", "mws-gpt-alpha")
CODING_MODEL = os.getenv("MWS_CODING_MODEL", "qwen3-coder-480b-a35b")
VLM_MODEL = os.getenv("MWS_VLM_MODEL", "qwen2.5-vl")
IMAGE_GEN_MODEL = os.getenv("MWS_IMAGE_GEN_MODEL", "").strip()
RESEARCH_MODEL = os.getenv("MWS_RESEARCH_MODEL", "mws-gpt-alpha")
SLIDES_MODEL = os.getenv("MWS_SLIDES_MODEL", "mws-gpt-alpha")


def is_auto_router_selection(manual_model: str | None) -> bool:
    if not manual_model:
        return True
    mid = manual_model.strip().lower()
    if mid == ROUTER_AUTO_MODEL_ID.lower():
        return True
    if mid in ("auto", "router-auto", "mws-router-auto"):
        return True
    return False


def select_model(
    message: str,
    has_image: bool = False,
    has_audio: bool = False,
    wants_image_generation: bool = False,
    manual_model: str | None = None,
) -> dict:
    if not is_auto_router_selection(manual_model):
        return {"model": manual_model, "task_type": "manual", "auto": False}

    text = (message or "").lower()

    if has_audio:
        return {"model": DEFAULT_CHAT, "task_type": "audio", "auto": True}

    if has_image:
        return {"model": VLM_MODEL, "task_type": "vision", "auto": True}

    if wants_image_generation and IMAGE_GEN_MODEL:
        return {"model": IMAGE_GEN_MODEL, "task_type": "image_gen", "auto": True}

    if any(kw in text for kw in IMAGE_GEN_KEYWORDS):
        if IMAGE_GEN_MODEL:
            return {"model": IMAGE_GEN_MODEL, "task_type": "image_gen", "auto": True}
        return {"model": DEFAULT_CHAT, "task_type": "image_gen_text", "auto": True}

    if any(kw in text for kw in CODING_KEYWORDS):
        return {"model": CODING_MODEL, "task_type": "coding", "auto": True}

    if any(kw in text for kw in SEMANTIC_KEYWORDS):
        return {"model": DEFAULT_CHAT, "task_type": "semantic", "auto": True}

    if any(kw in text for kw in SLIDES_KEYWORDS):
        return {"model": SLIDES_MODEL, "task_type": "slides", "auto": True}

    if any(kw in text for kw in DEEP_RESEARCH_KEYWORDS):
        return {"model": RESEARCH_MODEL, "task_type": "deep_research", "auto": True}

    if any(kw in text for kw in SEARCH_KEYWORDS):
        return {"model": DEFAULT_CHAT, "task_type": "search", "auto": True}

    return {"model": DEFAULT_CHAT, "task_type": "text", "auto": True}


def get_available_models() -> list:
    return [
        {"id": ROUTER_AUTO_MODEL_ID, "name": "Автовыбор модели (router)"},
        {"id": "mws-gpt-alpha", "name": "MWS GPT Alpha (универсальный)"},
        {"id": "qwen3-coder-480b-a35b", "name": "Qwen3 Coder (код)"},
        {"id": "qwen2.5-72b-instruct", "name": "Qwen2.5 72B (мощный)"},
        {"id": "cotype-pro-vl-32k", "name": "Cotype Pro VL 32k (длинный контекст)"},
        {"id": "qwen-image-lightning", "name": "Qwen Image Lightning (генерация картинок)"},
        {"id": "bge-m3", "name": "BGE-M3 (эмбеддинги)"},
    ]