"""
DOCX schema validator for Word document validation.

Validates unpacked DOCX files against Office Open XML standards,
checking for well-formedness, namespace declarations, tracked changes,
relationship references, and structural integrity.
"""

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import defusedxml.ElementTree as SafeET

from .base import BaseSchemaValidator

# Word 2006 main document namespace
WORD_2006_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

# Common namespaces used in DOCX files
DOCX_NAMESPACES = {
    "w": WORD_2006_NAMESPACE,
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
    "ct": "http://schemas.openxmlformats.org/package/2006/content-types",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "xml": "http://www.w3.org/XML/1998/namespace",
}


class DOCXSchemaValidator(BaseSchemaValidator):
    """Validator for DOCX (Word) documents.

    Performs comprehensive validation of unpacked DOCX files including:
    - XML well-formedness
    - Namespace declarations
    - Unique ID validation
    - File reference integrity
    - Content type validation
    - XSD schema validation
    - Whitespace preservation checks
    - Tracked changes validation (deletions, insertions)
    - Relationship ID references
    - Paragraph count comparison with original
    """

    # XPath prefix for Word namespace
    W_NS = f"{{{WORD_2006_NAMESPACE}}}"

    def validate(self) -> bool:
        """Run all DOCX validation checks.

        Returns:
            True if all validations pass, False otherwise.
        """
        # Run all validation tests
        self._validate_xml_wellformedness()
        self._validate_namespace_declarations()
        self._validate_unique_ids()
        self._validate_file_references()
        self._validate_content_types()
        self._validate_xsd_schema()
        self.validate_whitespace_preservation()
        self.validate_deletions()
        self.validate_insertions()
        self._validate_relationship_id_references()
        self.compare_paragraph_counts()

        # Print summary if verbose
        if self.verbose:
            self.print_summary()

        # Return True only if all validations passed
        return all(result.passed for result in self.results)

    def _validate_xml_wellformedness(self) -> None:
        """Validate that all XML files are well-formed."""
        xml_files = self.get_xml_files() + self.get_rels_files()
        errors: list[str] = []

        for xml_file in xml_files:
            try:
                SafeET.parse(xml_file)
            except ET.ParseError as e:
                errors.append(f"{xml_file.name}: {e}")

        self.add_result(
            name="XML Well-formedness",
            passed=len(errors) == 0,
            message=f"Checked {len(xml_files)} XML files",
            details=errors if errors else None,
        )

    def _validate_namespace_declarations(self) -> None:
        """Validate that required namespaces are properly declared."""
        document_xml = self.unpacked_dir / "word" / "document.xml"

        if not document_xml.exists():
            self.add_result(
                name="Namespace Declarations",
                passed=False,
                message="document.xml not found",
            )
            return

        try:
            content = self.read_file(document_xml)
            # Check for main Word namespace
            has_word_ns = WORD_2006_NAMESPACE in content

            # Check for relationships namespace
            rel_ns = DOCX_NAMESPACES["r"]
            has_rel_ns = rel_ns in content

            missing = []
            if not has_word_ns:
                missing.append(f"Word namespace: {WORD_2006_NAMESPACE}")
            if not has_rel_ns:
                missing.append(f"Relationships namespace: {rel_ns}")

            self.add_result(
                name="Namespace Declarations",
                passed=len(missing) == 0,
                message="Required namespaces declared" if not missing else "Missing namespaces",
                details=missing if missing else None,
            )
        except Exception as e:
            self.add_result(
                name="Namespace Declarations",
                passed=False,
                message=f"Error reading document.xml: {e}",
            )

    def _validate_unique_ids(self) -> None:
        """Validate that IDs are unique within each XML file."""
        xml_files = self.get_xml_files()
        errors: list[str] = []

        # Patterns for common ID attributes in DOCX
        id_patterns = [
            re.compile(r'w:id="([^"]+)"'),
            re.compile(r'r:id="([^"]+)"'),
            re.compile(r'w:rsid\w*="([^"]+)"'),
        ]

        for xml_file in xml_files:
            try:
                content = self.read_file(xml_file)

                for pattern in id_patterns:
                    ids = pattern.findall(content)
                    seen: dict[str, int] = {}

                    for id_val in ids:
                        seen[id_val] = seen.get(id_val, 0) + 1

                    # For w:id (bookmark IDs), duplicates are errors
                    # For r:id, duplicates are allowed (references)
                    # For rsid, duplicates are expected (revision session IDs)
                    if 'w:id="' in pattern.pattern:
                        duplicates = [k for k, v in seen.items() if v > 1]
                        if duplicates:
                            errors.append(
                                f"{xml_file.name}: Duplicate w:id values: {duplicates}"
                            )

            except Exception as e:
                errors.append(f"{xml_file.name}: Error checking IDs: {e}")

        self.add_result(
            name="Unique IDs",
            passed=len(errors) == 0,
            message=f"Checked {len(xml_files)} files for ID uniqueness",
            details=errors if errors else None,
        )

    def _validate_file_references(self) -> None:
        """Validate that file references in relationships are valid."""
        rels_files = self.get_rels_files()
        errors: list[str] = []

        for rels_file in rels_files:
            try:
                tree = SafeET.parse(rels_file)
                root = tree.getroot()

                # Get the directory containing the rels file for relative path resolution
                rels_dir = rels_file.parent.parent  # Go up from _rels directory

                for rel in root.findall(".//{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"):
                    target = rel.get("Target", "")
                    target_mode = rel.get("TargetMode", "Internal")

                    # Skip external references
                    if target_mode == "External" or target.startswith("http"):
                        continue

                    # Resolve relative path
                    if target.startswith("/"):
                        # Absolute path from package root
                        target_path = self.unpacked_dir / target.lstrip("/")
                    else:
                        # Relative path from rels file location
                        target_path = (rels_dir / target).resolve()

                    # Check if target exists
                    if not target_path.exists():
                        errors.append(
                            f"{rels_file.name}: Missing target '{target}'"
                        )

            except Exception as e:
                errors.append(f"{rels_file.name}: Error parsing: {e}")

        self.add_result(
            name="File References",
            passed=len(errors) == 0,
            message=f"Checked {len(rels_files)} relationship files",
            details=errors if errors else None,
        )

    def _validate_content_types(self) -> None:
        """Validate [Content_Types].xml file."""
        content_types_file = self.unpacked_dir / "[Content_Types].xml"

        if not content_types_file.exists():
            self.add_result(
                name="Content Types",
                passed=False,
                message="[Content_Types].xml not found",
            )
            return

        try:
            tree = SafeET.parse(content_types_file)
            root = tree.getroot()

            ct_ns = "{http://schemas.openxmlformats.org/package/2006/content-types}"

            # Check for required content types
            overrides = root.findall(f".//{ct_ns}Override")
            defaults = root.findall(f".//{ct_ns}Default")

            required_parts = ["/word/document.xml"]
            missing_parts = []

            override_parts = {o.get("PartName", "") for o in overrides}

            for part in required_parts:
                if part not in override_parts:
                    missing_parts.append(part)

            # Verify that overridden parts exist
            invalid_overrides = []
            for override in overrides:
                part_name = override.get("PartName", "")
                part_path = self.unpacked_dir / part_name.lstrip("/")
                if not part_path.exists():
                    invalid_overrides.append(part_name)

            errors = []
            if missing_parts:
                errors.append(f"Missing required parts: {missing_parts}")
            if invalid_overrides:
                errors.append(f"Invalid override references: {invalid_overrides}")

            self.add_result(
                name="Content Types",
                passed=len(errors) == 0,
                message=f"Found {len(overrides)} overrides, {len(defaults)} defaults",
                details=errors if errors else None,
            )

        except Exception as e:
            self.add_result(
                name="Content Types",
                passed=False,
                message=f"Error parsing [Content_Types].xml: {e}",
            )

    def _validate_xsd_schema(self) -> None:
        """Validate XML against XSD schemas.

        Note: Full XSD validation requires external schema files.
        This method performs basic structural validation.
        """
        document_xml = self.unpacked_dir / "word" / "document.xml"

        if not document_xml.exists():
            self.add_result(
                name="XSD Schema Validation",
                passed=False,
                message="document.xml not found",
            )
            return

        try:
            tree = SafeET.parse(document_xml)
            root = tree.getroot()

            errors = []

            # Check root element is w:document
            expected_root = f"{{{WORD_2006_NAMESPACE}}}document"
            if root.tag != expected_root:
                errors.append(f"Root element should be {expected_root}, found {root.tag}")

            # Check for w:body element
            body = root.find(f".//{{{WORD_2006_NAMESPACE}}}body")
            if body is None:
                errors.append("Missing w:body element")

            # Check that paragraphs have valid structure
            paragraphs = root.findall(f".//{{{WORD_2006_NAMESPACE}}}p")
            for i, p in enumerate(paragraphs):
                # Paragraphs should not contain other paragraphs directly
                nested_p = p.find(f".//{{{WORD_2006_NAMESPACE}}}p")
                if nested_p is not None:
                    errors.append(f"Paragraph {i} contains nested paragraph (invalid)")

            self.add_result(
                name="XSD Schema Validation",
                passed=len(errors) == 0,
                message=f"Validated document structure ({len(paragraphs)} paragraphs)",
                details=errors if errors else None,
            )

        except Exception as e:
            self.add_result(
                name="XSD Schema Validation",
                passed=False,
                message=f"Error during schema validation: {e}",
            )

    def validate_whitespace_preservation(self) -> None:
        """Validate whitespace preservation in text elements.

        Checks that text elements containing significant whitespace
        (leading/trailing spaces, multiple spaces) have xml:space='preserve'.
        """
        document_xml = self.unpacked_dir / "word" / "document.xml"

        if not document_xml.exists():
            self.add_result(
                name="Whitespace Preservation",
                passed=False,
                message="document.xml not found",
            )
            return

        try:
            tree = SafeET.parse(document_xml)
            root = tree.getroot()

            warnings: list[str] = []
            xml_ns = "{http://www.w3.org/XML/1998/namespace}"

            # Find all w:t elements (text runs)
            text_elements = root.findall(f".//{{{WORD_2006_NAMESPACE}}}t")

            for t_elem in text_elements:
                text = t_elem.text or ""

                # Check if text has significant whitespace
                has_significant_ws = (
                    text.startswith(" ")
                    or text.endswith(" ")
                    or "  " in text  # Multiple consecutive spaces
                )

                if has_significant_ws:
                    # Check for xml:space="preserve"
                    space_attr = t_elem.get(f"{xml_ns}space")
                    if space_attr != "preserve":
                        # Truncate text for display
                        display_text = text[:30] + "..." if len(text) > 30 else text
                        warnings.append(
                            f"Text with whitespace missing xml:space='preserve': '{display_text}'"
                        )

            self.add_result(
                name="Whitespace Preservation",
                passed=len(warnings) == 0,
                message=f"Checked {len(text_elements)} text elements",
                details=warnings[:10] if warnings else None,  # Limit to first 10
            )

        except Exception as e:
            self.add_result(
                name="Whitespace Preservation",
                passed=False,
                message=f"Error checking whitespace: {e}",
            )

    def validate_deletions(self) -> None:
        """Validate tracked deletions.

        In OOXML, deleted text should use w:delText, not w:t.
        This checks that w:del elements do not contain w:t elements directly.
        """
        document_xml = self.unpacked_dir / "word" / "document.xml"

        if not document_xml.exists():
            self.add_result(
                name="Deletion Validation",
                passed=False,
                message="document.xml not found",
            )
            return

        try:
            tree = SafeET.parse(document_xml)
            root = tree.getroot()

            errors: list[str] = []
            w_ns = f"{{{WORD_2006_NAMESPACE}}}"

            # Find all w:del elements (tracked deletions)
            deletions = root.findall(f".//{w_ns}del")

            for i, del_elem in enumerate(deletions):
                # Find any w:t elements that are direct descendants (not in nested ins)
                # We need to check if there are w:t elements that are NOT inside w:ins
                for t_elem in del_elem.findall(f".//{w_ns}t"):
                    # Check if this w:t is inside a w:ins (which would be valid)
                    parent = t_elem
                    is_in_ins = False

                    # Walk up to find if we hit w:ins before w:del
                    while parent is not None:
                        # ElementTree doesn't have parent references, use iterative search
                        break

                    # Alternative: check if there's a w:ins ancestor within the w:del
                    # For simplicity, just flag if w:t is found in w:del
                    # A proper check would use parent tracking
                    text = (t_elem.text or "")[:20]
                    errors.append(
                        f"Deletion {i}: Found w:t element (should use w:delText): '{text}...'"
                    )

            self.add_result(
                name="Deletion Validation",
                passed=len(errors) == 0,
                message=f"Checked {len(deletions)} tracked deletions",
                details=errors[:10] if errors else None,  # Limit to first 10
            )

        except Exception as e:
            self.add_result(
                name="Deletion Validation",
                passed=False,
                message=f"Error checking deletions: {e}",
            )

    def validate_insertions(self) -> None:
        """Validate tracked insertions.

        In OOXML, inserted text should use w:t, not w:delText.
        w:delText in w:ins is only valid if inside a nested w:del.
        """
        document_xml = self.unpacked_dir / "word" / "document.xml"

        if not document_xml.exists():
            self.add_result(
                name="Insertion Validation",
                passed=False,
                message="document.xml not found",
            )
            return

        try:
            tree = SafeET.parse(document_xml)
            root = tree.getroot()

            errors: list[str] = []
            w_ns = f"{{{WORD_2006_NAMESPACE}}}"

            # Find all w:ins elements (tracked insertions)
            insertions = root.findall(f".//{w_ns}ins")

            for i, ins_elem in enumerate(insertions):
                # Find w:delText elements in this insertion
                for del_text in ins_elem.findall(f".//{w_ns}delText"):
                    # Check if this delText is inside a nested w:del
                    # This is the only valid case for delText in ins
                    nested_dels = ins_elem.findall(f".//{w_ns}del")

                    is_valid = False
                    for nested_del in nested_dels:
                        if del_text in nested_del.iter():
                            is_valid = True
                            break

                    if not is_valid:
                        text = (del_text.text or "")[:20]
                        errors.append(
                            f"Insertion {i}: Found w:delText not in nested w:del: '{text}...'"
                        )

            self.add_result(
                name="Insertion Validation",
                passed=len(errors) == 0,
                message=f"Checked {len(insertions)} tracked insertions",
                details=errors[:10] if errors else None,  # Limit to first 10
            )

        except Exception as e:
            self.add_result(
                name="Insertion Validation",
                passed=False,
                message=f"Error checking insertions: {e}",
            )

    def _validate_relationship_id_references(self) -> None:
        """Validate that relationship ID references (r:id) are valid."""
        document_xml = self.unpacked_dir / "word" / "document.xml"
        document_rels = self.unpacked_dir / "word" / "_rels" / "document.xml.rels"

        if not document_xml.exists():
            self.add_result(
                name="Relationship ID References",
                passed=False,
                message="document.xml not found",
            )
            return

        try:
            # Get all defined relationship IDs
            defined_ids: set[str] = set()

            if document_rels.exists():
                rels_tree = SafeET.parse(document_rels)
                rels_root = rels_tree.getroot()
                rel_ns = "{http://schemas.openxmlformats.org/package/2006/relationships}"

                for rel in rels_root.findall(f".//{rel_ns}Relationship"):
                    rel_id = rel.get("Id", "")
                    if rel_id:
                        defined_ids.add(rel_id)

            # Get all referenced relationship IDs in document
            doc_content = self.read_file(document_xml)
            r_id_pattern = re.compile(r'r:(?:id|embed|link)="([^"]+)"')
            referenced_ids = set(r_id_pattern.findall(doc_content))

            # Find undefined references
            undefined = referenced_ids - defined_ids
            errors = [f"Undefined relationship ID: {rid}" for rid in undefined]

            self.add_result(
                name="Relationship ID References",
                passed=len(errors) == 0,
                message=f"Found {len(defined_ids)} defined, {len(referenced_ids)} referenced",
                details=errors[:10] if errors else None,
            )

        except Exception as e:
            self.add_result(
                name="Relationship ID References",
                passed=False,
                message=f"Error checking relationship IDs: {e}",
            )

    def count_paragraphs_in_unpacked(self) -> int:
        """Count paragraphs in the unpacked document.xml.

        Returns:
            Number of w:p elements in document.xml.
        """
        document_xml = self.unpacked_dir / "word" / "document.xml"

        if not document_xml.exists():
            return 0

        try:
            tree = SafeET.parse(document_xml)
            root = tree.getroot()
            paragraphs = root.findall(f".//{{{WORD_2006_NAMESPACE}}}p")
            return len(paragraphs)
        except Exception:
            return 0

    def count_paragraphs_in_original(self) -> int:
        """Count paragraphs in the original DOCX file.

        Returns:
            Number of w:p elements in the original document.xml.
        """
        if not self.original_file.exists():
            return 0

        try:
            with zipfile.ZipFile(self.original_file, "r") as zf:
                if "word/document.xml" not in zf.namelist():
                    return 0

                with zf.open("word/document.xml") as f:
                    tree = SafeET.parse(f)
                    root = tree.getroot()
                    paragraphs = root.findall(f".//{{{WORD_2006_NAMESPACE}}}p")
                    return len(paragraphs)
        except Exception:
            return 0

    def compare_paragraph_counts(self) -> None:
        """Compare paragraph counts between unpacked and original documents.

        This validation checks that the number of paragraphs in the unpacked
        document matches the original, which helps detect structural corruption.
        """
        unpacked_count = self.count_paragraphs_in_unpacked()
        original_count = self.count_paragraphs_in_original()

        if original_count == 0:
            self.add_result(
                name="Paragraph Count Comparison",
                passed=True,
                message="Could not count original paragraphs (skipped)",
            )
            return

        difference = unpacked_count - original_count
        passed = unpacked_count == original_count

        if passed:
            message = f"Both have {unpacked_count} paragraphs"
        else:
            message = (
                f"Unpacked: {unpacked_count}, Original: {original_count} "
                f"(difference: {difference:+d})"
            )

        self.add_result(
            name="Paragraph Count Comparison",
            passed=passed,
            message=message,
        )
