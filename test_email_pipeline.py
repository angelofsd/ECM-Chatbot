"""
Test email ingestion pipeline (without database/Qdrant).

Tests:
1. Email extraction from .msg files
2. Text chunking
3. Embedding generation
4. Prints stats and samples
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from api.extractors.email_extractor import extract_email
from sentence_transformers import SentenceTransformer
import numpy as np

# ========================
# Settings
# ========================

OUTLOOK_DIR = Path("C:/ecm-staging/Outlook")
SAMPLE_SIZE = 5
CHUNK_SIZE = 300  # tokens (approximate words)

# ========================
# Load Model
# ========================

print("Loading embedding model (BAAI/bge-small-en-v1.5)...")
embedding_model = SentenceTransformer("BAAI/bge-small-en-v1.5")
print(f"✓ Model loaded\n")

# ========================
# Process Emails
# ========================

email_files = list(OUTLOOK_DIR.glob("*.msg"))[:SAMPLE_SIZE]
print(f"Processing {len(email_files)} sample emails...\n")

total_emails = 0
total_chunks = 0
total_embeddings = 0
total_tokens = 0

for email_file in email_files:
    print(f"📧 {email_file.name}")
    
    # Extract email
    extracted = extract_email(email_file)
    if not extracted:
        print("  ✗ Failed to extract\n")
        continue
    
    total_emails += 1
    text = extracted["text"]
    title = extracted["title"]
    
    print(f"  Subject: {extracted['metadata'].get('subject', '(no subject)')[:60]}")
    print(f"  From: {extracted['metadata'].get('from', '(unknown)')[:40]}")
    print(f"  Text length: {len(text):,} chars")
    
    # Chunk text
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + CHUNK_SIZE, len(words))
        chunk_text = " ".join(words[start:end])
        chunks.append(chunk_text)
        total_tokens += (end - start)
        start = end - 50  # overlap
    
    total_chunks += len(chunks)
    print(f"  Chunks: {len(chunks)}")
    
    # Generate embeddings
    if chunks:
        embeddings = embedding_model.encode(chunks, normalize_embeddings=True)
        total_embeddings += len(embeddings)
        print(f"  Embeddings: {len(embeddings)} generated (dim: {embeddings[0].shape[0]})")
    
    print()

# ========================
# Summary
# ========================

print("=" * 60)
print("✓ TEST COMPLETE")
print("=" * 60)
print(f"Emails processed: {total_emails}")
print(f"Total chunks: {total_chunks}")
print(f"Total tokens: {total_tokens:,}")
print(f"Total embeddings: {total_embeddings}")
print(f"Avg chunks per email: {total_chunks / max(total_emails, 1):.1f}")
print(f"Avg tokens per chunk: {total_tokens / max(total_chunks, 1):.1f}")

if total_emails == SAMPLE_SIZE:
    print(f"\n📊 Estimated for full 199 emails:")
    print(f"  Total chunks: ~{int(total_chunks / SAMPLE_SIZE * 199)}")
    print(f"  Total tokens: ~{int(total_tokens / SAMPLE_SIZE * 199):,}")
    print(f"  Embedding time (at 5s/batch): ~{int((total_embeddings / SAMPLE_SIZE * 199) / 100 * 5 / 60)} min")
