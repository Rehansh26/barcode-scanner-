# Barcode Inventory

A self-hosted inventory management system built with Django, backed by PostgreSQL and Celery/Redis for background processing, with optional local LLM (Ollama) features for AI-assisted inventory insights and a retrieval-grounded chat assistant.

Track items by barcode or QR code, organize them by category and location, scan to look items up, search across your whole inventory, and print physical labels — all from a single dashboard.

## Features

- **Barcode/QR generation** — every item gets a generated Code128 barcode or QR code image on creation.
- **Scan lookup** — scan or type a barcode value to instantly pull up the matching item, with scan history logged per item.
- **Dashboard CRUD** — add/remove Categories and Locations directly from the dashboard, no admin panel required.
- **Knowledge Graph** — a dependency-free, hand-rolled force-directed graph visualizing Category ↔ Item ↔ Location relationships, with draggable nodes and click-to-navigate, plus a flat list view grouped by category.
- **AI Insights** — background-generated summaries and observations about your inventory, powered by a local/remote Ollama model.
- **RAG chat assistant** — ask natural-language questions about your inventory ("what's low on stock in the warehouse?"). A bag-of-words/TF-IDF retrieval step (`inventory/bow.py`) pulls the most relevant items before handing grounded context to the LLM, with a collapsible "Retrieved context" panel so you can see exactly what informed each answer.
- **Global search** — TF-IDF-ranked search across Items, Categories, and Locations from a search bar present on every page, with a status-keyword fallback so queries like "low stock" or "discontinued" reliably surface matches.
- **Printable labels** — generate a print-ready label (barcode/QR + item info) for a single item, or select multiple items from the dashboard and print a full label sheet in one go.
- **CSV export** — export the current inventory to CSV.

## Tech Stack

- **Backend:** Django 5.x, PostgreSQL, Celery + Redis for async tasks
- **AI:** Ollama (local or remote), bag-of-words/TF-IDF retrieval (pure Python, no numpy/scikit-learn)
- **Barcode/QR:** python-barcode, qrcode, Pillow
- **Frontend:** Django templates, vanilla JS (no build step, no frontend framework)

## Local Setup (without Docker)

1. Create and activate a virtual environment.
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill in your database credentials, Redis URL, and Ollama settings (see [Environment Variables](#environment-variables) below).
4. Create the PostgreSQL database referenced in your `.env`.
5. `python manage.py migrate`
6. `python manage.py createsuperuser`
7. `python manage.py runserver`

### Background workers

Run Redis locally (or point `REDIS_URL` at your Redis/Memurai instance), then in a separate terminal:

```bash
celery -A core worker -l info
```

> On Windows, Celery's default pool doesn't work reliably — use `celery -A core worker --pool=solo -l info` instead. The worker does not autoreload; restart it manually whenever `tasks.py` changes.

### Ollama

Set `OLLAMA_BASE_URL` to wherever your Ollama instance is reachable from the machine running the Celery worker (e.g. `http://localhost:11434` if it's on the same machine, or a LAN/VPN address if it's remote), and `OLLAMA_MODEL` to a model you've actually pulled there (check with `ollama list`). Both AI Insights and the AI Chat feature depend on this being reachable.

## Running with Docker

A `Dockerfile` and `docker-compose.yml` are included for local development and CI parity.

```bash
cp .env.example .env   # fill in real values first
docker compose up --build
```

This starts Postgres, Redis, the Django app (migrated + collected static, served via Gunicorn on port 8000), and a Celery worker. Ollama is **not** included in `docker-compose.yml` — point `OLLAMA_BASE_URL` at wherever Ollama is actually running (your host machine, e.g. `http://host.docker.internal:11434` on Mac/Windows, or a remote server).

## Environment Variables

See `.env.example` for the full list. Key variables:

| Variable | Purpose |
|---|---|
| `DJANGO_SECRET_KEY` | Django's cryptographic signing key — set a real random value in production |
| `DJANGO_DEBUG` | `True`/`False` |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated list of allowed hosts |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | PostgreSQL connection |
| `REDIS_URL` | Celery broker/result backend |
| `OLLAMA_BASE_URL` | Where Ollama is reachable from the Celery worker |
| `OLLAMA_MODEL` | Model name as pulled on the Ollama server (must exist via `ollama list`) |

## CI/CD

GitHub Actions (`.github/workflows/ci-cd.yml`) runs on every push and pull request to `main`:

1. **Test job** — spins up real Postgres and Redis service containers, installs dependencies, runs `manage.py check`, applies migrations, and runs the test suite (`inventory/tests.py`).
2. **Build & push job** — on a successful push to `main`, builds the Docker image and pushes it to GitHub Container Registry (GHCR) as `ghcr.io/<owner>/barcode-scanner:latest` and `:<commit-sha>`. No live deployment is configured yet — pulling and running the published image is a manual step for now.

To pull the latest built image once it's published:

```bash
docker pull ghcr.io/rehansh26/barcode-scanner:latest
```

(GHCR images default to private; if the package shows as private after the first push, you may need to set it to public in the repo's Packages settings, or authenticate with `docker login ghcr.io` first.)

## Media Files

Generated barcode/QR images are stored under `MEDIA_ROOT/barcodes/`. In production, serve media through a proper web server or object storage rather than Django's development server.

## Seed Data

Create at least one Category and Location (via the dashboard or `/admin/`) before generating items, so they can be assigned during barcode/item creation.
