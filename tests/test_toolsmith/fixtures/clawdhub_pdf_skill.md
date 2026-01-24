---
name: pdf
description: Comprehensive PDF manipulation toolkit for extracting text and tables, creating new PDFs, merging/splitting documents, and handling forms. When Claude needs to fill in a PDF form or programmatically process, generate, or analyze PDF documents at scale.
license: Proprietary. LICENSE.txt has complete terms
---

# PDF Processing Guide

This skill enables comprehensive PDF document processing including text extraction, table parsing, PDF creation, merging/splitting, and form handling.

## Quick Start

```python
from pypdf import PdfReader, PdfWriter

# Extract text from PDF
reader = PdfReader("document.pdf")
text = reader.pages[0].extract_text()
```

## Python Libraries

### pypdf
Document manipulation: merging, splitting, metadata, rotation

### pdfplumber
Content extraction: text with layout preservation, table extraction

### reportlab
PDF creation: basic and multi-page documents
