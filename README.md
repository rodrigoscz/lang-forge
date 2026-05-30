# lang-forge

AI SEO Lab — experimental playground for SEO research on AI Overviews and generative search.

## Thesis

**Todo es lenguaje.**

This lab explores how content structure, semantic HTML, and linguistic patterns affect citation rates in AI Overviews.

## Stack

- **Frontend**: Astro (static content, embedded visualizations)
- **Backend**: Python FastAPI (DataforSEO integration, data processing)
- **Storage**: SQLite
- **Package manager**: pnpm

## Structure

- `frontend/` — Astro static site for experiment writeups and variant pages.
- `backend/` — FastAPI service, SQLite schema, and experiment lifecycle CLI.
- `experiments/` — numbered, folder-based experiment specs, scripts, and data.
- `data/` — local SQLite databases and raw shared data exports.
- `outputs/` — generated diagrams, charts, and social cards.

## Backend Quick Start

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

The API exposes `GET /health` and initializes the SQLite schema from `backend/app/db/schema.sql` on startup.
Dependencies are pinned in `requirements.txt`; audit them with `python -m pip_audit -r requirements.txt`.

## First Experiment

**Content Structure vs AI Overview Citations**

Testing how semantic HTML and heading hierarchy affect citation rates in AI Overviews using 80 page variants.

## License

MIT
