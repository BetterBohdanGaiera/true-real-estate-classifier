"""
Base validator class for OOXML documents.

Provides foundational validation infrastructure for Office Open XML documents
including XML well-formedness, namespace validation, ID uniqueness checks,
relationship validation, and XSD schema validation.

This module uses lxml for robust XML parsing and XSD schema validation.
"""

import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from lxml import etree
from pydantic import BaseModel


class ValidationResult(BaseModel):
    """Result of a single validation check."""

    name: str
    passed: bool
    message: str | None = None
    details: list[str] | None = None


class BaseSchemaValidator(ABC):
    """
    Abstract base class for OOXML document validators.

    Provides common validation methods for Office Open XML documents including:
    - XML well-formedness checking
    - Namespace declaration validation
    - Unique ID validation
    - Relationship file (.rels) validation
    - Content Types validation
    - XSD schema validation

    Subclasses should implement the `validate()` method and define
    document-specific SCHEMA_MAPPINGS and UNIQUE_ID_REQUIREMENTS.

    Attributes:
        unpacked_dir: Path to the unpacked Office document directory.
        original_file: Path to the original Office file (.docx/.pptx/.xlsx).
        verbose: Enable verbose output for debugging.
        results: List of validation results from all checks.
        errors: List of error messages encountered during validation.
        warnings: List of warning messages encountered during validation.
    """

    # -------------------------------------------------------------------------
    # OOXML Namespace Constants
    # -------------------------------------------------------------------------

    # Markup Compatibility namespace (for mc:Ignorable, mc:Choice, etc.)
    MC_NAMESPACE = "http://schemas.openxmlformats.org/markup-compatibility/2006"

    # Standard XML namespace
    XML_NAMESPACE = "http://www.w3.org/XML/1998/namespace"

    # Package relationships namespace
    PACKAGE_RELATIONSHIPS_NAMESPACE = (
        "http://schemas.openxmlformats.org/package/2006/relationships"
    )

    # Content Types namespace
    CONTENT_TYPES_NAMESPACE = (
        "http://schemas.openxmlformats.org/package/2006/content-types"
    )

    # Office Document relationships namespace
    OFFICE_RELATIONSHIPS_NAMESPACE = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    )

    # WordprocessingML main namespace
    WML_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

    # PresentationML main namespace
    PML_NAMESPACE = "http://schemas.openxmlformats.org/presentationml/2006/main"

    # SpreadsheetML main namespace
    SML_NAMESPACE = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"

    # DrawingML main namespace
    DML_NAMESPACE = "http://schemas.openxmlformats.org/drawingml/2006/main"

    # DrawingML WordprocessingDrawing namespace
    WP_NAMESPACE = (
        "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
    )

    # DrawingML Picture namespace
    PIC_NAMESPACE = "http://schemas.openxmlformats.org/drawingml/2006/picture"

    # VML namespace
    VML_NAMESPACE = "urn:schemas-microsoft-com:vml"

    # Office VML namespace
    OFFICE_VML_NAMESPACE = "urn:schemas-microsoft-com:office:office"

    # Microsoft Office 2010+ Word namespaces
    W14_NAMESPACE = "http://schemas.microsoft.com/office/word/2010/wordml"
    W15_NAMESPACE = "http://schemas.microsoft.com/office/word/2012/wordml"
    W16_NAMESPACE = "http://schemas.microsoft.com/office/word/2018/wordml"

    # Microsoft Office PowerPoint namespaces
    P14_NAMESPACE = "http://schemas.microsoft.com/office/powerpoint/2010/main"
    P15_NAMESPACE = "http://schemas.microsoft.com/office/powerpoint/2012/main"

    # Set of all standard OOXML namespaces for quick lookup
    OOXML_NAMESPACES = {
        MC_NAMESPACE,
        PACKAGE_RELATIONSHIPS_NAMESPACE,
        CONTENT_TYPES_NAMESPACE,
        OFFICE_RELATIONSHIPS_NAMESPACE,
        WML_NAMESPACE,
        PML_NAMESPACE,
        SML_NAMESPACE,
        DML_NAMESPACE,
        WP_NAMESPACE,
        PIC_NAMESPACE,
        VML_NAMESPACE,
        OFFICE_VML_NAMESPACE,
        W14_NAMESPACE,
        W15_NAMESPACE,
        W16_NAMESPACE,
        P14_NAMESPACE,
        P15_NAMESPACE,
    }

    # -------------------------------------------------------------------------
    # Schema Mappings (to be overridden by subclasses)
    # -------------------------------------------------------------------------

    # Maps relative file paths to their XSD schema names
    # Example: {"word/document.xml": "wml.xsd"}
    SCHEMA_MAPPINGS: dict[str, str] = {}

    # -------------------------------------------------------------------------
    # Unique ID Requirements (to be overridden by subclasses)
    # -------------------------------------------------------------------------

    # Maps element local names to (attribute_name, scope) tuples
    # scope can be: "document" (unique across whole document) or "parent" (unique within parent)
    # Example: {"ins": ("id", "document"), "bookmarkStart": ("id", "document")}
    UNIQUE_ID_REQUIREMENTS: dict[str, tuple[str, str]] = {}

    # -------------------------------------------------------------------------
    # Template tag patterns (for removing Jinja2/Django-style template tags)
    # -------------------------------------------------------------------------

    TEMPLATE_TAG_PATTERN = re.compile(r"\{\{.*?\}\}|\{%.*?%\}")

    def __init__(
        self,
        unpacked_dir: Path | str,
        original_file: Path | str,
        verbose: bool = False,
    ) -> None:
        """
        Initialize the base schema validator.

        Args:
            unpacked_dir: Path to the unpacked Office document directory.
            original_file: Path to the original Office file (.docx/.pptx/.xlsx).
            verbose: Enable verbose output for debugging.
        """
        self.unpacked_dir = Path(unpacked_dir)
        self.original_file = Path(original_file)
        self.verbose = verbose
        self.results: list[ValidationResult] = []
        self.errors: list[str] = []
        self.warnings: list[str] = []

        # Schema directory path (relative to this file's location)
        self._schemas_dir = Path(__file__).parent.parent.parent / "schemas"

    # -------------------------------------------------------------------------
    # Abstract Methods
    # -------------------------------------------------------------------------

    @abstractmethod
    def validate(self) -> bool:
        """
        Perform all validations for this document type.

        Returns:
            bool: True if all validations pass, False otherwise.
        """
        pass

    # -------------------------------------------------------------------------
    # Result Management Methods
    # -------------------------------------------------------------------------

    def add_result(
        self,
        name: str,
        passed: bool,
        message: str | None = None,
        details: list[str] | None = None,
    ) -> None:
        """
        Record a validation result.

        Args:
            name: Name of the validation check.
            passed: Whether the check passed.
            message: Optional message describing the result.
            details: Optional list of detailed findings.
        """
        result = ValidationResult(
            name=name,
            passed=passed,
            message=message,
            details=details,
        )
        self.results.append(result)

        if self.verbose:
            status = "PASS" if passed else "FAIL"
            print(f"[{status}] {name}")
            if message:
                print(f"       {message}")
            if details:
                for detail in details:
                    print(f"       - {detail}")

    def print_summary(self) -> None:
        """Print a summary of all validation results."""
        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)
        print(f"\nValidation Summary: {passed}/{total} checks passed")

        if not self.verbose:
            failed = [r for r in self.results if not r.passed]
            if failed:
                print("\nFailed checks:")
                for result in failed:
                    print(f"  - {result.name}")
                    if result.message:
                        print(f"    {result.message}")

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _log(self, message: str) -> None:
        """Log a message if verbose mode is enabled."""
        if self.verbose:
            print(f"  {message}")

    def _log_error(self, message: str) -> None:
        """Log an error and add to errors list."""
        self.errors.append(message)
        print(f"  ERROR: {message}")

    def _log_warning(self, message: str) -> None:
        """Log a warning and add to warnings list."""
        self.warnings.append(message)
        if self.verbose:
            print(f"  WARNING: {message}")

    def _get_schema_path(self, schema_name: str) -> Optional[Path]:
        """
        Get the full path to an XSD schema file.

        Args:
            schema_name: Name of the schema file (e.g., "wml.xsd").

        Returns:
            Path to the schema file if it exists, None otherwise.
        """
        schema_path = self._schemas_dir / schema_name
        if schema_path.exists():
            return schema_path
        return None

    def get_xml_files(self, pattern: str = "*.xml") -> list[Path]:
        """
        Get all XML files matching a pattern in the unpacked directory.

        Args:
            pattern: Glob pattern to match files.

        Returns:
            List of paths to matching XML files.
        """
        return sorted(list(self.unpacked_dir.rglob(pattern)))

    def get_rels_files(self) -> list[Path]:
        """
        Get all relationship files in the unpacked directory.

        Returns:
            List of paths to .rels files.
        """
        return sorted(list(self.unpacked_dir.rglob("*.rels")))

    def _get_all_xml_files(self) -> list[Path]:
        """
        Get all XML and .rels files in the unpacked directory.

        Returns:
            List of paths to XML and .rels files.
        """
        xml_files = list(self.unpacked_dir.rglob("*.xml"))
        xml_files.extend(self.unpacked_dir.rglob("*.rels"))
        return sorted(xml_files)

    def read_file(self, file_path: Path) -> str:
        """
        Read the contents of a file.

        Args:
            file_path: Path to the file.

        Returns:
            File contents as string.
        """
        return file_path.read_text(encoding="utf-8")

    def _parse_xml(self, xml_file: Path) -> Optional[etree._Element]:
        """
        Parse an XML file using lxml and return the root element.

        Args:
            xml_file: Path to the XML file.

        Returns:
            Root element if parsing succeeds, None otherwise.
        """
        try:
            parser = etree.XMLParser(remove_blank_text=False, recover=False)
            tree = etree.parse(str(xml_file), parser)
            return tree.getroot()
        except etree.XMLSyntaxError as e:
            self._log_error(f"XML syntax error in {xml_file.name}: {e}")
            return None
        except Exception as e:
            self._log_error(f"Failed to parse {xml_file.name}: {e}")
            return None

    def _get_relative_path(self, xml_file: Path) -> str:
        """
        Get the relative path of a file from the unpacked directory.

        Args:
            xml_file: Absolute path to the file.

        Returns:
            Relative path as string.
        """
        return str(xml_file.relative_to(self.unpacked_dir))

    def _clean_ignorable_namespaces(
        self, root: etree._Element
    ) -> etree._Element:
        """
        Remove namespace declarations that are marked as ignorable via mc:Ignorable.

        This is useful for XSD validation as ignorable extensions may not be
        in the schema.

        Args:
            root: The root element to clean.

        Returns:
            A copy of the root element with ignorable namespaces removed.
        """
        # Create a deep copy to avoid modifying the original
        root_copy = etree.fromstring(etree.tostring(root))

        # Find mc:Ignorable attribute
        mc_prefix = None
        for prefix, uri in root_copy.nsmap.items():
            if uri == self.MC_NAMESPACE:
                mc_prefix = prefix
                break

        if mc_prefix is None:
            return root_copy

        # Get the list of ignorable prefixes
        ignorable_attr = f"{{{self.MC_NAMESPACE}}}Ignorable"
        ignorable_str = root_copy.get(ignorable_attr, "")
        ignorable_prefixes = set(ignorable_str.split())

        if not ignorable_prefixes:
            return root_copy

        # Get namespaces to remove
        namespaces_to_remove = set()
        for prefix in ignorable_prefixes:
            if prefix in root_copy.nsmap:
                namespaces_to_remove.add(root_copy.nsmap[prefix])

        # Remove elements from ignorable namespaces
        for ns in namespaces_to_remove:
            for elem in root_copy.iter():
                # Remove elements in ignorable namespace
                if elem.tag.startswith(f"{{{ns}}}"):
                    parent = elem.getparent()
                    if parent is not None:
                        parent.remove(elem)
                # Remove attributes in ignorable namespace
                else:
                    attrs_to_remove = [
                        attr
                        for attr in elem.attrib
                        if attr.startswith(f"{{{ns}}}")
                    ]
                    for attr in attrs_to_remove:
                        del elem.attrib[attr]

        return root_copy

    def _remove_template_tags(self, content: str) -> str:
        """
        Remove template tags (Jinja2/Django style) from content.

        Args:
            content: The string content to clean.

        Returns:
            Content with template tags removed.
        """
        return self.TEMPLATE_TAG_PATTERN.sub("", content)

    # -------------------------------------------------------------------------
    # Validation Methods
    # -------------------------------------------------------------------------

    def validate_xml(self) -> bool:
        """
        Check XML well-formedness of all XML files.

        Parses each XML file using lxml to verify it is well-formed.

        Returns:
            bool: True if all XML files are well-formed.
        """
        print("Validating XML well-formedness...")
        all_valid = True
        xml_files = self._get_all_xml_files()
        errors: list[str] = []

        for xml_file in xml_files:
            rel_path = self._get_relative_path(xml_file)
            self._log(f"Checking {rel_path}")

            try:
                parser = etree.XMLParser(remove_blank_text=False, recover=False)
                etree.parse(str(xml_file), parser)
            except etree.XMLSyntaxError as e:
                errors.append(f"{xml_file.name}: {e}")
                all_valid = False
            except Exception as e:
                errors.append(f"{xml_file.name}: {e}")
                all_valid = False

        self.add_result(
            name="XML Well-formedness",
            passed=all_valid,
            message=f"Checked {len(xml_files)} XML files",
            details=errors if errors else None,
        )

        return all_valid

    def validate_namespaces(self) -> bool:
        """
        Check that namespace declarations are valid and properly declared.

        Validates that all namespace prefixes used in elements and attributes
        are properly declared in the document.

        Returns:
            bool: True if all namespace declarations are valid.
        """
        print("Validating namespace declarations...")
        all_valid = True
        errors: list[str] = []

        for xml_file in self._get_all_xml_files():
            root = self._parse_xml(xml_file)
            if root is None:
                all_valid = False
                continue

            rel_path = self._get_relative_path(xml_file)

            # Check for undefined namespace prefixes in element names
            for elem in root.iter():
                if elem.tag.startswith("{"):
                    continue  # Properly namespaced (Clark notation)

                if ":" in elem.tag:
                    prefix = elem.tag.split(":")[0]
                    if prefix not in root.nsmap:
                        errors.append(
                            f"{rel_path}: Undefined namespace prefix '{prefix}' in element {elem.tag}"
                        )
                        all_valid = False

        self.add_result(
            name="Namespace Declarations",
            passed=all_valid,
            message="Checked namespace declarations in all XML files",
            details=errors if errors else None,
        )

        return all_valid

    def validate_unique_ids(self) -> bool:
        """
        Check that IDs required to be unique are actually unique.

        Uses UNIQUE_ID_REQUIREMENTS to determine which elements need unique IDs.
        Each entry maps element local names to (attribute_name, scope) tuples.

        Returns:
            bool: True if all required IDs are unique.
        """
        if not self.UNIQUE_ID_REQUIREMENTS:
            self._log("No unique ID requirements defined, skipping")
            return True

        print("Validating unique IDs...")
        all_valid = True
        errors: list[str] = []

        # Track IDs seen at document scope
        document_ids: dict[str, dict[str, list[str]]] = {}

        for xml_file in self._get_all_xml_files():
            root = self._parse_xml(xml_file)
            if root is None:
                continue

            rel_path = self._get_relative_path(xml_file)

            # Track IDs seen at parent scope (reset for each file)
            parent_ids: dict[etree._Element, dict[str, set[str]]] = {}

            for elem in root.iter():
                local_name = etree.QName(elem.tag).localname

                if local_name not in self.UNIQUE_ID_REQUIREMENTS:
                    continue

                attr_name, scope = self.UNIQUE_ID_REQUIREMENTS[local_name]

                # Get the attribute value
                # Try with common namespace prefixes first
                id_value = None
                for ns_prefix in ["w", "p", "a", "r", ""]:
                    if ns_prefix and ns_prefix in elem.nsmap:
                        ns_uri = elem.nsmap[ns_prefix]
                        full_attr = f"{{{ns_uri}}}{attr_name}"
                        id_value = elem.get(full_attr)
                        if id_value is not None:
                            break

                # Try without namespace
                if id_value is None:
                    id_value = elem.get(attr_name)

                if id_value is None:
                    continue  # Attribute not present

                if scope == "document":
                    # Check uniqueness across the entire document
                    if local_name not in document_ids:
                        document_ids[local_name] = {}

                    if id_value in document_ids[local_name]:
                        errors.append(
                            f"Duplicate {local_name}/@{attr_name}='{id_value}' "
                            f"in {rel_path} (first seen in "
                            f"{document_ids[local_name][id_value][0]})"
                        )
                        all_valid = False
                        document_ids[local_name][id_value].append(rel_path)
                    else:
                        document_ids[local_name][id_value] = [rel_path]

                elif scope == "parent":
                    # Check uniqueness within parent element
                    parent = elem.getparent()
                    if parent is None:
                        continue

                    if parent not in parent_ids:
                        parent_ids[parent] = {}
                    if local_name not in parent_ids[parent]:
                        parent_ids[parent][local_name] = set()

                    if id_value in parent_ids[parent][local_name]:
                        errors.append(
                            f"Duplicate {local_name}/@{attr_name}='{id_value}' "
                            f"within same parent in {rel_path}"
                        )
                        all_valid = False
                    else:
                        parent_ids[parent][local_name].add(id_value)

        self.add_result(
            name="Unique IDs",
            passed=all_valid,
            message="Checked ID uniqueness according to requirements",
            details=errors[:10] if errors else None,  # Limit to first 10
        )

        return all_valid

    def validate_file_references(self) -> bool:
        """
        Validate that all .rels file references point to existing files.

        Checks each Relationship element in .rels files to ensure the
        Target attribute points to an existing file (for internal references).

        Returns:
            bool: True if all referenced files exist.
        """
        print("Validating relationship file references...")
        all_valid = True
        errors: list[str] = []

        rels_files = self.get_rels_files()

        for rels_file in rels_files:
            root = self._parse_xml(rels_file)
            if root is None:
                all_valid = False
                continue

            # Get the directory that this .rels file describes
            # _rels/foo.xml.rels describes ../foo.xml
            rels_dir = rels_file.parent
            if rels_dir.name == "_rels":
                base_dir = rels_dir.parent
            else:
                base_dir = rels_dir

            rel_path = self._get_relative_path(rels_file)

            for relationship in root.iter():
                if not relationship.tag.endswith("}Relationship"):
                    continue

                target = relationship.get("Target")
                target_mode = relationship.get("TargetMode", "Internal")

                if target is None:
                    continue

                # Skip external targets
                if target_mode == "External":
                    self._log(f"External target: {target}")
                    continue

                # Skip absolute URIs
                if target.startswith("http://") or target.startswith("https://"):
                    continue

                # Resolve the target path
                if target.startswith("/"):
                    # Absolute path from package root
                    target_path = self.unpacked_dir / target.lstrip("/")
                else:
                    # Relative path from base directory
                    target_path = (base_dir / target).resolve()

                # Check if the target exists
                if not target_path.exists():
                    rel_type = relationship.get("Type", "unknown")
                    rel_id = relationship.get("Id", "unknown")
                    errors.append(
                        f"{rel_path}: Missing target '{target}' (Id='{rel_id}')"
                    )
                    all_valid = False

        self.add_result(
            name="File References",
            passed=all_valid,
            message=f"Checked {len(rels_files)} relationship files",
            details=errors if errors else None,
        )

        return all_valid

    def validate_all_relationship_ids(self) -> bool:
        """
        Validate that all r:id attributes reference valid relationship IDs.

        Builds a map of all relationship IDs from .rels files, then checks
        that all r:id, r:embed, and r:link references in XML files are valid.

        Returns:
            bool: True if all relationship ID references are valid.
        """
        print("Validating relationship ID references...")
        all_valid = True
        errors: list[str] = []

        # Build a map of all relationship IDs from .rels files
        rels_map: dict[Path, set[str]] = {}

        for rels_file in self.get_rels_files():
            root = self._parse_xml(rels_file)
            if root is None:
                continue

            # Determine which file this .rels describes
            rels_dir = rels_file.parent
            if rels_dir.name == "_rels":
                # Pattern: path/_rels/filename.xml.rels -> path/filename.xml
                described_file = rels_dir.parent / rels_file.stem
            else:
                described_file = rels_dir / rels_file.stem

            rel_ids = set()
            for relationship in root.iter():
                if relationship.tag.endswith("}Relationship"):
                    rel_id = relationship.get("Id")
                    if rel_id:
                        rel_ids.add(rel_id)

            rels_map[described_file] = rel_ids

        # Check r:id references in all XML files
        for xml_file in self.get_xml_files():
            root = self._parse_xml(xml_file)
            if root is None:
                continue

            # Find the .rels file that describes this XML file
            available_ids = rels_map.get(xml_file, set())

            # Also check for a .rels file in _rels subdirectory
            rels_file_path = xml_file.parent / "_rels" / f"{xml_file.name}.rels"
            if rels_file_path in rels_map:
                available_ids = available_ids.union(rels_map[rels_file_path])

            rel_path = self._get_relative_path(xml_file)

            for elem in root.iter():
                # Look for r:id, r:embed, r:link attributes
                for attr_name in ["id", "embed", "link"]:
                    # Try with relationships namespace
                    for prefix, ns_uri in (elem.nsmap or {}).items():
                        if "relationships" in ns_uri.lower():
                            full_attr = f"{{{ns_uri}}}{attr_name}"
                            ref_id = elem.get(full_attr)
                            if ref_id and available_ids and ref_id not in available_ids:
                                errors.append(
                                    f"{rel_path}: Unresolved relationship "
                                    f"reference {prefix}:{attr_name}='{ref_id}'"
                                )

        self.add_result(
            name="Relationship ID References",
            passed=len(errors) == 0,
            message="Checked relationship ID references",
            details=errors[:10] if errors else None,  # Limit to first 10
        )

        return len(errors) == 0

    def validate_content_types(self) -> bool:
        """
        Validate the [Content_Types].xml file.

        Checks that:
        - The file exists and is well-formed
        - All Override PartNames reference existing files
        - Default extensions cover files that exist

        Returns:
            bool: True if Content_Types.xml is valid.
        """
        print("Validating [Content_Types].xml...")
        all_valid = True
        errors: list[str] = []

        content_types_file = self.unpacked_dir / "[Content_Types].xml"

        if not content_types_file.exists():
            self.add_result(
                name="Content Types",
                passed=False,
                message="[Content_Types].xml not found",
            )
            return False

        root = self._parse_xml(content_types_file)
        if root is None:
            self.add_result(
                name="Content Types",
                passed=False,
                message="Failed to parse [Content_Types].xml",
            )
            return False

        ct_ns = f"{{{self.CONTENT_TYPES_NAMESPACE}}}"

        # Collect default extensions
        default_extensions: set[str] = set()
        defaults = root.findall(f".//{ct_ns}Default")
        for default in defaults:
            ext = default.get("Extension", "").lower()
            if ext:
                default_extensions.add(ext)

        # Check Override part names
        overrides = root.findall(f".//{ct_ns}Override")
        override_parts: set[str] = set()

        for override in overrides:
            part_name = override.get("PartName", "")
            if part_name:
                override_parts.add(part_name.lstrip("/"))
                # Part names start with /
                part_path = self.unpacked_dir / part_name.lstrip("/")
                if not part_path.exists():
                    errors.append(f"Override references missing file: {part_name}")
                    all_valid = False

        # Check that all files have content types
        all_files = list(self.unpacked_dir.rglob("*"))
        for file_path in all_files:
            if not file_path.is_file():
                continue

            rel_path = self._get_relative_path(file_path)
            ext = file_path.suffix.lower().lstrip(".")

            # Check if file is covered by Default or Override
            if rel_path not in override_parts and ext not in default_extensions:
                self._log_warning(f"File has no content type: {rel_path}")

        self.add_result(
            name="Content Types",
            passed=all_valid,
            message=f"Found {len(overrides)} overrides, {len(defaults)} defaults",
            details=errors if errors else None,
        )

        return all_valid

    def validate_against_xsd(self) -> bool:
        """
        Validate XML files against their XSD schemas.

        Uses SCHEMA_MAPPINGS to determine which schema to use for each file.
        Files without a schema mapping are skipped.

        Returns:
            bool: True if all files validate against their schemas.
        """
        if not self.SCHEMA_MAPPINGS:
            self._log("No schema mappings defined, skipping XSD validation")
            return True

        print("Validating against XSD schemas...")
        all_valid = True
        errors: list[str] = []

        for rel_path, schema_name in self.SCHEMA_MAPPINGS.items():
            xml_file = self.unpacked_dir / rel_path

            if not xml_file.exists():
                self._log(f"Skipping {rel_path}: file not found")
                continue

            if not self.validate_file_against_xsd(xml_file, verbose=self.verbose):
                all_valid = False

        self.add_result(
            name="XSD Schema Validation",
            passed=all_valid,
            message=f"Validated {len(self.SCHEMA_MAPPINGS)} file mappings",
            details=errors if errors else None,
        )

        return all_valid

    def validate_file_against_xsd(
        self,
        xml_file: Path,
        verbose: bool = False,
    ) -> bool:
        """
        Validate a single XML file against its XSD schema.

        Args:
            xml_file: Path to the XML file to validate.
            verbose: Enable verbose output.

        Returns:
            bool: True if the file validates against its schema.
        """
        rel_path = self._get_relative_path(xml_file)

        if rel_path not in self.SCHEMA_MAPPINGS:
            if verbose:
                self._log(f"No schema mapping for {rel_path}")
            return True

        schema_name = self.SCHEMA_MAPPINGS[rel_path]
        schema_path = self._get_schema_path(schema_name)

        if schema_path is None:
            self._log_warning(f"Schema not found: {schema_name}")
            return True  # Don't fail validation if schema is missing

        root = self._parse_xml(xml_file)
        if root is None:
            return False

        # Clean ignorable namespaces for validation
        cleaned_root = self._clean_ignorable_namespaces(root)

        try:
            schema_doc = etree.parse(str(schema_path))
            schema = etree.XMLSchema(schema_doc)

            if schema.validate(cleaned_root):
                if verbose:
                    self._log(f"Valid: {rel_path}")
                return True
            else:
                for error in schema.error_log:
                    self._log_error(
                        f"XSD validation error in {rel_path} "
                        f"(line {error.line}): {error.message}"
                    )
                return False

        except etree.XMLSchemaParseError as e:
            self._log_warning(f"Could not parse schema {schema_name}: {e}")
            return True  # Don't fail validation if schema is invalid

        except Exception as e:
            self._log_error(f"XSD validation failed for {rel_path}: {e}")
            return False
