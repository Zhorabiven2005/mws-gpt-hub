import httpx

async def try_generate_image(prompt, api_base, headers, model):
    if not model:
        return None
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                f"{api_base.rstrip('/')}/images/generations",
                json={"model": model, "prompt": (prompt or "")[:4000], "n": 1},
                headers=headers,
            )
            if r.status_code != 200:
                return None
            data = r.json()
            arr = data.get("data") or []
            if not arr:
                return None
            item = arr[0]
            return item.get("url") or (f"data:image/png;base64,{item['b64_json']}" if item.get("b64_json") else None)
    except Exception:
        return None