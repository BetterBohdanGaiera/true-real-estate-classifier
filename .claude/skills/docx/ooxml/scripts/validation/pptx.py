#!/usr/bin/env python3
"""
PowerPoint schema validator for PPTX document validation.

Validates unpacked PPTX files against Office Open XML standards,
checking for well-formedness, namespace declarations, slide layouts,
relationship references, and structural integrity.
"""

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import defusedxml.ElementTree as SafeET

from .base import BaseSchemaValidator


# PresentationML namespace constant
PRESENTATIONML_NAMESPACE = "http://schemas.openxmlformats.org/presentationml/2006/main"

# Mapping of element types to their relationship types
ELEMENT_RELATIONSHIP_TYPES = {
    "slide": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide",
    "slideLayout": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout",
    "slideMaster": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster",
    "theme": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme",
    "notesSlide": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesSlide",
    "notesMaster": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesMaster",
    "handoutMaster": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/handoutMaster",
    "presProps": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/presProps",
    "viewProps": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/viewProps",
    "tableStyles": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/tableStyles",
    "image": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image",
    "hyperlink": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
    "oleObject": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/oleObject",
    "audio": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/audio",
    "video": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/video",
    "chart": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart",
    "diagramData": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/diagramData",
    "comments": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments",
    "commentAuthors": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/commentAuthors",
}

# Common namespaces used in PPTX files
PPTX_NAMESPACES = {
    "p": PRESENTATIONML_NAMESPACE,
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "ct": "http://schemas.openxmlformats.org/package/2006/content-types",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "xml": "http://www.w3.org/XML/1998/namespace",
    "p14": "http://schemas.microsoft.com/office/powerpoint/2010/main",
    "p15": "http://schemas.microsoft.com/office/powerpoint/2012/main",
}


class PPTXSchemaValidator(BaseSchemaValidator):
    """Validator for PPTX (PowerPoint) documents.

    Performs comprehensive validation of unpacked PPTX files including:
    - XML well-formedness
    - Namespace declarations
    - Unique ID validation
    - UUID ID validation
    - File reference integrity
    - Slide layout ID validation
    - Content type validation
    - XSD schema validation
    - Notes slide reference validation
    - Relationship ID validation
    - Duplicate slide layout validation
    """

    # XPath prefix for PresentationML namespace
    P_NS = f"{{{PRESENTATIONML_NAMESPACE}}}"

    def validate(self) -> bool:
        """Run all PPTX validation checks.

        Returns:
            True if all validations pass, False otherwise.
        """
        # Run all validation tests
        self._validate_xml_wellformedness()
        self._validate_namespace_declarations()
        self._validate_unique_ids()
        self.validate_uuid_ids()
        self._validate_file_references()
        self.validate_slide_layout_ids()
        self._validate_content_types()
        self._validate_xsd_schema()
        self.validate_notes_slide_references()
        self._validate_relationship_id_references()
        self.validate_no_duplicate_slide_layouts()

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
        presentation_xml = self.unpacked_dir / "ppt" / "presentation.xml"

        if not presentation_xml.exists():
            self.add_result(
                name="Namespace Declarations",
                passed=False,
                message="presentation.xml not found",
            )
            return

        try:
            content = self.read_file(presentation_xml)
            # Check for main PresentationML namespace
            has_pres_ns = PRESENTATIONML_NAMESPACE in content

            # Check for relationships namespace
            rel_ns = PPTX_NAMESPACES["r"]
            has_rel_ns = rel_ns in content

            missing = []
            if not has_pres_ns:
                missing.append(f"PresentationML namespace: {PRESENTATIONML_NAMESPACE}")
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
                message=f"Error reading presentation.xml: {e}",
            )

    def _validate_unique_ids(self) -> None:
        """Validate that IDs are unique within each XML file."""
        xml_files = self.get_xml_files()
        errors: list[str] = []

        # Patterns for common ID attributes in PPTX
        id_patterns = [
            re.compile(r'id="(\d+)"'),
            re.compile(r'r:id="([^"]+)"'),
        ]

        for xml_file in xml_files:
            try:
                content = self.read_file(xml_file)

                for pattern in id_patterns:
                    ids = pattern.findall(content)
                    seen: dict[str, int] = {}

                    for id_val in ids:
                        seen[id_val] = seen.get(id_val, 0) + 1

                    # For numeric IDs (shape IDs), duplicates within the same file are errors
                    if 'id="' in pattern.pattern and '\\d+' in pattern.pattern:
                        duplicates = [k for k, v in seen.items() if v > 1]
                        if duplicates:
                            errors.append(
                                f"{xml_file.name}: Duplicate id values: {duplicates}"
                            )

            except Exception as e:
                errors.append(f"{xml_file.name}: Error checking IDs: {e}")

        self.add_result(
            name="Unique IDs",
            passed=len(errors) == 0,
            message=f"Checked {len(xml_files)} files for ID uniqueness",
            details=errors if errors else None,
        )

    def validate_uuid_ids(self) -> None:
        """Validate that IDs that should be UUIDs are properly formatted.

        Checks IDs in specific contexts where UUID format is expected,
        such as creationId attributes.
        """
        xml_files = self.get_xml_files()
        errors: list[str] = []
        uuid_ids_checked = 0

        for xml_file in xml_files:
            try:
                tree = SafeET.parse(xml_file)
                root = tree.getroot()
                rel_path = str(xml_file.relative_to(self.unpacked_dir))

                # Find elements that commonly use UUID-style IDs
                for elem in root.iter():
                    # Check for guid/uuid attributes
                    for attr_name in ["guid", "uuid", "creationId"]:
                        attr_value = elem.get(attr_name)
                        if attr_value:
                            uuid_ids_checked += 1
                            if not self._looks_like_uuid(attr_value):
                                # Some creationId values may be numeric, which is valid
                                if attr_name == "creationId" and attr_value.isdigit():
                                    continue
                                errors.append(
                                    f"{rel_path}: Invalid UUID format for {attr_name}='{attr_value}'"
                                )

                    # Also check id attribute if it looks like a UUID pattern
                    id_value = elem.get("id")
                    if id_value and self._looks_like_uuid(id_value):
                        uuid_ids_checked += 1
                        # If it looks like a UUID, validate it's properly formatted
                        if not self._is_valid_uuid(id_value):
                            errors.append(
                                f"{rel_path}: Malformed UUID ID: '{id_value}'"
                            )

            except ET.ParseError:
                # Skip files that can't be parsed (handled in well-formedness check)
                continue

        self.add_result(
            name="UUID ID Validation",
            passed=len(errors) == 0,
            message=f"Checked {uuid_ids_checked} UUID-style IDs",
            details=errors[:10] if errors else None,
        )

    def _looks_like_uuid(self, value: str) -> bool:
        """Check if a string looks like it could be a UUID.

        Args:
            value: The string to check.

        Returns:
            True if the value appears to be a UUID, False otherwise.
        """
        if not value:
            return False

        # Remove common UUID wrappers (curly braces)
        cleaned = value.strip("{}").lower()

        # UUID pattern: 8-4-4-4-12 hex digits
        uuid_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"

        return bool(re.match(uuid_pattern, cleaned))

    def _is_valid_uuid(self, value: str) -> bool:
        """Validate that a UUID-like string is properly formatted.

        Args:
            value: The UUID string to validate.

        Returns:
            True if the UUID is valid, False otherwise.
        """
        return self._looks_like_uuid(value)

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

    def validate_slide_layout_ids(self) -> None:
        """Validate that slide layout references are valid.

        Checks that each slide properly references a slide layout and
        that the referenced layout exists.
        """
        slides_dir = self.unpacked_dir / "ppt" / "slides"

        if not slides_dir.exists():
            self.add_result(
                name="Slide Layout IDs",
                passed=True,
                message="No slides directory found (skipped)",
            )
            return

        slide_files = list(slides_dir.glob("slide*.xml"))
        errors: list[str] = []

        for slide_file in slide_files:
            try:
                # Find the corresponding .rels file
                rels_file = slides_dir / "_rels" / f"{slide_file.name}.rels"

                if not rels_file.exists():
                    errors.append(f"{slide_file.name}: Missing relationship file")
                    continue

                # Parse the .rels file to find slide layout reference
                rels_tree = SafeET.parse(rels_file)
                rels_root = rels_tree.getroot()
                rel_ns = "{http://schemas.openxmlformats.org/package/2006/relationships}"

                layout_found = False
                for rel in rels_root.findall(f".//{rel_ns}Relationship"):
                    rel_type = rel.get("Type", "")

                    if "slideLayout" in rel_type:
                        layout_found = True
                        target = rel.get("Target", "")

                        if target:
                            # Resolve layout path
                            if target.startswith("/"):
                                layout_path = self.unpacked_dir / target.lstrip("/")
                            else:
                                layout_path = (slides_dir / target).resolve()

                            if not layout_path.exists():
                                errors.append(
                                    f"{slide_file.name}: Referenced layout not found: {target}"
                                )

                if not layout_found:
                    errors.append(f"{slide_file.name}: No slide layout relationship found")

            except Exception as e:
                errors.append(f"{slide_file.name}: Error checking layout: {e}")

        self.add_result(
            name="Slide Layout IDs",
            passed=len(errors) == 0,
            message=f"Checked {len(slide_files)} slides for layout references",
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

            required_parts = ["/ppt/presentation.xml"]
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
        presentation_xml = self.unpacked_dir / "ppt" / "presentation.xml"

        if not presentation_xml.exists():
            self.add_result(
                name="XSD Schema Validation",
                passed=False,
                message="presentation.xml not found",
            )
            return

        try:
            tree = SafeET.parse(presentation_xml)
            root = tree.getroot()

            errors = []

            # Check root element is p:presentation
            expected_root = f"{{{PRESENTATIONML_NAMESPACE}}}presentation"
            if root.tag != expected_root:
                errors.append(f"Root element should be {expected_root}, found {root.tag}")

            # Check for required child elements
            # p:sldIdLst (slide ID list) is typically present
            sld_id_lst = root.find(f".//{{{PRESENTATIONML_NAMESPACE}}}sldIdLst")
            if sld_id_lst is None:
                # Not necessarily an error - empty presentations may not have this
                pass

            # Validate slide files
            slides_dir = self.unpacked_dir / "ppt" / "slides"
            if slides_dir.exists():
                slide_files = list(slides_dir.glob("slide*.xml"))
                for slide_file in slide_files:
                    try:
                        slide_tree = SafeET.parse(slide_file)
                        slide_root = slide_tree.getroot()

                        # Check root element is p:sld
                        expected_sld = f"{{{PRESENTATIONML_NAMESPACE}}}sld"
                        if slide_root.tag != expected_sld:
                            errors.append(
                                f"{slide_file.name}: Root should be {expected_sld}, found {slide_root.tag}"
                            )

                        # Check for required p:cSld (common slide data)
                        c_sld = slide_root.find(f".//{{{PRESENTATIONML_NAMESPACE}}}cSld")
                        if c_sld is None:
                            errors.append(f"{slide_file.name}: Missing p:cSld element")

                    except ET.ParseError as e:
                        errors.append(f"{slide_file.name}: Parse error - {e}")

            self.add_result(
                name="XSD Schema Validation",
                passed=len(errors) == 0,
                message="Validated presentation structure",
                details=errors[:10] if errors else None,
            )

        except Exception as e:
            self.add_result(
                name="XSD Schema Validation",
                passed=False,
                message=f"Error during schema validation: {e}",
            )

    def validate_notes_slide_references(self) -> None:
        """Validate that notes slide references are valid.

        Checks that slides with notes references point to existing notes slides.
        """
        slides_dir = self.unpacked_dir / "ppt" / "slides"
        slides_rels_dir = slides_dir / "_rels" if slides_dir.exists() else None

        if not slides_rels_dir or not slides_rels_dir.exists():
            self.add_result(
                name="Notes Slide References",
                passed=True,
                message="No slides relationships directory found (skipped)",
            )
            return

        rels_files = list(slides_rels_dir.glob("*.rels"))
        errors: list[str] = []
        notes_refs_checked = 0
        rel_ns = "{http://schemas.openxmlformats.org/package/2006/relationships}"

        for rels_file in rels_files:
            try:
                tree = SafeET.parse(rels_file)
                root = tree.getroot()

                for rel in root.findall(f".//{rel_ns}Relationship"):
                    rel_type = rel.get("Type", "")

                    if "notesSlide" in rel_type:
                        notes_refs_checked += 1
                        target = rel.get("Target", "")

                        if target:
                            # Resolve notes slide path
                            if target.startswith("/"):
                                notes_path = self.unpacked_dir / target.lstrip("/")
                            else:
                                notes_path = (slides_dir / target).resolve()

                            if not notes_path.exists():
                                errors.append(
                                    f"{rels_file.name}: Notes slide not found: {target}"
                                )

            except Exception as e:
                errors.append(f"{rels_file.name}: Error checking notes: {e}")

        self.add_result(
            name="Notes Slide References",
            passed=len(errors) == 0,
            message=f"Checked {notes_refs_checked} notes slide references",
            details=errors if errors else None,
        )

    def _validate_relationship_id_references(self) -> None:
        """Validate that relationship ID references (r:id) are valid."""
        presentation_xml = self.unpacked_dir / "ppt" / "presentation.xml"
        presentation_rels = self.unpacked_dir / "ppt" / "_rels" / "presentation.xml.rels"

        if not presentation_xml.exists():
            self.add_result(
                name="Relationship ID References",
                passed=False,
                message="presentation.xml not found",
            )
            return

        try:
            # Get all defined relationship IDs from presentation.xml.rels
            defined_ids: set[str] = set()

            if presentation_rels.exists():
                rels_tree = SafeET.parse(presentation_rels)
                rels_root = rels_tree.getroot()
                rel_ns = "{http://schemas.openxmlformats.org/package/2006/relationships}"

                for rel in rels_root.findall(f".//{rel_ns}Relationship"):
                    rel_id = rel.get("Id", "")
                    if rel_id:
                        defined_ids.add(rel_id)

            # Get all referenced relationship IDs in presentation
            pres_content = self.read_file(presentation_xml)
            r_id_pattern = re.compile(r'r:(?:id|embed|link)="([^"]+)"')
            referenced_ids = set(r_id_pattern.findall(pres_content))

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

    def validate_no_duplicate_slide_layouts(self) -> None:
        """Validate that there are no duplicate slide layout references.

        Checks that slide masters do not have duplicate references to
        the same slide layout, which could cause corruption.
        """
        masters_dir = self.unpacked_dir / "ppt" / "slideMasters"
        masters_rels_dir = masters_dir / "_rels" if masters_dir.exists() else None

        if not masters_rels_dir or not masters_rels_dir.exists():
            self.add_result(
                name="Duplicate Slide Layouts",
                passed=True,
                message="No slide masters relationships directory found (skipped)",
            )
            return

        rels_files = list(masters_rels_dir.glob("*.rels"))
        errors: list[str] = []
        rel_ns = "{http://schemas.openxmlformats.org/package/2006/relationships}"

        for rels_file in rels_files:
            try:
                tree = SafeET.parse(rels_file)
                root = tree.getroot()

                # Track layout targets to detect duplicates within a master
                layout_targets: list[str] = []

                for rel in root.findall(f".//{rel_ns}Relationship"):
                    rel_type = rel.get("Type", "")

                    if "slideLayout" in rel_type:
                        target = rel.get("Target", "")
                        if target:
                            # Normalize the target path for comparison
                            normalized_target = target.replace("\\", "/").lower()
                            if normalized_target in layout_targets:
                                errors.append(
                                    f"{rels_file.name}: Duplicate layout reference: {target}"
                                )
                            else:
                                layout_targets.append(normalized_target)

            except Exception as e:
                errors.append(f"{rels_file.name}: Error checking layouts: {e}")

        self.add_result(
            name="Duplicate Slide Layouts",
            passed=len(errors) == 0,
            message=f"Checked {len(rels_files)} slide master relationship files",
            details=errors if errors else None,
        )
