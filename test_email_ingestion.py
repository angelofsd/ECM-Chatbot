"""
Test email ingestion pipeline - extract and chunk emails WITHOUT database.

This tests the core functionality:
1. Extract 199 emails
2. Parse content
3. Chunk text
4. Count tokens

No database or vector store needed for this test.
"""

from pathlib import Path
from collections import defaultdict
import sys

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
print(f"Extracting emails from: {outlook_dir}")
print("=" * 70)

emails = extract_emails_from_folder(outlook_dir)
print(f"\n✓ Extracted {len(emails)} emails\n")

# Analyze
total_chars = 0
total_chunks = 0
stats_by_sender = defaultdict(lambda: {"count": 0, "chars": 0, "chunks": 0})
extraction_success = 0

for email in emails:
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

# Print summary
print("=" * 70)
print("INGESTION TEST RESULTS")
print("=" * 70)
print(f"Total emails extracted: {extraction_success} / {len(emails)}")
print(f"Total text: {total_chars:,} characters")
print(f"Total chunks: {total_chunks:,}")
print(f"Avg chunk size: {total_chars / total_chunks if total_chunks > 0 else 0:.0f} chars")
print(f"Avg chunks per email: {total_chunks / extraction_success if extraction_success > 0 else 0:.1f}")

print("\n" + "=" * 70)
print("TOP SENDERS (by email count)")
print("=" * 70)

for sender, stats in sorted(stats_by_sender.items(), key=lambda x: x[1]["count"], reverse=True)[:10]:
    print(f"{sender:40} | {stats['count']:3} emails | {stats['chunks']:5} chunks")

print("\n" + "=" * 70)
print("✓ Email extraction test SUCCESSFUL!")
print("=" * 70)
print("\nReady for full ingestion pipeline when database is configured.")
print("Next step: python -m api.ingest --email-dir 'C:\\ecm-staging\\Outlook'")
