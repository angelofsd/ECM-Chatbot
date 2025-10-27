"""
Test full email ingestion pipeline.
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from api.ingest import main

# Test with sample of emails
print("Testing email ingestion pipeline...")
print("\nIngesting sample of 5 emails from C:\\ecm-staging\\Outlook\n")

try:
    main(
        pdf_dir=None,  # Skip PDFs for now
        email_dir=Path("C:/ecm-staging/Outlook"),
        sample=5
    )
    print("\n✓ Test completed successfully!")
except Exception as e:
    print(f"\n✗ Test failed: {e}")
    import traceback
    traceback.print_exc()
