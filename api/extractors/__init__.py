"""
Extractor modules for different document sources.

Each extractor converts a source document to a standardized format:
    {
        "text": str,              # Main content
        "title": str,             # Document title
        "source_type": str,       # "pdf", "email", "word", etc.
        "metadata": dict,         # Extra fields (from, to, date, etc.)
    }
"""
