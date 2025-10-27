"""
Quick test of email extraction to verify it works before full ingestion.
"""

from pathlib import Path
import sys

# Add api to path
sys.path.insert(0, str(Path(__file__).parent))

from api.extractors.email_extractor import extract_email

# Test with first email
outlook_dir = Path("C:/ecm-staging/Outlook")
email_files = list(outlook_dir.glob("*.msg"))[:3]

print(f"Testing email extraction with {len(email_files)} sample emails...\n")

for email_file in email_files:
    print(f"Testing: {email_file.name}")
    try:
        result = extract_email(email_file)
        if result:
            print(f"  ✓ Success")
            print(f"    Title: {result['title'][:60]}")
            print(f"    Text length: {len(result['text'])} chars")
            print(f"    Metadata: {list(result['metadata'].keys())}")
        else:
            print(f"  ✗ Failed - no result")
    except Exception as e:
        print(f"  ✗ Failed - {e}")
    print()
