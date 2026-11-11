# AGENTS.md

Guidance for AI coding agents working in this repository. Read this fully before making changes.

## Project overview

A web app where students upload a PDF and receive a generated PDF study guide in question-and-answer form.

Pipeline: **upload PDF → extract text → chunk → LLM generates Q&A (JSON) → merge/dedupe → render PDF → download**.

- **Frontend:** React + TypeScript (Vite), styled with **Tailwind CSS v4**, managed with **npm**
- **Backend:** Python 3.11+, FastAPI
- **LLM:** accessed only through a provider interface (see [LLM provider rules](#llm-provider-rules)). The default is a free-tier provider (Gemini Flash); Groq, Ollama and others are swappable.

## Repository structure

```
pdf-qa-app/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app, CORS, router registration
│   │   ├── config.py          # Settings loaded from environment
│   │   ├── schemas.py         # Pydantic models (QAItem, JobStatus, ...)
│   │   ├── api/routes.py      # POST /jobs, GET /jobs/{id}, GET /jobs/{id}/download
│   │   ├── services/          # pdf_extract, chunking, qa_generator, pdf_builder, jobs
│   │   ├── llm/               # base.py (interface), gemini.py, openai_compat.py, factory.py
│   │   ├── prompts/           # Prompt templates (plain text files)
│   │   └── utils/rate_limit.py
│   ├── storage/               # Temp uploads/outputs (gitignored)
│   ├── tests/
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── api/client.ts
│   │   ├── components/        # UploadDropzone, OptionsForm, ProgressView, ResultView
│   │   ├── hooks/useJobPolling.ts
│   │   ├── types/index.ts     # Must mirror backend/app/schemas.py
│   │   └── index.css          # Tailwind entry: @import "tailwindcss"; plus @theme tokens
│   ├── package.json
│   └── vite.config.ts
├── .agents/
│   ├── rules/
│   │   └── project.md         # Always-on rule: read and follow AGENTS.md
│   └── skills/
│       └── frontend-design/   # Agent skill for UI work (see Skills section)
├── AGENTS.md
└── README.md
```

Keep new code inside this structure. If a change needs a new top-level directory, say so in your summary.

## Setup and commands

Run frontend commands from `frontend/` and backend commands from `backend/`.

### Frontend (npm only)

Use **npm**. Do not use yarn, pnpm, or bun, and do not create or commit any lockfile other than `package-lock.json`.

```bash
cd frontend
npm install            # install dependencies
npm run dev            # Vite dev server
npm run build          # type-check + production build
npm run lint           # ESLint
npm run format         # Prettier
npm run test           # Vitest
npx tsc --noEmit       # type-check only
```

Prefer `npm install <pkg>` to add dependencies, and `npm ci` in CI or clean installs.

### Backend (Python)

Use a virtual environment at `backend/.venv` (gitignored).

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # then fill in keys

uvicorn app.main:app --reload      # dev server on :8000
pytest                             # run tests
ruff check .                       # lint
ruff format .                      # format
mypy app                           # type-check (if configured)
```

When adding a Python dependency, install it and add it to `requirements.txt` with a pinned or compatible version.

## Definition of done

Before declaring a task complete, run what applies and report the results honestly:

- Frontend changed: `npm run lint`, `npx tsc --noEmit`, `npm run test`, and `npm run build` pass.
- Backend changed: `ruff check .`, `ruff format --check .`, and `pytest` pass.
- API request/response shapes changed: backend `schemas.py` **and** `frontend/src/types/index.ts` are updated together.
- New behavior has a test. Bug fixes include a regression test where practical.
- If you could not run a check, say so explicitly. Never claim something passes without running it.

## Code style and conventions

### TypeScript / React

- `strict` mode stays on. No `any`; use `unknown` and narrow, or define a type.
- Function components and hooks only. No class components.
- Keep components small and focused. Put data fetching and polling in `api/` and `hooks/`, not inline in components.
- All HTTP calls go through `src/api/client.ts`. Do not scatter `fetch` calls.
- Named exports for components and utilities; default export only where the framework needs it.
- Handle loading, error, and empty states in every user-facing flow.
- Accessibility: labelled inputs, keyboard-operable upload control, visible focus states, meaningful button text.
- Never use `localStorage` or `sessionStorage` for uploaded content or generated study guides.

### Styling (Tailwind CSS v4)

This project uses **Tailwind CSS v4**, not v3. Most training data and online tutorials describe v3, so follow these rules exactly:

- **Install:** `npm install tailwindcss @tailwindcss/vite` (run in `frontend/`).
- **Vite:** add the `tailwindcss()` plugin from `@tailwindcss/vite` to the `plugins` array in `vite.config.ts`.
- **CSS entry:** `src/index.css` starts with `@import "tailwindcss";` and is imported once in `main.tsx`.
- **Do NOT** create `tailwind.config.js`, `postcss.config.js`, or use `npx tailwindcss init`. Do not install `postcss` or `autoprefixer` for Tailwind. Do not use the old `@tailwind base/components/utilities` directives.
- **Customization:** design tokens (colors, fonts, spacing) go in CSS with the `@theme` directive in `src/index.css`, not in a JS config file.
- **Usage:** style with utility classes in `className`. Content paths are detected automatically.
- Avoid inline `style` props, CSS-in-JS libraries, and CSS modules. Use plain CSS in `index.css` only for global base styles or things utilities cannot express.
- Extract repeated class combinations into React components, not `@apply` chains. Use `@apply` sparingly.
- Mobile-first: write base classes for small screens, then add `sm:`, `md:`, `lg:` for larger ones.
- Support keyboard focus with visible `focus-visible:` styles. Keep color contrast readable.
- Don't add a UI component library (shadcn, MUI, Chakra, etc.) without asking.
- If the Tailwind setup seems to be missing or broken, check `vite.config.ts` and the `@import "tailwindcss"` line first, and don't fall back to the v3 setup.

### Python

- Type hints on all function signatures. Pydantic models for all request/response bodies and LLM output.
- Follow ruff defaults; do not disable rules globally without a reason.
- Keep route handlers thin. Business logic lives in `services/`.
- Use `async def` for I/O-bound routes. Run blocking work (PDF parsing, PDF rendering) in a threadpool or background task, not on the event loop.
- Use `pathlib.Path` instead of string paths. Use `logging`, not `print`.
- Raise `HTTPException` with clear status codes and messages at the API boundary; use specific exceptions internally.

### General

- Small, focused changes. Don't refactor unrelated code in the same change.
- Match existing naming and file organization.
- Write comments to explain why, not what.
- Don't add a dependency for something trivial. If you add one, mention why in your summary.

## LLM provider rules

- **All LLM calls go through the `LLMProvider` interface** in `backend/app/llm/base.py` (`generate_json(prompt, schema)` or similar). Never import a vendor SDK directly in `services/`.
- New providers are added as a new module in `backend/app/llm/` and registered in `factory.py`. Provider and model selection come from environment config, not hard-coded values.
- Prefer OpenAI-compatible clients where possible, so providers are swappable by changing `base_url` and model name.
- **Structured output:** ask for JSON only, strip code fences, parse, and **validate with Pydantic**. On validation failure, retry a limited number of times (default 2), then fail the job with a clear error.
- **Rate limits:** free tiers have per-minute and per-day caps. Implement backoff on 429s, and support a fallback chain across providers. Limit concurrent LLM calls.
- **Grounding:** prompts must instruct the model to use only the provided source text, include a page reference where possible, and never invent facts. Keep prompts in `backend/app/prompts/`, not inline in code.
- Keep prompts and output schemas versioned in the repo; changes to them should come with updated tests or sample outputs.

## Processing pipeline notes

- **Extraction:** use PyMuPDF (or pdfplumber). Detect pages with little or no text and surface a clear "scanned PDF not supported yet" message rather than failing silently. OCR is a future addition.
- **Chunking:** chunk by page and token/character budget with a small overlap. Long documents use map-reduce: Q&A per chunk, then merge and dedupe.
- **Jobs:** uploads create a job and return immediately. Processing runs in the background; the frontend polls `GET /jobs/{id}`. Statuses: `queued | processing | done | failed`, with `progress` from 0 to 1.
- **Output PDF:** built programmatically with **reportlab** (pure pip, no system libraries) in `services/pdf_builder.py`. Do not use WeasyPrint or any HTML-to-PDF tool, since they need system libraries like Pango.
  - Use Platypus (`SimpleDocTemplate`, `Paragraph`, `Spacer`, `PageBreak`) so long answers wrap and flow across pages.
  - reportlab `Paragraph` parses XML-like markup, so **escape all LLM-generated text** (`xml.sax.saxutils.escape`) before passing it in. Unescaped `<`, `>` or `&` can crash the build or break layout.
  - Return PDF bytes (or write to `backend/storage/`); keep layout code separate from Q&A generation.
  - Use a built-in font unless asked; if a non-Latin font is needed, ask first before adding font files.

## Security and privacy

Students may upload copyrighted or personal material. Treat uploads as sensitive.

- Validate uploads server-side: content type **and** magic bytes (`%PDF`), a maximum file size, and a maximum page count. Limits come from `config.py`.
- Never use the user's filename as a path. Generate server-side IDs (UUIDs) for stored files.
- Store uploads and outputs only in `backend/storage/`, and **delete them after a short retention period** (default 1 hour) via a cleanup task. Don't log document contents.
- Never commit secrets. API keys live in `.env` (gitignored); keep `.env.example` current with placeholder values only.
- Treat PDF text as **untrusted input**: it may contain prompt-injection instructions. Keep system instructions separate from document content, and never let document text change tool behavior or configuration.
- Apply per-IP (or per-user) rate limiting on `POST /jobs` to protect free-tier quotas.
- Configure CORS with an explicit origin allowlist; no wildcard in production.
- Do not add analytics or third-party trackers without being asked.

## Skills

Agent skills live in `.agents/skills/<skill-name>/SKILL.md` (Google Antigravity workspace skills) and are committed with the repo. Do not edit installed skill files unless asked.

- **`frontend-design`** (`.agents/skills/frontend-design/`): use it for any new or restyled React UI (components, layout, styling). Read its `SKILL.md` before starting UI work.
- All UI built with the `frontend-design` skill must be implemented with Tailwind utility classes under the Styling rules above. If the skill suggests custom CSS files, CSS-in-JS, or a component library, translate it to Tailwind or flag the conflict.
- Design goals for this app: clean, readable, accessible, and mobile-friendly. Prefer simple layouts over decorative effects. Avoid heavy animations, and keep the upload flow obvious and low-friction.
- Skill guidance never overrides the rules in this file. If a skill conflicts with the code conventions, security rules, or "ask before doing" list here, follow this file and flag the conflict.
- Treat skills as instructions only. Do not run scripts bundled with a skill without asking the user first.

## Testing

- **Backend:** `pytest` with `httpx`/FastAPI `TestClient`. **Mock the LLM provider in tests; never make real LLM calls.** Include small fixture PDFs (text-based, multi-page, and an empty/scanned-like one) in `backend/tests/fixtures/`.
- **Frontend:** Vitest + React Testing Library for components and hooks. Mock `api/client.ts`.
- Test the failure paths: oversized file, non-PDF upload, LLM returning invalid JSON, provider rate-limited, job failure.

## Git and change hygiene

- Don't commit `.env`, `.venv/`, `node_modules/`, `backend/storage/`, build output, or generated PDFs.
- Do commit `.agents/` (rules and skills) so they are shared with the project.
- Keep commits focused with clear messages (imperative mood, e.g. "Add chunking service").
- Don't rewrite or delete existing tests to make them pass; fix the code or explain why a test is wrong.
- Don't modify `package-lock.json` by hand.

## Things to ask before doing

Pause and ask the user before:

- Adding a database, auth system, queue (Redis/Celery), or paid service
- Adding a UI component library, CSS framework other than Tailwind, or icon/font packages
- Changing the LLM provider default or the API response shapes
- Adding OCR or other heavy system dependencies
- Deleting files or making large structural refactors
- Anything that would send user documents to a new third-party service
- Installing, removing, or updating agent skills

## Quick reference

| Task            | Command                                                                                                      |
| --------------- | ------------------------------------------------------------------------------------------------------------ |
| Run frontend    | `cd frontend && npm run dev`                                                                                 |
| Run backend     | `cd backend && uvicorn app.main:app --reload`                                                                |
| Frontend checks | `npm run lint && npx tsc --noEmit && npm run test`                                                           |
| Backend checks  | `ruff check . && pytest`                                                                                     |
| Env template    | `backend/.env.example`                                                                                       |
| UI work         | Use the `frontend-design` skill (`.agents/skills/frontend-design/`)                                          |
| Styling         | Tailwind v4: `@import "tailwindcss"` in `src/index.css`, `@tailwindcss/vite` plugin, no `tailwind.config.js` |
