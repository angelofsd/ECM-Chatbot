# OpenAI Embeddings Setup Guide

## Why Switch to OpenAI?

**Memory Efficiency**: The local BGE model (`BAAI/bge-small-en-v1.5`) loads ~80MB + processing overhead into RAM, causing your system to spike to 96% memory usage. OpenAI embeddings use their API instead, so **no model is loaded into local memory**.

**Benefits:**
- ✅ No memory spike during ingestion
- ✅ Fast and reliable (OpenAI's infrastructure)
- ✅ High-quality embeddings (1536 dimensions vs 384)
- ✅ Can process documents in batches without memory concerns
- ✅ Cost-effective: ~$0.13 per 1M tokens (very cheap for 262 PDFs + 199 emails)

## Setup Steps

### 1. Set Your OpenAI API Key

**Windows (PowerShell):**
```powershell
$env:OPENAI_API_KEY="sk-your-key-here"
```

**Windows (CMD):**
```cmd
set OPENAI_API_KEY=sk-your-key-here
```

**Permanently (add to System Environment Variables):**
1. Search for "Environment Variables" in Windows
2. Add new System Variable: `OPENAI_API_KEY` = `sk-your-key-here`
3. Restart terminal

### 2. Install/Update OpenAI Package (if needed)

```bash
pip install --upgrade openai
```

### 3. Test OpenAI Embeddings

```bash
python test_openai_embeddings.py
```

Expected output:
```
=== Testing OpenAI Embeddings ===

✓ API key found: sk-proj-...
✓ Model: text-embedding-3-small
✓ Dimension: 1536

Test 1: Single text embedding
  ✓ Embedding shape: (1536,)
  
Test 2: Batch embedding (3 texts)
  ✓ Embeddings shape: (3, 1536)
  
Test 3: Larger batch (10 texts)
  ✓ Embeddings shape: (10, 1536)

SUCCESS! OpenAI embeddings are working correctly.
```

### 4. Update Qdrant Collection for New Dimensions

OpenAI embeddings are **1536 dimensions** (vs BGE's 384), so we need to recreate the Qdrant collection:

```bash
# Delete old collection (if exists)
curl -X DELETE "http://localhost:6333/collections/ecm_docs"

# Or use Python:
python -c "from qdrant_client import QdrantClient; client = QdrantClient('http://localhost:6333'); client.delete_collection('ecm_docs')"
```

The ingestion script will automatically create a new collection with correct dimensions.

### 5. Run Full Ingestion with OpenAI

**Small test (3 PDFs):**
```bash
USE_OPENAI_EMBEDDINGS=true USE_SQLITE=false python -m api.ingest --pdf-dir "C:/ecm-staging/04_text_ready" --sample 3
```

**Full ingestion (all PDFs):**
```bash
USE_OPENAI_EMBEDDINGS=true USE_SQLITE=false python -m api.ingest --pdf-dir "C:/ecm-staging/04_text_ready"
```

**With emails too:**
```bash
USE_OPENAI_EMBEDDINGS=true USE_SQLITE=false python -m api.ingest --pdf-dir "C:/ecm-staging/04_text_ready" --email-dir "C:/ecm-staging/outlook" --batch-size 50
```

## What Changed in the Code

### 1. `/api/config.py`
- Added `USE_OPENAI_EMBEDDINGS` toggle (default: false)
- Auto-sets dimension to 1536 when using OpenAI

### 2. `/api/embeddings.py` (NEW)
- Unified `EmbeddingGenerator` class
- Supports both local (sentence-transformers) and OpenAI
- Lazy-loads model only when needed
- Batch processing for OpenAI API

### 3. `/api/ingest.py`
- Removed immediate `SentenceTransformer()` loading (was causing memory spike)
- Now uses `get_embedding_generator()` - lazy loaded
- Only initializes embedding model when first chunk needs embedding

## Cost Estimate

OpenAI `text-embedding-3-small` pricing: **$0.02 per 1M tokens**

**Estimate for your project:**
- 262 PDFs × ~2,000 tokens/PDF = 524K tokens
- 199 emails × ~500 tokens/email = 100K tokens
- **Total**: ~625K tokens = **$0.0125 (about 1 cent)**

Even with chunking overhead: **< $0.05 total** 🎉

## Troubleshooting

### "openai package not installed"
```bash
pip install openai
```

### "OPENAI_API_KEY is not set"
Make sure you exported/set the environment variable in your current terminal session.

### "Rate limit exceeded"
OpenAI has rate limits. The embeddings module automatically batches requests (100 texts/batch) to avoid this. If you still hit limits, reduce `--batch-size`:
```bash
USE_OPENAI_EMBEDDINGS=true python -m api.ingest ... --batch-size 25
```

### "Invalid API key"
Check your API key at: https://platform.openai.com/api-keys

## Reverting to Local Model (if needed)

Just run without the `USE_OPENAI_EMBEDDINGS` flag:
```bash
USE_SQLITE=false python -m api.ingest --pdf-dir "C:/ecm-staging/04_text_ready"
```

This will use the local BGE model (but will have the memory issue again).

## Next Steps After Successful Ingestion

1. ✅ Verify documents in Postgres: `python test_db_connection.py`
2. ✅ Test retrieval: `python -m api.main` then hit `/query` endpoint
3. ✅ Build Phase 2: LLM integration for answering questions
4. ✅ Build Phase 3: Next.js frontend

---

**Questions?** Check the logs during ingestion for progress updates!
