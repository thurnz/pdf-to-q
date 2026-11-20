# PDF → Q&A Study Guide

A full-stack web application where students upload lecture notes, textbook chapters, or reading materials in PDF format and receive a concise, beautifully formatted PDF study guide with questions and answers.

---

## How It Works

1. **Upload & Validation**: Students select or drag-and-drop a PDF. The frontend validates the file extension and size; the backend verifies the `%PDF` magic bytes, enforces size limits (default 20 MB), and checks page counts (default 200 pages).
2. **Text Extraction**: PyMuPDF extracts text page-by-page. Scanned or image-only PDFs with little extractable text are rejected immediately with a friendly explanation.
3. **Chunking & Concurrency Limiting**: Long documents are split into logical chunks respecting page boundaries and character budgets (up to 30,000 chars per chunk, capped at 12 chunks). Processing jobs are throttled with an in-memory concurrency semaphore (default 2 concurrent jobs) to protect API rate limits; extra submissions remain queued safely until a slot frees up.
4. **Structured Q&A Generation**: Text chunks are passed to the configured LLM (Google Gemini Flash by default) to generate structured questions and answers. The backend enforces JSON schema validation with automatic retries and exponential backoff on transient errors (429 rate limits, 500/503 service issues), with optional fallback model support.
5. **Study Guide PDF Generation**: Results are merged, deduplicated, sorted by page reference, and built into a publication-quality PDF using ReportLab Platypus.
6. **Download & Privacy Cleanup**: The student downloads `study-guide.pdf`. The uploaded source PDF is permanently deleted immediately upon completion. Generated study guides are purged after a 1-hour retention window.

---

## Requirements

- **Python 3.11+**
- **Node.js 18+** and **npm**
- **Google Gemini API Key** (from [Google AI Studio](https://aistudio.google.com/)) or an OpenAI-compatible API key (Groq, Ollama, etc.)

---

## Setup and Running

### 1. Backend Setup

```bash
cd backend

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate       # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
```

Edit `backend/.env` with your API key and chosen model:
```dotenv
GEMINI_API_KEY=your-gemini-api-key-here
GEMINI_MODEL=gemini-2.5-flash
```

> **Tip**: You can list the models available to your Gemini API key by running:
> ```bash
> python scripts/list_models.py
> ```

Start the backend development server:
```bash
uvicorn app.main:app --reload
```
The backend API is now running at `http://127.0.0.1:8000`.

### 2. Frontend Setup

In a new terminal window:

```bash
cd frontend

# Install dependencies
npm install

# Start Vite development server
npm run dev
```
The frontend web application is now available at `http://localhost:5173`.

---

## Environment Variables Reference

Configure these settings in `backend/.env`:

| Variable | Description | Default |
| :--- | :--- | :--- |
| `LLM_PROVIDER` | LLM provider to use (`gemini` or `openai_compat`) | `gemini` |
| `GEMINI_API_KEY` | API key from Google AI Studio | *(required for Gemini)* |
| `GEMINI_MODEL` | Primary Gemini model name (e.g. `gemini-2.5-flash`) | *(required, no default)* |
| `GEMINI_FALLBACK_MODEL` | Secondary Gemini model used if primary fails with 503/429 | `""` *(disabled)* |
| `LLM_MAX_ATTEMPTS` | Maximum retry attempts for transient API errors | `4` |
| `LLM_RETRY_BASE_SECONDS` | Initial backoff delay for retries (in seconds) | `2.0` |
| `OPENAI_COMPAT_BASE_URL` | Base URL for OpenAI-compatible providers | `""` |
| `OPENAI_COMPAT_API_KEY` | API key for OpenAI-compatible providers | `""` |
| `MAX_FILE_SIZE_MB` | Maximum allowed uploaded PDF size in megabytes | `20` |
| `MAX_PAGE_COUNT` | Maximum allowed pages per uploaded PDF | `200` |
| `CHUNK_MAX_CHARS` | Maximum character budget per chunk | `30000` |
| `MAX_CHUNKS` | Maximum chunk count per document before failing as too long | `12` |
| `CHUNK_DELAY_SECONDS` | Delay between consecutive chunk requests (in seconds) | `0.0` |
| `RATE_LIMIT_PER_MINUTE` | Maximum uploads allowed per minute per client IP | `5` |
| `MAX_CONCURRENT_JOBS` | Maximum simultaneous jobs processed concurrently | `2` |
| `FILE_RETENTION_SECONDS`| Time until generated study guide outputs are deleted (in seconds) | `3600` *(1 hour)* |
| `ALLOWED_ORIGINS` | Comma-separated list of allowed CORS origins | `http://localhost:5173, http://127.0.0.1:5173` |

---

## System Limits

- **File Size**: Up to 20 MB per PDF upload.
- **Page Count**: Up to 200 pages per document.
- **Chunking Limit**: Documents requiring more than 12 chunks (~360,000 characters) are rejected with a request to upload a smaller chapter or section.
- **Rate Limit**: 5 upload requests per minute per IP address.
- **Concurrency**: 2 simultaneous processing pipelines. Extra submissions remain safely queued until a worker slot is released.

---

## Privacy & Security

- **Immediate Upload Purge**: Uploaded source PDFs are stored temporarily under an anonymized UUID filename in `backend/storage/uploads/` and are **permanently deleted from disk as soon as processing finishes** (on both success and failure).
- **Automated Output Retention**: Generated study guides stored in `backend/storage/outputs/` are automatically deleted after 1 hour by a background cleanup task.
- **Safe Downloads**: Generated files are served with a generic, safe header: `Content-Disposition: attachment; filename="study-guide.pdf"`. User filenames and document text are never reflected in download paths or headers.
- **Zero Document Logging**: The application never logs document text, prompt contents, or original user filenames.
- **Data Sent to LLM**: Only extracted document text and question generation instructions are transmitted via encrypted HTTPS to the configured provider (Google Gemini or OpenAI-compatible endpoint). No student identifiers or uploaded filenames are sent.

---

## Troubleshooting

### 1. `Set GEMINI_MODEL in .env`
- **Cause**: `GEMINI_MODEL` is missing or empty in `backend/.env`.
- **Solution**: Set `GEMINI_MODEL` to a valid Gemini model name (e.g. `GEMINI_MODEL=gemini-2.5-flash`). Check available models with:
  ```bash
  python scripts/list_models.py
  ```

### 2. `404 Not Found: Model '<name>' not found or retired`
- **Cause**: Google periodically retires older preview and experimental model names.
- **Solution**: Run `python scripts/list_models.py` inside `backend/` to see the currently supported models for your key, then update `GEMINI_MODEL` in `.env`.

### 3. `503 Service Unavailable` or `429 Rate Limit Exceeded`
- **Cause**: Google Gemini free-tier quotas or transient service load.
- **Solution**: The backend automatically retries up to 4 times with exponential backoff and jitter. You can also configure `GEMINI_FALLBACK_MODEL` in `.env` to fall back to an alternate model, or lower `MAX_CONCURRENT_JOBS` and increase `CHUNK_DELAY_SECONDS`.

### 4. CORS Errors in Browser Console
- **Cause**: The frontend is accessing the backend from an origin not listed in `ALLOWED_ORIGINS`.
- **Solution**: Verify that `backend/.env` contains your frontend port in `ALLOWED_ORIGINS` (e.g. `ALLOWED_ORIGINS=http://localhost:5173, http://127.0.0.1:5173`).

---

## Development Checks

Before committing changes, ensure all verification suites pass:

```bash
# Backend checks
cd backend
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pytest

# Frontend checks
cd ../frontend
npm run lint
npx tsc --noEmit
npm run test
npm run build
```

---

## Deployment

The recommended setup is **Render** for the backend (free tier with auto-spin-up) and any static host (Netlify, Vercel, GitHub Pages, Render Static Sites) for the frontend.

> [!IMPORTANT]
> Never commit `.env` files. Set secrets in your host's environment dashboard.

### Deploy Order

Always deploy the **backend first** so the backend URL is available when building the frontend.

---

### Backend on Render (Python Web Service)

| Render Setting | Value |
| :--- | :--- |
| **Runtime** | Python 3 |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips='*'` |
| **Working Directory** | `backend` |

> [!NOTE]
> `--proxy-headers` tells Uvicorn to trust `X-Forwarded-For` headers injected by Render's load balancer, so per-IP rate limiting uses the real client IP, not the proxy's IP.
> `--forwarded-allow-ips='*'` trusts all upstream proxies — safe on Render, which controls the network edge.

**Required environment variables** (set in Render's Environment tab):

| Variable | Value |
| :--- | :--- |
| `GEMINI_API_KEY` | Your Google AI Studio key |
| `GEMINI_MODEL` | A current model name, e.g. `gemini-2.5-flash` |
| `ALLOWED_ORIGINS` | Comma-separated list of your frontend URLs, e.g. `https://my-app.netlify.app` |

All other backend settings have sensible defaults and are optional. See the [Environment Variables Reference](#environment-variables-reference) table for the full list.

---

### Frontend on a Static Host (Netlify / Vercel / GitHub Pages)

**Required build-time variable** — set this in your host's build environment before `npm run build`:

| Variable | Value |
| :--- | :--- |
| `VITE_API_BASE_URL` | Your deployed backend URL, e.g. `https://my-backend.onrender.com` |

> [!CAUTION]
> The build will fail with a clear error message if `VITE_API_BASE_URL` is not set in production mode. This is intentional — a missing URL would silently default to `localhost` and break all API calls in production.

**Example build commands:**

```bash
# Netlify / Vercel (set env var in dashboard, then):
npm run build

# Or inline for one-off deploys:
VITE_API_BASE_URL=https://my-backend.onrender.com npm run build
```

**Static site settings:**

| Setting | Value |
| :--- | :--- |
| **Build Command** | `npm run build` |
| **Publish Directory** | `frontend/dist` |
| **Base Directory** | `frontend` (or set in repo root with `cd frontend &&` prefix) |
