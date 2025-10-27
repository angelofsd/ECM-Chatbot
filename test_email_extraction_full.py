"""
Test email ingestion without database (verify extraction and chunking).
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from api.extractors.email_extractor import extract_emails_from_folder

def chunk_text(text: str, chunk_size: int = 300, overlap: int = 50) -> list:
    """Simple chunking for testing."""
    if not text or not text.strip():
        return []
    
    words = text.split()
    chunks = []
    sequence = 0
    
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk_text = " ".join(words[start:end])
        chunks.append({
            "text": chunk_text,
            "sequence": sequence,
            "token_count": end - start,
        })
        sequence += 1
        start = end - overlap
    
    return chunks


print("Testing email extraction and chunking pipeline...\n")

outlook_dir = Path("C:/ecm-staging/Outlook")

# Extract emails
print(f"Extracting emails from {outlook_dir}...")
emails = extract_emails_from_folder(outlook_dir)
print(f"✓ Extracted {len(emails)} emails\n")

# Process sample
for i, email in enumerate(emails[:5]):
    print(f"Email {i+1}: {email['title']}")
    print(f"  From: {email['metadata']['from']}")
    print(f"  Subject: {email['metadata']['subject'][:50]}")
    
    # Chunk the email
    chunks = chunk_text(email['text'])
    print(f"  Chunks: {len(chunks)}")
    
    if chunks:
        print(f"    First chunk: {chunks[0]['text'][:80]}...")
        print(f"    Tokens: {chunks[0]['token_count']}")
    print()

# Statistics
total_emails = len(emails)
total_chunks = 0
total_chars = 0

for email in emails:
    chunks = chunk_text(email['text'])
    total_chunks += len(chunks)
    total_chars += len(email['text'])

print(f"Summary:")
print(f"  Total emails: {total_emails}")
print(f"  Total chunks: {total_chunks}")
print(f"  Total characters: {total_chars:,}")
print(f"  Avg chunks per email: {total_chunks/total_emails:.1f}")
print(f"  Avg chars per email: {total_chars/total_emails:,.0f}")
