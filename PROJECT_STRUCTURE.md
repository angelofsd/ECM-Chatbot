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

| Folder | Component | Description |
|---------|------------|-------------|
| `/api/ingest_pdf.py` | OCR'd document loader | ✅ Reads `04_text_ready` PDFs, chunks with configurable params, embeds via BGE, stores in Qdrant + Postgres |
| `/api/db.py` | DB schema & connection | ✅ SQLAlchemy ORM: User, Document, Chunk, ACLRule models with session management |
| `/api/retriever.py` | Retrieval logic | ✅ Hybrid search (vector + BM25) + CrossEncoder reranking + ACL filtering by department |
| `/api/security.py` | Auth layer | ✅ Demo bearer token auth, middleware integration, ready for Azure AD JWT |
| `/api/main.py` | FastAPI routes | ✅ `/health`, `/ingest`, `/query` endpoints with logging and error handling |

## 5. Components To Build Next

### 🧠 Phase 2 — Retrieval & Answer Generation

### 🧠 Phase 2 — LLM Integration & Answer Generation
| Component | Purpose |
|------------|----------|
| `llm.py` | LLM connector (OpenAI GPT-4, configurable) |
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
            |  User Question  |
            +----------------+
