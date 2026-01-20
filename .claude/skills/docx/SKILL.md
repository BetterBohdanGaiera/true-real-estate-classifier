---
name: docx
description: Comprehensive DOCX manipulation toolkit for reading Word documents, creating new documents with docx-js, and editing existing documents with tracked changes using OOXML. When Claude needs to work with Word documents.
license: Proprietary. LICENSE.txt has complete terms
---

# DOCX Tool

## Reading Content

Use `pandoc` to extract text content, or unpack the file to access raw XML for comments, formatting, and metadata.

## Creating Word Documents

Use the docx-js library to generate Word files. Read docx-js.md for complete documentation.

## Editing Existing Documents

Use the Python Document library for OOXML manipulation. Unpack the file, run your Python script, then repack it.

## Redlining (Tracked Changes)

For professional document review with tracked changes, use a markdown-first planning approach before OOXML implementation. Key principle: "only mark text that actually changes".

Workflow:
1. Convert to markdown with tracked changes preserved
2. Identify and group changes into 3-10 item batches
3. Read full documentation (ooxml.md)
4. Implement batches systematically with XML grepping to verify text location
5. Pack the final document and verify all changes applied

## Document Conversion

Convert DOCX to images via two-step process: DOCX to PDF (LibreOffice) to JPEG (pdftoppm).

**Critical Note**: Read ooxml.md and docx-js.md completely before proceeding with operations.
