"""
Разбор последнего user-сообщения OpenWebUI / OpenAI-совместимого формата.
"""
import base64
import re

from tools.file_parser import parse_file


def parse_last_user_message(messages: list | None) -> dict:
    result = {
        "text": "",
        "has_image": False,
        "has_audio": False,
        "file_context": "",
        "audio_bytes": None,
        "audio_filename": "audio.webm",
        "wants_image_generation": False,
    }
    if not messages:
        return result

    last = None
    for m in reversed(messages):
        if m.get("role") == "user":
            last = m
            break
    if not last:
        return result

    text_chunks: list[str] = []
    file_chunks: list[str] = []

    def handle_part(part):
        if isinstance(part, str):
            text_chunks.append(part)
            return
        if not isinstance(part, dict):
            return
        t = part.get("type")
        if t == "text":
            text_chunks.append(part.get("text") or "")
        elif t == "image_url":
            result["has_image"] = True
        elif t in ("input_audio", "audio_url", "audio"):
            result["has_audio"] = True
            ia = part.get("input_audio") or part.get("audio_url") or part
            if isinstance(ia, dict):
                data = ia.get("data") or ia.get("base64")
                if isinstance(data, str):
                    if data.startswith("data:") and "," in data:
                        data = data.split(",", 1)[1]
                    try:
                        result["audio_bytes"] = base64.b64decode(data)
                    except Exception:
                        result["audio_bytes"] = None
                fmt = ia.get("format") or "webm"
                if isinstance(fmt, str):
                    result["audio_filename"] = f"audio.{fmt.lstrip('.')}"
        elif t in ("file", "document", "attachment"):
            doc = part.get("document") or part.get("file") or part
            if not isinstance(doc, dict):
                return
            fn = doc.get("filename") or doc.get("name") or "file"
            txt = doc.get("text") or doc.get("content")
            if isinstance(txt, str) and txt.strip():
                file_chunks.append(f"[Содержимое файла «{fn}»]:\n{txt[:12000]}")
                return
            b64 = doc.get("data")
            if isinstance(b64, str):
                try:
                    raw = base64.b64decode(b64)
                    extracted = parse_file(str(fn), raw)
                    if extracted and not extracted.startswith("Файл "):
                        file_chunks.append(f"[Извлечено из «{fn}»]:\n{extracted[:12000]}")
                except Exception:
                    pass

    content = last.get("content")
    if isinstance(content, str):
        text_chunks.append(content)
    elif isinstance(content, list):
        for p in content:
            handle_part(p)

    result["text"] = "\n".join(x for x in text_chunks if x).strip()

    img_kw = re.compile(
        r"нарисуй|сгенерируй изображение|картинк|изображен|illustration|draw\s|generate\s+image",
        re.I,
    )
    if not result["has_image"] and result["text"] and img_kw.search(result["text"]):
        result["wants_image_generation"] = True

    result["file_context"] = "\n\n".join(file_chunks)
    return result
