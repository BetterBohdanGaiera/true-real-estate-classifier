#!/usr/bin/env python3
"""
Redlining validator for Word documents with tracked changes.

This module validates that Claude's tracked changes (insertions and deletions)
in Word documents preserve the original content integrity.
"""

import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Optional


class RedliningValidator:
    """
    Validator for tracked changes (redlining) in Word documents.

    This validator ensures that Claude's modifications to a document
    (tracked as w:ins and w:del elements) preserve the original content
    when the changes are applied.

    Attributes:
        unpacked_dir: Path to the unpacked document directory
        original_docx: Path to the original .docx file
        verbose: Enable verbose output
        namespaces: XML namespaces used in Word documents
    """

    def __init__(
        self,
        unpacked_dir: Path,
        original_docx: Path,
        verbose: bool = False,
    ) -> None:
        """
        Initialize the RedliningValidator.

        Args:
            unpacked_dir: Path to the unpacked document directory
            original_docx: Path to the original .docx file
            verbose: Enable verbose output for debugging
        """
        self.unpacked_dir = Path(unpacked_dir)
        self.original_docx = Path(original_docx)
        self.verbose = verbose

        # Standard namespaces for Word documents
        self.namespaces = {
            "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
            "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
            "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
            "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
            "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
            "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
            "w14": "http://schemas.microsoft.com/office/word/2010/wordml",
            "w15": "http://schemas.microsoft.com/office/word/2012/wordml",
        }

        # Register namespaces for ElementTree
        for prefix, uri in self.namespaces.items():
            ET.register_namespace(prefix, uri)

    def validate(self) -> bool:
        """
        Validate tracked changes in the modified document.

        This method:
        1. Checks if modified document.xml exists
        2. Detects tracked changes authored by Claude
        3. If no Claude changes, passes immediately
        4. Unpacks original docx to a temp directory
        5. Removes Claude's tracked changes from both documents
        6. Extracts and compares text content
        7. Generates detailed diff on mismatch

        Returns:
            bool: True if validation passes, False otherwise
        """
        modified_document_path = self.unpacked_dir / "word" / "document.xml"

        # Check if modified document.xml exists
        if not modified_document_path.exists():
            if self.verbose:
                print("Redlining validation: No document.xml found, skipping")
            return True

        # Parse the modified document
        try:
            modified_tree = ET.parse(modified_document_path)
            modified_root = modified_tree.getroot()
        except ET.ParseError as e:
            print(f"Redlining validation FAILED: Could not parse document.xml: {e}")
            return False

        # Detect Claude's tracked changes
        claude_changes = self._detect_claude_changes(modified_root)

        if not claude_changes:
            if self.verbose:
                print("Redlining validation: No Claude tracked changes detected, PASSED")
            return True

        if self.verbose:
            print(f"Redlining validation: Found {len(claude_changes)} Claude tracked changes")

        # Unpack original docx to temp directory
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            try:
                with zipfile.ZipFile(self.original_docx, "r") as zf:
                    zf.extractall(temp_path)
            except zipfile.BadZipFile as e:
                print(f"Redlining validation FAILED: Could not unpack original docx: {e}")
                return False

            original_document_path = temp_path / "word" / "document.xml"

            if not original_document_path.exists():
                print("Redlining validation FAILED: Original document.xml not found")
                return False

            # Parse original document
            try:
                original_tree = ET.parse(original_document_path)
                original_root = original_tree.getroot()
            except ET.ParseError as e:
                print(f"Redlining validation FAILED: Could not parse original document.xml: {e}")
                return False

            # Remove Claude's tracked changes from both documents
            # For original: just extract text as-is
            # For modified: remove Claude's insertions, unwrap Claude's deletions
            self._remove_claude_tracked_changes(modified_root)

            # Extract text content from both
            original_text = self._extract_text_content(original_root)
            modified_text = self._extract_text_content(modified_root)

            # Compare text content
            if original_text == modified_text:
                if self.verbose:
                    print("Redlining validation: Text content matches after removing Claude changes, PASSED")
                print("Redlining validation PASSED!")
                return True
            else:
                print("Redlining validation FAILED: Text content mismatch after removing Claude changes")
                self._generate_detailed_diff(original_text, modified_text)
                return False

    def _detect_claude_changes(self, root: ET.Element) -> list[ET.Element]:
        """
        Detect tracked changes authored by Claude.

        Args:
            root: The XML root element of the document

        Returns:
            List of elements representing Claude's tracked changes
        """
        claude_changes = []
        w_ns = self.namespaces["w"]

        # Find all w:ins (insertions) and w:del (deletions) by Claude
        for tag in ["ins", "del"]:
            for elem in root.iter(f"{{{w_ns}}}{tag}"):
                author = elem.get(f"{{{w_ns}}}author", "")
                if author.lower() == "claude":
                    claude_changes.append(elem)

        return claude_changes

    def _remove_claude_tracked_changes(self, root: ET.Element) -> None:
        """
        Remove Claude's tracked changes from the document.

        For insertions (w:ins with author="Claude"): Remove the entire element
        For deletions (w:del with author="Claude"): Unwrap the element (keep content)

        This effectively reverts Claude's changes to show the original content.

        Args:
            root: The XML root element of the document (modified in place)
        """
        w_ns = self.namespaces["w"]

        # Process in multiple passes to handle nested elements correctly
        changes_made = True
        while changes_made:
            changes_made = False

            # Find all parent-child relationships for tracked changes
            for parent in root.iter():
                children_to_process = []

                for child in list(parent):
                    # Check for w:ins authored by Claude - remove entirely
                    if child.tag == f"{{{w_ns}}}ins":
                        author = child.get(f"{{{w_ns}}}author", "")
                        if author.lower() == "claude":
                            children_to_process.append(("remove", child))

                    # Check for w:del authored by Claude - unwrap (keep content)
                    elif child.tag == f"{{{w_ns}}}del":
                        author = child.get(f"{{{w_ns}}}author", "")
                        if author.lower() == "claude":
                            children_to_process.append(("unwrap", child))

                # Process the changes
                for action, child in children_to_process:
                    if action == "remove":
                        # Remove the insertion entirely
                        parent.remove(child)
                        changes_made = True
                    elif action == "unwrap":
                        # Unwrap deletion: replace w:del with its children
                        index = list(parent).index(child)
                        parent.remove(child)
                        # Insert children at the same position
                        for i, subchild in enumerate(child):
                            parent.insert(index + i, subchild)
                        changes_made = True

    def _extract_text_content(self, root: ET.Element) -> str:
        """
        Extract text content from the document, preserving paragraph structure.

        This method extracts text from w:t elements and adds newlines
        between paragraphs (w:p) for comparison purposes.

        Args:
            root: The XML root element of the document

        Returns:
            Extracted text content as a string
        """
        w_ns = self.namespaces["w"]
        text_parts = []

        # Find all paragraphs
        for paragraph in root.iter(f"{{{w_ns}}}p"):
            paragraph_text = []

            # Find all text elements within the paragraph
            for text_elem in paragraph.iter(f"{{{w_ns}}}t"):
                if text_elem.text:
                    paragraph_text.append(text_elem.text)

            # Join text within paragraph and add to parts
            if paragraph_text:
                text_parts.append("".join(paragraph_text))

        # Join paragraphs with newlines
        return "\n".join(text_parts)

    def _generate_detailed_diff(
        self,
        original_text: str,
        modified_text: str,
    ) -> None:
        """
        Generate a detailed diff between original and modified text.

        This method prints a human-readable diff showing the differences
        between the original and modified document text.

        Args:
            original_text: The original document text
            modified_text: The modified document text (after removing Claude changes)
        """
        print("\n" + "=" * 60)
        print("DETAILED DIFF")
        print("=" * 60)

        # Try git word diff first for better output
        git_diff = self._get_git_word_diff(original_text, modified_text)

        if git_diff:
            print("\nWord-level diff (git diff --word-diff):")
            print("-" * 40)
            print(git_diff)
        else:
            # Fallback to simple line-by-line comparison
            print("\nLine-by-line comparison:")
            print("-" * 40)

            original_lines = original_text.split("\n")
            modified_lines = modified_text.split("\n")

            max_lines = max(len(original_lines), len(modified_lines))

            for i in range(max_lines):
                orig_line = original_lines[i] if i < len(original_lines) else "<missing>"
                mod_line = modified_lines[i] if i < len(modified_lines) else "<missing>"

                if orig_line != mod_line:
                    print(f"\nLine {i + 1} differs:")
                    print(f"  Original: {repr(orig_line)}")
                    print(f"  Modified: {repr(mod_line)}")

        print("\n" + "=" * 60)

    def _get_git_word_diff(
        self,
        original_text: str,
        modified_text: str,
    ) -> Optional[str]:
        """
        Use git diff for character-level comparison.

        This method creates temporary files and uses git's word-diff
        capability to show character-level differences between texts.

        Args:
            original_text: The original text
            modified_text: The modified text

        Returns:
            The git diff output as a string, or None if git is unavailable
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            original_file = temp_path / "original.txt"
            modified_file = temp_path / "modified.txt"

            # Write texts to temporary files
            original_file.write_text(original_text, encoding="utf-8")
            modified_file.write_text(modified_text, encoding="utf-8")

            try:
                # Use git diff with word-diff for character-level comparison
                result = subprocess.run(
                    [
                        "git",
                        "diff",
                        "--no-index",
                        "--word-diff=color",
                        "--word-diff-regex=.",
                        str(original_file),
                        str(modified_file),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                # git diff returns exit code 1 when there are differences
                # which is expected, so we don't check returncode
                if result.stdout:
                    # Filter out the file header lines
                    lines = result.stdout.split("\n")
                    filtered_lines = [
                        line for line in lines
                        if not line.startswith("diff --git")
                        and not line.startswith("index ")
                        and not line.startswith("---")
                        and not line.startswith("+++")
                        and not line.startswith("@@")
                    ]
                    return "\n".join(filtered_lines).strip()

                return None

            except FileNotFoundError:
                # git not available
                if self.verbose:
                    print("Note: git not available for word-diff, using fallback")
                return None
            except subprocess.TimeoutExpired:
                if self.verbose:
                    print("Note: git diff timed out, using fallback")
                return None
            except Exception as e:
                if self.verbose:
                    print(f"Note: git diff failed ({e}), using fallback")
                return None
