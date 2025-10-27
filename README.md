# ECM RAG Chatbot

A Retrieval-Augmented Generation (RAG) chatbot that answers questions about New Mexico Mutual's ECM (Enterprise Content Management) replacement project using company documents.

## Overview

The chatbot uses a **local RAG pipeline** to provide accurate, cited answers from internal ECM project documentation:

- **Document Processing**: OCR for scanned PDFs using Tesseract + Ghostscript
- **Vector Store**: Qdrant for semantic search
- **Metadata Store**: Postgres for document metadata and ACL rules
- **Backend**: FastAPI for retrieval and LLM orchestration
- **Frontend**: Next.js for interactive chat interface

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

## Contributing

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Make changes and update docs as needed
3. Test locally
4. Commit with clear messages: `git commit -m "Add feature: description"`
5. Push frequently: `git push origin feature/your-feature`
6. Open a PR when ready

See `AGENTS.md` for conventions and how AI agents should approach development.

## Troubleshooting

### Docker services won't start
```bash
docker-compose down -v
docker-compose up -d
```

### Postgres connection error
Check `api/config.py` — ensure `DATABASE_URL` matches docker-compose

### Qdrant vector search returns no results
Run ingestion again: `python -m api.ingest_pdf --reset`

### OCR failures
See `C:\ecm-staging\inventory.csv` for action/error details

## License

Internal use only — New Mexico Mutual

## Contact

Angela — angelofsd@github.com
