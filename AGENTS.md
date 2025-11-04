# AGENTS.md — Guide for AI Agents & Collaborators

This document is a "constitution" for development on this project, ensuring that human and AI collaborators work coherently and maintain quality.

## Project Mission

Build a **local RAG chatbot** that answers questions about ECM replacement using OCR'd internal documents, with proper ACL enforcement and citations.

## Current Status (as of Nov 4, 2025)

✅ **Phase 0 Complete:**
- 262 PDFs processed via `ocr_prepare.py`
- 58 scanned PDFs → OCR'd with Tesseract
- 204 PDFs → pass-through (already had text)
- Output: `C:\ecm-staging\04_text_ready` + inventory.csv

✅ **Phase 1 Complete:**
- **252 documents indexed** (53 PDFs + 199 emails)
- **1,471 text chunks** with OpenAI embeddings (text-embedding-3-small, 1536d)
- Production-ready pipeline with memory optimization and resume capability
- Tools: `/ingest_pool.py`, `/rebuild_vectors.py`

✅ **Phase 2 Complete:**
- LLM integration (`api/llm.py` + `api/answer_generator.py`)
- Full text storage in Qdrant (no dual-lookup architecture)
- GPT-4o-mini responding with contextual answers and citations

✅ **Phase 3 Complete:**
- Next.js 14 frontend with chat UI deployed locally
- Real-time chat interface with expandable citations
- Frontend on port 3000, backend on port 8000

✅ **Phase 3b Complete (Nov 3-4, 2025):**
- **Text file (.txt) ingestion support** for Teams call transcripts
- **3 transcripts indexed**: box, opentext, newgen discovery calls (72 chunks)
- **255 total documents** (53 PDFs + 199 emails + 3 transcripts)
- **1,543 total chunks** (1,471 + 72 from transcripts)
- Incremental ingestion: skips already-processed files
- CLI: `python ingest_pool.py --text-dir <path> --max-text N`

💡 **Next Consideration:** Streaming response implementation (6/10 difficulty, 2-3 hours)

## Key Principles

### 1. **Documentation-First Development**

- **Every new file/module must include**:
  - Module docstring explaining purpose
  - Function docstrings with inputs/outputs
  - Inline comments for non-obvious logic
  
- **Update docs when you change code**:
  - `PROJECT_STRUCTURE.md` if architecture changes
  - `README.md` if setup/paths change
  - Add comments in code if logic is complex

### 2. **Git Hygiene**

- **Commit frequently** — aim for 1 commit per meaningful feature/fix
- **Use clear commit messages**:
  ```
  ✅ Good:   "Add Postgres schema for documents and chunks"
  ❌ Bad:    "Fix stuff" or "WIP"
  ```
- **Branch convention**: `feature/feature-name` or `fix/issue-name`
- **Always push after committing** — enables hand-offs to other agents

### 3. **Code Style & Structure**

- **Language**: Python 3.11+ for backend, TypeScript/React for frontend
- **Formatting**: Use `black` for Python, `prettier` for JS/TS
- **Imports**: Keep them organized (stdlib → third-party → local)
- **Type hints**: Required for Python functions; use them liberally
- **Configuration**: Use `config.py` for env-based settings (no hardcoded paths)

### 4. **Testing & Validation**

- **Before committing**, run:
  - `python -m pytest` (if tests exist)
  - Type checking: `mypy api/` (optional but encouraged)
  - Lint: `pylint api/` or `black --check api/`
  
- **Manual testing for Phase 1**:
  - Can connect to local Postgres?
  - Can ingest a small batch of PDFs?
  - Can query and get results?

### 5. **Local Environment Setup**

All agents should assume the following environment:

| Variable | Value | Source |
|----------|-------|--------|
| `POSTGRES_URL` | `postgresql://user:pass@localhost:5432/ecm_rag` | docker-compose |
| `QDRANT_URL` | `http://localhost:6333` | docker-compose |
| `OCR_OUTPUT_DIR` | `C:\ecm-staging\04_text_ready` | ocr_prepare.py output |
| `INVENTORY_CSV` | `C:\ecm-staging\inventory.csv` | ocr_prepare.py output |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` (local Hugging Face) | – |

See `api/config.py` for how these are loaded.

## Development Workflow for AI Agents

### When Picking Up a Task

1. **Read the todo list** (in manage_todo_list)
2. **Read PROJECT_STRUCTURE.md** to understand the current architecture
3. **Read AGENTS.md** (this file) to understand conventions
4. **Check the current branch**: `git branch -a` (should be on `main` or feature branch)
5. **Read relevant source files** to understand context

### When Building a New Component

Example: Building `db.py`

```python
# api/db.py
"""
Postgres schema and ORM models for ECM RAG chatbot.

Tables:
  - documents: Source PDF metadata + ACLs
  - chunks: Text chunks with embeddings
  - users: User profiles + departments
  - acl_rules: Define which users can access which departments

Connections use sqlalchemy with async support.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
# ... rest of code
```

**Steps:**
1. Write clear module docstring
2. Define schema + models
3. Test connection locally with `docker-compose up -d`
4. Add to `requirements.txt` if new dependencies
5. Update `PROJECT_STRUCTURE.md` with what was built
6. Commit: `git commit -m "Add Postgres schema (documents, chunks, acl_rules)"`
7. Push: `git push origin main` (or feature branch)

### When Debugging

- **Check logs**: FastAPI logs → Postgres connection issues
- **Check docker**: `docker-compose ps` — are containers running?
- **Check env**: Print `api/config.py` values to ensure they're loaded
- **Check paths**: Ensure `C:\ecm-staging\04_text_ready` has PDFs before ingesting

### When Handing Off to Another Agent

1. **Push all uncommitted work**
2. **Update todo list** with completed tasks
3. **Leave a note in the last commit** about what's next:
   ```
   git commit -m "WIP: db.py schema complete, next: ingest_pdf.py for document loading"
   ```
4. **Update AGENTS.md current status** if phase changes

## Multi-Source Ingestion Strategy

### Supported Source Types
1. **PDFs** – OCR'd and text-based documents (current)
2. **Outlook Emails** – .msg files with subject, body, attachments
3. **Future**: Word docs, spreadsheets, Teams chat exports

### Architecture Principles
- **Extensible**: Each source type has its own extractor module
- **Unified pipeline**: All sources → chunks → embeddings → Qdrant + Postgres
- **Metadata tracking**: `source_type` field in Document model to distinguish origins
- **ACL by folder**: Emails in `Outlook/Claims/` → department="Claims"

### Adding a New Source Type
Example: Adding support for Word documents

```python
# api/extractors/word_extractor.py
def extract_from_docx(file_path: Path) -> dict:
    """Extract text from .docx file."""
    from docx import Document
    doc = Document(file_path)
    text = "\n".join([p.text for p in doc.paragraphs])
    return {
        "text": text,
        "title": file_path.stem,
        "metadata": {"source_type": "word"}
    }

# Then in ingest.py: add to supported_formats list
```

## Phase 1 Detailed Breakdown

### `api/config.py`
- Load env vars (POSTGRES_URL, QDRANT_URL, etc.)
- Define paths for OCR output, inventory CSV
- Embedding model name (BGE)

### `api/db.py`
- SQLAlchemy models: `Document`, `Chunk`, `User`, `ACLRule`
- Session factory + connection management
- Methods: `get_or_create_user()`, `add_chunk()`, `get_user_accessible_chunks()`

### `api/ingest_pdf.py`
- Read PDFs from `C:\ecm-staging\04_text_ready`
- Chunk text (size: ~300 tokens, overlap: ~50 tokens) — adjust if needed
- Embed chunks using BGE model (via `sentence-transformers`)
- Write to Qdrant (vector) + Postgres (metadata)
- Log progress (which PDFs, how many chunks, errors)

### `api/retriever.py`
- `hybrid_search()` — combine vector + BM25 search
- `rerank()` — optional CrossEncoder reranking
- `filter_by_acl()` — ensure user can access results

### `api/main.py`
- FastAPI app with middleware (logging, auth)
- `@app.get("/health")` — returns status
- `@app.post("/ingest")` — trigger document ingestion
- `@app.post("/query")` — RAG query endpoint
- Auth middleware (demo token for now)

## Common Tasks & How to Approach Them

### Task: "Add support for OpenAI embeddings"
- Modify `config.py` to add `OPENAI_API_KEY`
- Update `ingest_pdf.py` to switch embedding model
- Re-ingest with flag: `python -m api.ingest_pdf --force-reindex`
- Commit: `git commit -m "Add OpenAI embedding support (configurable)"`

### Task: "Improve chunking strategy"
- Test different chunk sizes/overlaps in `ingest_pdf.py`
- Log results to CSV (chunk count, coverage, etc.)
- Decide on best params and commit
- Commit: `git commit -m "Optimize chunking: 300 tokens, 50 overlap (tested)"`

### Task: "Add user authentication"
- Expand `security.py` with JWT validation
- Update `main.py` middleware to extract user from token
- Commit: `git commit -m "Add JWT auth middleware (demo Azure AD ready)"`

## Documentation Maintenance

### When to Update Files

| File | When | Example |
|------|------|---------|
| `README.md` | Setup changes, new endpoints | New env var, Docker service |
| `PROJECT_STRUCTURE.md` | Architecture changes, phase progress | Completed Phase 1, starting Phase 2 |
| `AGENTS.md` | Development conventions, status | New embedding model, auth approach |
| Code comments | Non-obvious logic, edge cases | "Skip chunks <50 tokens to reduce noise" |

## Red Flags & How to Handle Them

| Red Flag | Action |
|----------|--------|
| Uncommitted code | Commit immediately with clear message |
| Missing docstrings | Add before merging (or commit with "docs: add docstrings") |
| Hardcoded paths | Move to `config.py` and commit |
| No tests, unclear if it works | Manual testing + document results in commit |
| Postgres errors | Check docker, check connection string, check schema |
| Vector search returns nothing | Re-run ingestion with `--force-reindex` or use `rebuild_vectors.py` |
| Memory spike during ingestion | Lower `--workers` count, check `EMBEDDING_MINI_BATCH_SIZE` |
| Transaction rollback / data loss | **NEVER use delete-then-recreate patterns**—use `TRUNCATE` or upserts |
| Stale Qdrant vectors after DB clear | Run `USE_SQLITE=false python rebuild_vectors.py` |

## Questions to Ask Before Committing

- [ ] Does the code match the project style?
- [ ] Are functions documented (docstrings)?
- [ ] Is the commit message clear?
- [ ] Did I test this locally?
- [ ] Should I update README/PROJECT_STRUCTURE/AGENTS?
- [ ] Are there any hardcoded values that should be in config.py?

## Next AI Agent Session

When a new AI agent picks up this project:

1. **Read in this order**:
   - `README.md` (overview + quick start)
   - `PROJECT_STRUCTURE.md` (architecture)
   - `AGENTS.md` (this file)
   - Check `git log` for recent work

2. **Verify environment**:
   ```bash
   docker-compose ps  # Are Qdrant + Postgres running?
   ls C:\ecm-staging\04_text_ready  # Do PDFs exist?
   python -c "import config; print(config.POSTGRES_URL)"  # Is config working?
   ```

3. **Check what's done** by reading recent commits:
   ```bash
   git log --oneline -20
   ```

4. **Pick next todo** from manage_todo_list or `PROJECT_STRUCTURE.md`

5. **Start working** — and commit frequently!

---

**Remember**: Clear documentation + frequent commits = smooth hand-offs between agents. Good luck! 🚀
