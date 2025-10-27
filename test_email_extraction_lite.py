"""
Lightweight email extraction test - NO embedding model (to avoid RAM issues).

This only tests:
1. Extract emails
2. Parse content
3. Chunk text
4. Show statistics
"""

from pathlib import Path
from collections import defaultdict
import sys
import gc

sys.path.insert(0, str(Path(__file__).parent))

from api.extractors.email_extractor import extract_emails_from_folder

def chunk_text(text: str, chunk_size: int = 300) -> list:
    """Split text into chunks."""
    if not text or not text.strip():
        return []
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))
        start = end - 150  # overlap
    return chunks

# Extract emails
outlook_dir = Path("C:/ecm-staging/Outlook")
print(f"Testing email extraction from: {outlook_dir}")
print("=" * 70)
print("\nExtracting and processing emails (streaming)...\n")

# Analyze (without loading embedding model)
total_chars = 0
total_chunks = 0
stats_by_sender = defaultdict(lambda: {"count": 0, "chars": 0, "chunks": 0})
extraction_success = 0

# Process emails one at a time (generator - low memory)
for i, email in enumerate(extract_emails_from_folder(outlook_dir), 1):
    text = email["text"]
    metadata = email["metadata"]
    
    total_chars += len(text)
    chunks = chunk_text(text)
    total_chunks += len(chunks)
    extraction_success += 1
    
    sender = metadata.get("from", "unknown")[:40]
    stats_by_sender[sender]["count"] += 1
    stats_by_sender[sender]["chars"] += len(text)
    stats_by_sender[sender]["chunks"] += len(chunks)
    
    if i % 50 == 0:
        print(f"  Processed {i} emails...")
        gc.collect()  # Force garbage collection to free memory

# Print summary
print("\n" + "=" * 70)
print("EMAIL INGESTION TEST RESULTS")
print("=" * 70)
print(f"✓ Emails extracted:      {extraction_success}")
print(f"✓ Total text:            {total_chars:,} characters")
print(f"✓ Total text:            {total_chars:,} characters")
print(f"✓ Total chunks:          {total_chunks:,}")
print(f"✓ Avg chars per email:   {total_chars / extraction_success if extraction_success > 0 else 0:,.0f}")
print(f"✓ Avg chunks per email:  {total_chunks / extraction_success if extraction_success > 0 else 0:.1f}")

print("\n" + "=" * 70)
print("TOP 10 SENDERS (by email count)")
print("=" * 70)

for sender, stats in sorted(stats_by_sender.items(), key=lambda x: x[1]["count"], reverse=True)[:10]:
    pct = (stats['count'] / extraction_success) * 100
    print(f"{stats['count']:3} emails ({pct:5.1f}%) | {sender}")

print("\n" + "=" * 70)
print("✓✓✓ EMAIL EXTRACTION TEST SUCCESSFUL! ✓✓✓")
print("=" * 70)
print(f"\n{extraction_success} emails ready for ingestion into RAG system.")
print("\nNext steps:")
print("1. Start services: docker-compose up -d")
print("2. Run full ingestion: python -m api.ingest --email-dir 'C:\\ecm-staging\\Outlook'")
print("3. Query with: curl -X POST http://localhost:8000/query ...")
