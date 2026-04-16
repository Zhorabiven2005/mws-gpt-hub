# AI Workspace (MWS GPT Hub)

Единое AI-пространство для решения задач через чат-интерфейс с поддержкой мультимодальности, автоматического выбора моделей и памяти.

## Возможности

* Автоматический выбор модели (router)
* Единый чат-интерфейс (OpenWebUI)
* Поддержка:

  * текстовых запросов
  * изображений
  * аудио и голоса
  * файлов
* Долгосрочная память (embeddings)
* Инструменты:

  * web search
  * анализ файлов
  * обработка изображений
* Ручной выбор модели

## Архитектура

User → Chat UI → Router → Tool / Model → MWS GPT API → Response

## Технологии

* Python (FastAPI)
* OpenWebUI
* MWS GPT API
* Docker / Docker Compose

## Запуск

```bash
git clone https://github.com/Zhorabiven2005/-AI-hub-
cd -AI-hub-
docker compose up
```

После запуска:
http://localhost:3000

## Сценарии

* Генерация изображений
* Анализ файлов
* Веб-поиск
* Голосовые запросы
* Контекстные ответы с учетом памяти

## Roadmap

* Улучшение router (LLM-based)
* Deep research
* Расширение инструментов
* Голосовой ассистент

## Автор

Дмитрий
