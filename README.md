# ECM RAG Chatbot

A Retrieval-Augmented Generation (RAG) chatbot that answers questions about New Mexico Mutual's ECM (Enterprise Content Management) replacement project using company documents.

## Overview

The chatbot uses a **local RAG pipeline** to provide accurate, cited answers from internal ECM project documentation:

- **Document Processing**: OCR for scanned PDFs using Tesseract + Ghostscript
- **Vector Store**: Qdrant for semantic search
- **Metadata Store**: Postgres for document metadata and ACL rules
- **Backend**: FastAPI for retrieval and LLM orchestration
- **Frontend**: Next.js for interactive chat interface

## Supported Document Sources

- **PDFs** – OCR'd and text-based documents
- **Outlook Emails** – .msg and .eml files with full header preservation
- **Future** – Word docs (.docx), spreadsheets, Teams exports

See [Multi-Source Strategy](#multi-source-ingestion) below.

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose (for Qdrant, Postgres)
- Tesseract + Ghostscript (for OCR, Phase 0 only)
- OpenAI API key (for embeddings)

### Setup

1. **Clone the repo**
   ```bash
   git clone https://github.com/angelofsd/ECM-Chatbot.git
   cd ECM-Chatbot
   ```

2. **Set up environment variables**
   ```bash
   # Create .env file in project root
   echo "OPENAI_API_KEY=your-key-here" > .env
   ```

3. **Start infrastructure (Qdrant + Postgres)**
   ```bash
   docker-compose up -d
   ```

4. **Install Python dependencies**
   ```bash
   pip install -r api/requirements.txt
   ```

5. **Ingest documents (parallel, recommended)**
   ```bash
   python ingest_pool.py --workers 20
   # Completed in ~19 minutes for 262 PDFs
   ```

6. **Verify ingestion**
   ```bash
   docker exec ecm_postgres psql -U postgres -d ecm_rag -c \
     "SELECT COUNT(*) as docs, SUM(chunk_count) as chunks FROM documents;"
   # Expected: 261 docs, 3122 chunks
   ```

7. **Start FastAPI backend** (Phase 2)
   ```bash
   uvicorn api.main:app --reload --port 8000
   ```

8. **Test API** (Phase 2)
   ```bash
   # Navigate to http://localhost:8000/docs
   ```

## Project Structure

```
ECM-Chatbot/
├── README.md                      # This file
├── AGENTS.md                      # Guide for AI agents and collaborators
├── PROJECT_STRUCTURE.md           # Detailed architecture & phases
├── ocr_prepare.py                 # Phase 0: Document OCR and inventory
├── ingest_pool.py                 # Phase 1: Parallel PDF ingestion (PRIMARY TOOL)
├── rebuild_vectors.py             # Phase 1: Re-upload vectors to Qdrant from Postgres
├── ingest_emails_batch.py         # Phase 2: Email ingestion (ready for use)
├── api/
│   ├── __init__.py
│   ├── config.py                  # Configuration (env vars, paths, OpenAI key)
│   ├── db.py                      # Postgres schema & ORM models
│   ├── ingest.py                  # Core ingestion pipeline with memory guards
│   ├── embeddings.py              # OpenAI + local embedding generators
│   ├── extractors/
│   │   ├── email_extractor.py     # .msg/.eml processing
│   │   └── pdf_extractor.py       # PDF text extraction
│   ├── retriever.py               # Vector search & hybrid retrieval
│   ├── security.py                # Auth middleware & token validation
│   ├── main.py                    # FastAPI app & routes
│   └── requirements.txt           # Python dependencies
├── docker-compose.yml             # Postgres + Qdrant services
└── .env                           # Environment variables (OPENAI_API_KEY)
```

## Key Concepts

### RAG Pipeline

1. **Ingestion**: OCR'd PDFs → chunked (500 tokens, 75 overlap) → embedded (OpenAI text-embedding-3-small) → stored in Qdrant + Postgres
2. **Retrieval** (Phase 2): User query → embedded → hybrid search (vector + BM25) → reranked → top-k chunks
3. **Generation** (Phase 2): Retrieved context + prompt → LLM (OpenAI GPT-4) → final answer with citations

### Current Stats

- **261 documents indexed** (99.6% success rate)
- **3,122 text chunks** (avg ~12 chunks per document)
- **3,122 embeddings** (OpenAI text-embedding-3-small, 1536 dimensions)
- **Ingestion time**: 19 minutes with 20 parallel workers
- **Database**: Postgres on port 15432 (Windows Docker workaround)
- **Vector store**: Qdrant on ports 6333-6334

### ACL & Security

- Each document chunk tagged with `department` and `allowed_users`
- Query filtered by authenticated user's department/role
- Demo auth in dev (token-based), upgrade to Azure AD in production

### Local Paths

| Component | Path |
|-----------|------|
| OneDrive Source | `C:\Users\angela\OneDrive - New Mexico Mutual\Projects\ECM Replacement Research` |
| OCR Output | `C:\ecm-staging\04_text_ready` |
| Inventory | `C:\ecm-staging\inventory.csv` |

## Development

### Current Phase

**Phase 1 — Ingestion & Indexing** ✅ COMPLETE (Oct 28, 2025)
- ✅ `db.py`: Postgres schema for documents, chunks, users, ACLs
- ✅ `ingest.py`: Memory-hardened ingestion with 500-token chunks, 40-chunk mini-batches
- ✅ `ingest_pool.py`: Parallel orchestrator with ProcessPoolExecutor (4-20 workers tested)
- ✅ `rebuild_vectors.py`: Utility to re-upload vectors from Postgres to Qdrant
- ✅ `embeddings.py`: OpenAI text-embedding-3-small integration
- ✅ 261 PDFs indexed in 19 minutes

### Next Phases

- **Phase 2 (Next)**: LLM integration
  - `api/llm.py`: OpenAI GPT-4 connector
  - `api/answer_generator.py`: RAG prompt builder with citations
  - Test retrieval with sample queries
- **Phase 3**: Next.js frontend with citations & session history
- **Phase 4**: Docker deployment, monitoring, backups

See `PROJECT_STRUCTURE.md` for detailed roadmap.

## API Endpoints (Phase 2+)

```bash
# Health check (available now)
GET /health

# Query documents with RAG (Phase 2 - in development)
POST /query
  { 
    "query": "What is the timeline for ECM replacement?",
    "top_k": 5,
    "use_reranker": true
  }
  Returns: { "answer": "...", "sources": [...], "confidence": 0.92 }
```

## Multi-Source Ingestion

The ingestion pipeline supports multiple document types with unified processing:

### Supported Sources

1. **PDFs** (`/04_text_ready/`)
   - OCR'd scanned documents
   - Native text PDFs
   - Automatically detected via MIME type

2. **Outlook Emails** (`/outlook/`)
   - `.msg` files (Outlook format)
   - `.eml` files (Standard RFC 822)
   - Full metadata preserved (From, To, CC, Date, Subject)
   - Body text + headers in searchable format

### Folder Structure

```
C:\ecm-staging\
├── 04_text_ready/        # OCR'd PDFs (Phase 0 output)
│   ├── Claims/
│   ├── Underwriting/
│   └── ...
└── outlook/              # Email files (to add)
    ├── Claims/           # Dept-based folder → ACL tag
    │   ├── email1.msg
    │   └── email2.eml
    ├── Underwriting/
    └── ...
```

### Usage

**Ingest PDFs (primary tool - parallel processing):**
```bash
python ingest_pool.py --workers 20                       # Full speed (recommended for 32GB RAM)
python ingest_pool.py --workers 4 --max-pdfs 50          # Process 50 PDFs only
python ingest_pool.py --workers 8 --dry-run              # Preview what would be ingested
```

**Rebuild Qdrant vectors (if needed):**
```bash
USE_SQLITE=false python rebuild_vectors.py
```

**Ingest emails (Phase 2, not yet integrated):**
```bash
python ingest_emails_batch.py --email-dir "C:\ecm-staging\Outlook" --batch-size 50
```

### Adding New Source Types

Each source type has an extractor module in `/api/extractors/`:

```python
# api/extractors/word_extractor.py
def extract_from_docx(file_path: Path) -> Optional[Dict]:
    """Extract text from .docx file."""
    from docx import Document
    doc = Document(file_path)
    text = "\n".join([p.text for p in doc.paragraphs])
    return {
        "text": text,
        "title": file_path.stem,
        "source_type": "word",
        "metadata": {"filename": file_path.name}
    }
```

Then register in `ingest.py`:
```python
def extract_content(file_path, source_type):
    if source_type == "word":
        return extract_from_docx(file_path)
    # ...
```

## Contributing

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Make changes and update docs as needed
3. Test locally
4. Commit with clear messages: `git commit -m "Add feature: description"`
5. Push frequently: `git push origin feature/your-feature`
6. Open a PR when ready

See `AGENTS.md` for conventions and how AI agents should approach development.

## Troubleshooting

### Postgres Connection Issues
**Symptom:** Can't connect to database from Python scripts

**Solution:** Windows Docker Desktop has issues with standard ports. We use port 15432 instead:
```bash
# Verify Postgres is running
docker ps | grep ecm_postgres
# Should show: 0.0.0.0:15432->5432/tcp

# Test connection
docker exec ecm_postgres psql -U postgres -d ecm_rag -c "SELECT 1;"
```

### Stale Qdrant Vectors
**Symptom:** Qdrant has more vectors than Postgres has chunks

**Solution:** Clear and rebuild vectors from Postgres:
```bash
USE_SQLITE=false python rebuild_vectors.py
```

### Memory Issues During Ingestion
**Symptom:** Python process exceeds 85% RAM

**Solution:** Reduce parallel workers:
```bash
python ingest_pool.py --workers 8  # Down from 20
```

### Docker Services Won't Start
```bash
docker-compose down -v
docker-compose up -d
```

## License

Internal use only — New Mexico Mutual

## Contact

Angel Acosta— angelofsd@github.com
