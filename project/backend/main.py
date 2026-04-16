"""
Главный FastAPI бэкенд — прослойка между OpenWebUI и MWS GPT API.
"""
import json
import os
import re
import uuid
from pathlib import Path

import httpx
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from router import select_model, get_available_models, IMAGE_GEN_MODEL
from memory import build_memory_prompt, extract_and_save_facts
from tools.web_search import web_search
from tools.web_scraper import scrape_url
from tools.file_parser import parse_file
from tools.image_gen import try_generate_image
from tools.asr import try_transcribe_bytes
from tools.deep_research import gather_research_context
from tools.slides_pptx import (
    build_pptx_file,
    fallback_structure,
    generate_slides_structure,
    json_to_markdown,
    new_export_id,
)
from message_parse import parse_last_user_message

DEEP_RESEARCH_SYSTEM = """
---
Режим Deep Research: опирайся на блок «Материалы веб-поиска» в контексте выше.
Сделай структурированный отчёт: (1) краткое резюме, (2) ключевые факты списком, (3) нюансы и противоречия если видны,
(4) ограничения данных, (5) что изучить дальше. Не придумывай конкретные ссылки и цифры без опоры на переданные фрагменты.
"""

load_dotenv()

MWS_API_KEY = os.getenv("MWS_API_KEY", "")
MWS_API_BASE = os.getenv("MWS_API_BASE", "https://api.gpt.mws.ru/v1")

EXPORTS_DIR = Path(os.getenv("MEMORY_DB_PATH", "/app/data/memory.db")).parent / "exports"
_PPTX_ID = re.compile(
    r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\.pptx$",
    re.I,
)

app = FastAPI(title="MWS GPT Router", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HEADERS = {
    "Authorization": f"Bearer {MWS_API_KEY}",
    "Content-Type": "application/json",
}

URL_PATTERN = re.compile(r"https?://[^\s]+")


def extract_urls(text: str) -> list[str]:
    return URL_PATTERN.findall(text or "")


def extract_user_id(request: Request, body: dict) -> str:
    u = body.get("user")
    if isinstance(u, str) and u.strip():
        return u.strip()[:128]
    for h in (
        "X-User-Id",
        "X-OpenWebUI-User-Id",
        "X-Openwebui-User-Id",
        "X-User-Email",
    ):
        v = request.headers.get(h)
        if v and v.strip():
            return v.strip()[:128]
    return "default_user"


@app.get("/v1/models")
async def list_models():
    models = get_available_models()
    return {
        "object": "list",
        "data": [
            {
                "id": m["id"],
                "object": "model",
                "created": 1700000000,
                "owned_by": "mws",
                "name": m["name"],
            }
            for m in models
        ],
    }


def _openai_chat_response(content: str, model: str, finish_reason: str = "stop") -> dict:
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
        "object": "chat.completion",
        "created": 1700000000,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": finish_reason,
            }
        ],
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    user_id = extract_user_id(request, body)
    messages = list(body.get("messages") or [])
    manual_model = body.get("model")

    parsed = parse_last_user_message(messages)
    last_user_msg = parsed["text"]
    has_image = parsed["has_image"]
    has_audio = parsed["has_audio"]
    file_context = parsed["file_context"]
    wants_image_generation = parsed["wants_image_generation"]

    extract_and_save_facts(user_id, last_user_msg)

    route = select_model(
        last_user_msg,
        has_image=has_image,
        has_audio=has_audio,
        wants_image_generation=wants_image_generation,
        manual_model=manual_model,
    )
    chosen_model = route["model"]
    task_type = route["task_type"]

    memory_text = build_memory_prompt(user_id)
    extra_context = ""

    if file_context:
        extra_context += "\n\n" + file_context

    if parsed["audio_bytes"] and os.getenv("MWS_ASR_MODEL", "").strip():
        tr = await try_transcribe_bytes(
            parsed["audio_bytes"],
            parsed["audio_filename"],
            MWS_API_BASE,
            HEADERS,
        )
        if tr:
            extra_context += f"\n\nРаспознанная речь из вложения:\n{tr}"

    urls = extract_urls(last_user_msg)
    if urls:
        scraped = []
        for url in urls[:2]:
            scraped.append(await scrape_url(url))
        extra_context += "\n\n" + "\n\n".join(scraped)

    if task_type == "search":
        search_result = await web_search(last_user_msg)
        extra_context += "\n\n" + search_result

    if task_type == "deep_research":
        extra_context += "\n\n" + await gather_research_context(last_user_msg)

    if task_type == "image_gen_text" and not IMAGE_GEN_MODEL:
        extra_context += (
            "\n\n[Подсказка: в .env задайте MWS_IMAGE_GEN_MODEL при наличии images/generations у MWS.]"
        )

    if task_type == "slides":
        base_url = os.getenv("PPTX_PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
        user_blob = last_user_msg
        if extra_context.strip():
            user_blob = f"{last_user_msg}\n\n--- Дополнительный контекст ---\n{extra_context}"
        mem_frag = memory_text.strip()
        try:
            struct = await generate_slides_structure(
                MWS_API_BASE,
                HEADERS,
                chosen_model,
                user_blob,
                mem_frag,
                timeout=120.0,
            )
        except Exception:
            struct = fallback_structure(last_user_msg)
        eid = new_export_id()
        out_path = EXPORTS_DIR / f"{eid}.pptx"
        try:
            build_pptx_file(struct, out_path)
        except Exception:
            struct = fallback_structure(last_user_msg)
            build_pptx_file(struct, out_path)
        md = json_to_markdown(struct)
        url = f"{base_url}/v1/exports/{eid}.pptx"
        note = f"\n\n_[Модель: {chosen_model} | Задача: slides+pptx | Авто: {route['auto']}]_"
        content = (
            f"{md}\n\n---\n**Скачать презентацию (.pptx):**\n{url}\n\n"
            "Если UI на порту **3000**, ссылка ведёт на **8000** — откройте в браузере.\n"
            + note
        )
        return JSONResponse(_openai_chat_response(content, chosen_model))

    mode_suffix = ""
    if task_type == "deep_research":
        mode_suffix = DEEP_RESEARCH_SYSTEM

    system_content = (
        "Ты умный ИИ-ассистент. Отвечай на русском языке, если пользователь пишет по-русски."
        + memory_text
        + (f"\n\nДополнительный контекст:\n{extra_context}" if extra_context else "")
        + mode_suffix
    )

    has_system = any(m.get("role") == "system" for m in messages)
    if has_system:
        for m in messages:
            if m.get("role") == "system":
                prev = m.get("content", "")
                if isinstance(prev, str):
                    m["content"] = system_content + "\n\n" + prev
                else:
                    m["content"] = system_content
                break
    else:
        messages = [{"role": "system", "content": system_content}] + messages

    wants_stream = body.get("stream", False)

    if task_type == "image_gen" and IMAGE_GEN_MODEL and not has_image:
        img_url = await try_generate_image(
            last_user_msg or "image",
            MWS_API_BASE,
            HEADERS,
            IMAGE_GEN_MODEL,
        )
        if img_url:
            note = f"\n\n_[Модель: {IMAGE_GEN_MODEL} | Задача: image_gen | Авто: {route['auto']}]_"
            content = f"Сгенерировано изображение:\n\n![image]({img_url}){note}"
            return JSONResponse(_openai_chat_response(content, IMAGE_GEN_MODEL))

    mws_body = {
        "model": chosen_model,
        "messages": messages,
        "temperature": body.get("temperature", 0.7),
        "max_tokens": body.get("max_tokens", 2048),
        "stream": wants_stream,
    }
    if body.get("presence_penalty"):
        mws_body["presence_penalty"] = body["presence_penalty"]
    if body.get("frequency_penalty"):
        mws_body["frequency_penalty"] = body["frequency_penalty"]
    if user_id and user_id != "default_user":
        mws_body["user"] = user_id

    api_timeout = (
        httpx.Timeout(300.0, connect=45.0)
        if task_type == "deep_research"
        else httpx.Timeout(120.0, connect=30.0)
    )
    if task_type == "deep_research":
        mws_body["max_tokens"] = max(int(mws_body.get("max_tokens") or 2048), 4096)

    if mws_body["stream"]:
        stream_note = (
            f"\n\n_[Модель: {chosen_model} | Задача: {task_type} | Авто: {route['auto']}]_"
        )

        async def stream_response():
            extra_needed = True
            async with httpx.AsyncClient(timeout=api_timeout) as client:
                async with client.stream(
                    "POST",
                    f"{MWS_API_BASE}/chat/completions",
                    json=mws_body,
                    headers=HEADERS,
                ) as resp:
                    if resp.status_code != 200:
                        err_raw = (await resp.aread()).decode("utf-8", errors="replace")[
                            :2500
                        ]
                        err_payload = {
                            "error": {
                                "message": f"MWS вернул {resp.status_code}: {err_raw}",
                                "type": "upstream_error",
                                "code": resp.status_code,
                            }
                        }
                        yield (
                            "data: "
                            + json.dumps(err_payload, ensure_ascii=False)
                            + "\n\n"
                        ).encode("utf-8")
                        yield b"data: [DONE]\n\n"
                        return

                    async for line in resp.aiter_lines():
                        s = line.strip()
                        if (
                            extra_needed
                            and s.startswith("data:")
                            and "[DONE]" in s
                        ):
                            footer_chunk = {
                                "id": "chatcmpl-router-footer",
                                "object": "chat.completion.chunk",
                                "created": 0,
                                "model": chosen_model,
                                "choices": [
                                    {
                                        "index": 0,
                                        "delta": {"content": stream_note},
                                        "finish_reason": None,
                                    }
                                ],
                            }
                            yield (
                                "data: "
                                + json.dumps(footer_chunk, ensure_ascii=False)
                                + "\n\n"
                            ).encode("utf-8")
                            extra_needed = False
                        yield (line + "\n").encode("utf-8")

        return StreamingResponse(stream_response(), media_type="text/event-stream")

    async with httpx.AsyncClient(timeout=api_timeout) as client:
        resp = await client.post(
            f"{MWS_API_BASE}/chat/completions",
            json=mws_body,
            headers=HEADERS,
        )

    try:
        result = resp.json()
    except Exception:
        return JSONResponse(
            {"error": {"message": resp.text[:500], "type": "upstream_error"}},
            status_code=resp.status_code if resp.status_code != 200 else 502,
        )

    if resp.status_code != 200:
        return JSONResponse(result, status_code=resp.status_code)

    if "choices" in result and result["choices"]:
        note = f"\n\n_[Модель: {chosen_model} | Задача: {task_type} | Авто: {route['auto']}]_"
        msg = result["choices"][0].get("message", {})
        if msg.get("content"):
            result["choices"][0]["message"]["content"] += note

    return JSONResponse(result)


@app.post("/v1/upload")
async def upload_file(file: UploadFile = File(...)):
    content = await file.read()
    text = parse_file(file.filename, content)
    return {"filename": file.filename, "extracted_text": text}


@app.get("/v1/exports/{file_id}")
async def download_pptx_export(file_id: str):
    if not _PPTX_ID.match(file_id):
        return JSONResponse({"error": "invalid file id"}, status_code=404)
    path = EXPORTS_DIR / file_id
    if not path.is_file():
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(
        path,
        filename="presentation.pptx",
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )


@app.post("/v1/embeddings")
async def embeddings_proxy(request: Request):
    body = await request.json()
    body = dict(body)
    body["model"] = body.get("model") or "bge-m3"
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{MWS_API_BASE}/embeddings",
            json=body,
            headers=HEADERS,
        )
    try:
        data = resp.json()
    except Exception:
        return JSONResponse({"error": resp.text[:300]}, status_code=502)
    return JSONResponse(data, status_code=resp.status_code)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "MWS GPT Router"}
