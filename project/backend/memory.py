"""
Долгосрочная память пользователя — хранит факты между сессиями.
"""
import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.getenv("MEMORY_DB_PATH", "/app/data/memory.db")


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            fact TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_context (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def save_fact(user_id: str, fact: str):
    """Сохранить факт о пользователе."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO user_memory (user_id, fact, created_at) VALUES (?, ?, ?)",
        (user_id, fact, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()


def get_facts(user_id: str) -> list[str]:
    """Получить все факты о пользователе."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT fact FROM user_memory WHERE user_id = ? ORDER BY created_at DESC LIMIT 20",
        (user_id,)
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def build_memory_prompt(user_id: str) -> str:
    """Собрать системный промпт с фактами о пользователе."""
    facts = get_facts(user_id)
    if not facts:
        return ""
    facts_text = "\n".join(f"- {f}" for f in facts)
    return f"\n\nЧто известно о пользователе из прошлых диалогов:\n{facts_text}"


def extract_and_save_facts(user_id: str, message: str):
    """
    Простая эвристика: если в сообщении есть 'меня зовут', 'я работаю', 'я люблю' —
    сохраняем как факт.
    """
    triggers = ["меня зовут", "я работаю", "я люблю", "мой проект", "я занимаюсь",
                "я из", "я живу", "моя компания", "мне нравится"]
    msg_lower = message.lower()
    for trigger in triggers:
        if trigger in msg_lower:
            save_fact(user_id, message[:200])
            break


init_db()
