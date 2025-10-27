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
- Node.js 18+
- Docker & Docker Compose (for Qdrant, Postgres)
- Tesseract + Ghostscript (for OCR)

### Setup

1. **Clone the repo**
   ```bash
   git clone https://github.com/angelofsd/ECM-Chatbot.git
   cd ECM-Chatbot
   ```

2. **Start infrastructure (Qdrant + Postgres)**
   ```bash
   docker-compose up -d
   ```

3. **Install Python dependencies**
   ```bash
   cd api
   pip install -r requirements.txt
   ```

4. **Prepare documents (if not already done)**
   ```bash
   python ocr_prepare.py
   # Output: C:\ecm-staging\04_text_ready + inventory.csv
   ```

5. **Ingest documents into vector store**
   ```bash
   python -m api.ingest_pdf
   ```

6. **Start FastAPI backend**
   ```bash
   uvicorn api.main:app --reload --port 8000
   ```

7. **In a new terminal, start Next.js frontend**
   ```bash
   cd ui
   npm install
   npm run dev
   # Navigate to http://localhost:3000
   ```

## Project Structure

```
ECM-Chatbot/
├── README.md                      # This file
├── AGENTS.md                      # Guide for AI agents and collaborators
├── PROJECT_STRUCTURE.md           # Detailed architecture & phases
├── ocr_prepare.py                 # Document OCR and inventory pipeline
├── api/
│   ├── __init__.py
│   ├── config.py                  # Configuration (env vars, paths)
│   ├── db.py                      # Postgres schema & ORM models
│   ├── ingest_pdf.py              # Document ingestion & embedding
│   ├── retriever.py               # Vector search & hybrid retrieval
│   ├── security.py                # Auth middleware & token validation
│   ├── main.py                    # FastAPI app & routes
│   └── requirements.txt           # Python dependencies
├── ui/
│   ├── app/
│   │   ├── page.tsx               # Main chat UI
│   │   └── api/query/route.ts     # Next.js server action
│   ├── components/
│   │   └── ChatMessage.tsx        # Chat UI components
│   ├── package.json
│   └── env.local                  # Frontend env vars
├── docker-compose.yml             # Local services (Qdrant, Postgres)
└── .gitignore
```

## Key Concepts

### RAG Pipeline

1. **Ingestion**: OCR'd PDFs → chunked → embedded (BGE model) → stored in Qdrant + Postgres
2. **Retrieval**: User query → embedded → hybrid search (vector + BM25) → reranked → top-k chunks
3. **Generation**: Retrieved context + prompt → LLM (OpenAI) → final answer with citations

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

**Phase 1 — Ingestion & Indexing** (in progress)
- `db.py`: Postgres schema for documents, chunks, users, ACLs
- `ingest_pdf.py`: Load OCR'd PDFs, chunk, embed, write to Qdrant
- `retriever.py`: Vector + BM25 hybrid search with filtering
- `main.py`: FastAPI routes `/ingest`, `/query`, `/health`

### Next Phases

- **Phase 2**: Reranking, LLM integration, evaluation
- **Phase 3**: Next.js frontend with citations & session history
- **Phase 4**: Docker deployment, monitoring, backups

See `PROJECT_STRUCTURE.md` for detailed roadmap.

## API Endpoints (Phase 1+)

```bash
# Health check
GET /health

# Ingest documents (admin only)
POST /ingest
  { "collection": "ecm_docs", "force_reindex": false }

# Query documents with RAG
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

**Ingest PDFs only (Phase 0 output):**
```bash
python -m api.ingest --pdf-dir "C:\ecm-staging\04_text_ready"
```

**Ingest emails only:**
```bash
python -m api.ingest --email-dir "C:\ecm-staging\outlook"
```

**Ingest both PDFs and emails:**
```bash
python -m api.ingest \
  --pdf-dir "C:\ecm-staging\04_text_ready" \
  --email-dir "C:\ecm-staging\outlook"
```

**Sample mode (process only first 5 files):**
```bash
python -m api.ingest --sample 5
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

### Email Ingestion Memory Issues
**Symptom:** Python process consumes 85%+ RAM when processing .msg files

**Cause:** Outlook .msg files are OLE compound documents that load entire file into memory, including attachments. Large files (376KB-500KB) with attachments can spike memory usage.

**Solutions (in order of preference):**

1. **Use msg-extractor CLI tool** (most memory efficient)
   ```bash
   # Install: pip install msg-extractor
   msg-extractor file.msg  # Extracts to JSON - uses subprocess (separate memory space)
   ```

2. **Convert .msg to .eml format first**
   ```bash
   # Use Outlook or online tools to batch convert
   # .eml files are plain text - much more memory efficient
   python -m api.ingest --email-dir "C:\ecm-staging\outlook"  # Now uses .eml files
   ```

3. **Increase system RAM**
   - Each .msg file loads 300KB-400KB per file
   - With 199 files, peak usage ~100MB but spikes higher with concurrent operations
   - Recommend: 8GB+ RAM for this pipeline

4. **Process in smaller batches**
   ```bash
   python -m api.ingest --email-dir "C:\ecm-staging\outlook" --batch-size 20
   ```

### Docker services won't start
```bash
docker-compose down -v
docker-compose up -d
```

### Postgres connection error
Check `api/config.py` — ensure `DATABASE_URL` matches docker-compose

### Qdrant vector search returns no results
Run ingestion again: `python -m api.ingest --reset`

## License

Internal use only — New Mexico Mutual

## Contact

Angela — angelofsd@github.com
