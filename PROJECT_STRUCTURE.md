# ECM RAG Chatbot — Project Structure Manifest
**Purpose:** Provide a full picture of the architecture and current progress so that human or AI collaborators (VS Code agents, Copilot, etc.) can continue development safely.

---

## 1. Project Overview
The ECM RAG Chatbot answers internal questions about New Mexico Mutual’s ECM replacement project using company documents (RFPs, research, notes, P&P, etc.) stored in OneDrive.  
It uses a local **RAG pipeline** with:
- OCR for scanned files
- Qdrant as the vector store
- Postgres for metadata & ACLs
- FastAPI backend for retrieval
- Next.js frontend chat interface

---

## 2. Current Local Paths
| Role | Path |
|------|------|
| OneDrive Source | `C:\Users\angela\OneDrive - New Mexico Mutual\Projects\ECM Replacement Research` |
| OCR/Text Output | `C:\ecm-staging\04_text_ready` |
| Inventory File | `C:\ecm-staging\inventory.csv` |
| App Repo Root | `C:\dev\ecm-rag` *(adjust to your local repo path)* |

---

## 3. Completed Components
### ✅ Phase 0 — Document & OCR Prep
- `ocr_prepare.py` — detects scanned PDFs, OCRs them, and builds `inventory.csv`
- Produces ready-to-index corpus in `04_text_ready`
- Includes department-based ACL tagging guess logic
- Tesseract + Ghostscript verified locally

---

## 4. Completed: Phase 1 — Ingestion & Indexing ✅

| Component | Description |
|---------|-------------|
| `/api/config.py` | ✅ Centralized env-based config (paths, models, DB, OpenAI API key) |
| `/api/db.py` | ✅ SQLAlchemy ORM: User, Document, Chunk, ACLRule models with session management |
| `/api/ingest.py` | ✅ **FINAL (Oct 28)**: Memory-hardened chunking (500 tokens, 75 overlap, 200-chunk cap), mini-batch embeddings (40 chunks), infinite-loop guards |
| `/api/extractors/email_extractor.py` | ✅ .msg/.eml extraction with memory cleanup (ready for Phase 2) |
| `/api/retriever.py` | ✅ Hybrid search (vector + BM25) + CrossEncoder reranking + ACL filtering |
| `/api/security.py` | ✅ Auth middleware (demo token, ready for Azure AD JWT) |
| `/api/main.py` | ✅ FastAPI routes: `/health`, `/ingest`, `/query` |
| `/docker-compose.yml` | ✅ Postgres 15 (port 15432) + Qdrant running locally |
| `/ingest_emails_batch.py` | ✅ Email batch ingestion tool (ready for Phase 2) |
| `/ingest_pool.py` | ✅ **PRIMARY TOOL**: Parallel ingestion with `--workers`, `--max-pdfs`, `--dry-run` |
| `/rebuild_vectors.py` | ✅ **UTILITY**: Re-upload vectors to Qdrant from Postgres chunks (bulk processing) |
| `/ocr_prepare.py` | ✅ Phase 0 complete: 262 PDFs processed (58 OCR'd, 204 text-ready) |

**Phase 1 Status**: ✅ **COMPLETE (Oct 28, 2025)** — Full PDF ingestion pipeline operational.

**Final Stats**:
- **261 documents indexed** (99.6% success rate)
- **3,122 text chunks** created (avg ~12 chunks/doc)
- **3,122 embeddings** in Qdrant (OpenAI text-embedding-3-small, 1536d)
- **Ingestion time**: 19 minutes with 20 parallel workers
- **Known failure**: 1 PDF (Integrion Org Chart) has no extractable text after OCR

**Key Achievements**:
- Parallel processing with ProcessPoolExecutor (4-20 workers tested)
- OpenAI embeddings integration with proper API key management
- Memory optimization: 500-token chunks, 40-chunk mini-batches, explicit gc.collect()
- Resume capability: skips already-processed documents
- Postgres on non-standard port 15432 (Windows Docker workaround)

## 5. Components To Build Next

### 🧠 Phase 2 — Retrieval & Answer Generation

### 🧠 Phase 2 — LLM Integration & Answer Generation
| Component | Purpose |
|------------|----------|
| `llm.py` | LLM connector (OpenAI GPT-5, configurable) |
| `answer_generator.py` | Build context-limited prompts with citations |
| Update `/api/main.py` | Integrate LLM into `/query` endpoint |
| `eval.py` | RAGAS evaluation or manual golden set testing |

### 💬 Phase 3 — Frontend
| Folder | Component | Description |
|---------|------------|-------------|
| `/ui/app/page.tsx` | Main chat UI |
| `/ui/app/api/query/route.ts` | Next.js server action calling FastAPI |
| `/ui/components/ChatMessage.tsx` | Message bubbles + citation expansion |
| `/ui/styles` | Tailwind config |
| `/ui/env.local` | Environment variables (`NEXT_PUBLIC_API_BASE`) |

### ⚙️ Phase 4 — Deployment & Ops
| Task | Description |
|------|-------------|
| Docker Compose | Bring up Qdrant, Postgres, FastAPI, Next.js |
| .env management | API keys, DB URL, collection name |
| Logs & Monitoring | store prompt, latency, similarity |
| Backups | snapshot Qdrant storage + Postgres volume |
| Blue/Green index rollout | `ecm_docs_v2` → switch collection atomically |

---

## 5. Data Flow Summary

```text
        +--------------------------+
        |  OneDrive ECM Documents  |
        +------------+-------------+
                     |
          (ocr_prepare.py)
                     v
          +-------------------+
          |  OCR/Text Corpus  |
          | 04_text_ready     |
          +---------+---------+
                    |
          (FastAPI /ingest)
                    v
     +----------------------+        +---------------------+
     | Qdrant Vector Store  |<-----> | Postgres (metadata) |
     +----------------------+        +---------------------+
                    |
          (FastAPI /query)
                    v
            +---------------+
            |   LLM Engine   |
            | (OpenAI/BGE)   |
            +-------+-------+
                    |
              (Next.js UI)
                    v
            +----------------+
                        +----------------+
            |  User Question  |
            +----------------+
```

---

## 6. Known Issues & Troubleshooting

### 🔴 **Postgres Host Connection (RESOLVED Oct 27)**
**Issue**: Docker Postgres port 5432 wasn't binding to Windows host.

**Solution**: Changed to non-standard port **15432** on host → 5432 in container
- Updated `docker-compose.yml`: `ports: - "15432:5432"`
- Updated `api/config.py`: `POSTGRES_PORT = "15432"`
- Added `init-db.sql` for proper initialization

**Verification**: ✅ `docker ps` shows `0.0.0.0:15432->5432/tcp`
**Test**: Run `python test_db_connection.py` → Should connect successfully

**Note**: Windows Docker Desktop has known issues binding standard ports (5432, 3306). Using non-standard ports (15432, 13306) typically resolves this.

### ✅ **Chunking / Session Stability (RESOLVED Oct 28)**
**Issue**: Large PDFs (>200 chunks) triggered runaway chunking loops, detached SQLAlchemy instances, and OpenAI embedding stalls.

**Solutions Implemented**:
- Configurable `CHUNK_LIMIT` (defaults 200) with progress logging
- Infinite-loop guard when chunk slices collapse to whitespace-only segments
- Configurable embedding mini-batching (`EMBEDDING_MINI_BATCH_SIZE`, default 40)
- `add_document()` returns ID instead of detached object
- Character-based chunking instead of word-splitting arrays

**Performance Tuning Knobs** (in `api/config.py`):
- `CHUNK_SIZE` — Tokens per chunk (default 500, up from 300)
- `CHUNK_OVERLAP` — Overlap between chunks (default 75, up from 50)
- `CHUNK_LIMIT` — Max chunks per document (default 200)
- `EMBEDDING_MINI_BATCH_SIZE` — Chunks per mini-batch (default 40, up from 20)
- `EMBEDDING_API_BATCH_SIZE` — Batch size for OpenAI API (default 100)

**Status**: ✅ 262 PDFs processed in 19 minutes with 20 workers, 261 successful

### ⚠️ **Data Loss Incident & Recovery (Oct 28)**
**Issue**: Earlier version of `ingest_resume.py` used delete-then-recreate pattern that caused transaction rollback, deleting 260 documents from DB without committing new ones.

**Root Cause**: Script deleted existing document records, then called `ingest_document()` to recreate, but transaction rolled back before commit.

**Recovery**: 
- All PDFs remained safe on disk (`C:\ecm-staging\04_text_ready`)
- Used `TRUNCATE documents, chunks RESTART IDENTITY CASCADE` to clear stale DB state
- Re-ran full ingestion with `ingest_pool.py --workers 20`
- Created `rebuild_vectors.py` utility to re-upload vectors from Postgres to Qdrant

**Lessons Learned**:
- Never use delete-then-recreate patterns with SQLAlchemy—use upserts or update-in-place
- SQLAlchemy soft deletes don't clear cached state across processes—use raw SQL `TRUNCATE` for resets
- Worker processes inherit stale env vars—always force-set critical vars in worker initializers

**Script Status**: `ingest_resume.py` removed from codebase (buggy, do not use)

---

## 7. Next Priority Actions

1. ✅ **Phase 1 Complete** — 261 PDFs indexed with 3,122 chunks in ~19 minutes
2. **Phase 2 Next**: Build LLM integration
   - Create `api/llm.py` (OpenAI GPT-4 connector)
   - Create `api/answer_generator.py` (RAG prompt builder with citations)
   - Test retrieval with sample queries: "What is the timeline for ECM replacement?"
3. **Integration**: Wire LLM into `/query` endpoint
4. **Testing**: RAGAS eval or golden set validation
5. **Phase 3**: Next.js frontend setup
6. **Email ingestion**: Process 199 .msg files from Outlook folder

---

## 7. Quick Start Commands

```bash
# Start Docker services
docker-compose up -d

# Verify database connection
docker exec ecm_postgres psql -U postgres -d ecm_rag -c "SELECT COUNT(*) FROM documents;"

# Full PDF ingestion (parallel, recommended)
python ingest_pool.py --workers 20                       # 20 parallel workers (optimal for 32GB RAM)
python ingest_pool.py --workers 4 --max-pdfs 50          # ingest 50 PDFs then stop
python ingest_pool.py --workers 8 --dry-run              # preview what would be ingested

# Rebuild Qdrant vectors from Postgres (if needed)
USE_SQLITE=false python rebuild_vectors.py

# Email ingestion (Phase 2, not yet integrated)
python ingest_emails_batch.py --email-dir "C:\ecm-staging\Outlook" --batch-size 50

# Start FastAPI dev server
uvicorn api.main:app --reload

# View API docs
# Open http://localhost:8000/docs

# Check ingestion stats
docker exec ecm_postgres psql -U postgres -d ecm_rag -c "
  SELECT COUNT(*) as total_docs, SUM(chunk_count) as total_chunks 
  FROM documents;
"
```

---

**Last Updated**: Oct 28, 2025  
**Status**: ✅ Phase 1 Complete — 261 documents indexed, 3,122 chunks, ready for Phase 2 (LLM integration)
