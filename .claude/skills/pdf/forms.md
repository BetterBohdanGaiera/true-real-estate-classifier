# PDF Form Filling Guide

This guide covers the complete workflow for filling PDF forms, including both fillable (interactive) and non-fillable (static) PDF documents.

## Initial Check

Before proceeding, determine whether the PDF has fillable form fields:

```bash
python scripts/check_fillable_fields.py <file.pdf>
```

This script analyzes the PDF and reports whether it contains interactive form fields. Based on the result, follow either the **Fillable Fields** section or the **Non-Fillable Fields** section below.

---

## Fillable Fields

If the PDF has fillable form fields, follow this workflow:

### Step 1: Extract Field Information

Extract all form field metadata to a JSON file:

```bash
python scripts/extract_form_field_info.py <input.pdf> <field_info.json>
```

This generates a `field_info.json` file with the following format:

```json
[
  {
    "field_id": "first_name",
    "page": 1,
    "rect": [100, 700, 300, 720],
    "type": "text"
  },
  {
    "field_id": "agree_terms",
    "page": 1,
    "rect": [100, 650, 120, 670],
    "type": "checkbox",
    "checked_value": "Yes",
    "unchecked_value": "Off"
  },
  {
    "field_id": "gender",
    "page": 1,
    "rect": [100, 600, 200, 620],
    "type": "radio_group",
    "radio_options": ["Male", "Female", "Other"]
  },
  {
    "field_id": "country",
    "page": 2,
    "rect": [100, 500, 300, 520],
    "type": "choice",
    "choice_options": ["USA", "Canada", "UK", "Other"]
  }
]
```

**Field Types:**

| Type | Description | Additional Properties |
|------|-------------|----------------------|
| `text` | Standard text input field | None |
| `checkbox` | Boolean checkbox | `checked_value`, `unchecked_value` |
| `radio_group` | Radio button group | `radio_options` (array of values) |
| `choice` | Dropdown/select field | `choice_options` (array of values) |

### Step 2: Convert PDF to Images (Optional)

For visual reference when determining field values:

```bash
python scripts/convert_pdf_to_images.py <file.pdf> <output_directory>
```

This creates PNG images of each page for visual inspection.

### Step 3: Create Field Values

Create a `field_values.json` file specifying the values to fill:

```json
[
  {
    "field_id": "first_name",
    "description": "Applicant's first name",
    "page": 1,
    "value": "John"
  },
  {
    "field_id": "agree_terms",
    "description": "Terms and conditions agreement",
    "page": 1,
    "value": "Yes"
  },
  {
    "field_id": "gender",
    "description": "Gender selection",
    "page": 1,
    "value": "Male"
  },
  {
    "field_id": "country",
    "description": "Country of residence",
    "page": 2,
    "value": "USA"
  }
]
```

**Field Values Format:**

| Property | Required | Description |
|----------|----------|-------------|
| `field_id` | Yes | Must match a field_id from field_info.json |
| `description` | Yes | Human-readable description of the field |
| `page` | Yes | Page number where the field appears |
| `value` | Yes | The value to set (for checkboxes, use checked_value or unchecked_value) |

### Step 4: Fill the Form

Execute the fill operation:

```bash
python scripts/fill_fillable_fields.py <input.pdf> <field_values.json> <output.pdf>
```

This creates a new PDF with all specified fields filled.

---

## Non-Fillable Fields

If the PDF does not have fillable form fields, use annotation-based filling:

### Step 1: Convert PDF to Images

First, create images for visual analysis:

```bash
python scripts/convert_pdf_to_images.py <file.pdf> <output_directory>
```

### Step 2: Visual Analysis

Examine the generated images to identify:
- Form field locations (where text should be entered)
- Label positions (field descriptions in the document)
- Exact pixel coordinates for bounding boxes

### Step 3: Create Fields Definition

Create a `fields.json` file defining all field locations and values:

```json
{
  "pages": [
    {
      "page_number": 1,
      "image_width": 2550,
      "image_height": 3300
    },
    {
      "page_number": 2,
      "image_width": 2550,
      "image_height": 3300
    }
  ],
  "form_fields": [
    {
      "page_number": 1,
      "description": "Applicant's full legal name",
      "field_label": "Name",
      "label_bounding_box": [100, 200, 200, 230],
      "entry_bounding_box": [210, 200, 500, 230],
      "entry_text": {
        "text": "John Smith",
        "font_size": 12,
        "font_color": "#000000"
      }
    },
    {
      "page_number": 1,
      "description": "Date of birth in MM/DD/YYYY format",
      "field_label": "DOB",
      "label_bounding_box": [100, 250, 150, 280],
      "entry_bounding_box": [160, 250, 350, 280],
      "entry_text": {
        "text": "01/15/1990"
      }
    },
    {
      "page_number": 2,
      "description": "Signature date",
      "field_label": "Date",
      "label_bounding_box": [400, 700, 450, 730],
      "entry_bounding_box": [460, 700, 600, 730],
      "entry_text": {
        "text": "January 14, 2026",
        "font_size": 10
      }
    }
  ]
}
```

**Fields.json Structure:**

**Pages Array:**

| Property | Required | Description |
|----------|----------|-------------|
| `page_number` | Yes | 1-indexed page number |
| `image_width` | Yes | Width of the page image in pixels |
| `image_height` | Yes | Height of the page image in pixels |

**Form Fields Array:**

| Property | Required | Description |
|----------|----------|-------------|
| `page_number` | Yes | 1-indexed page number where field appears |
| `description` | Yes | Human-readable description of the field purpose |
| `field_label` | Yes | The label text shown in the PDF |
| `label_bounding_box` | Yes | [x1, y1, x2, y2] coordinates of the label |
| `entry_bounding_box` | Yes | [x1, y1, x2, y2] coordinates where text will be placed |
| `entry_text` | Yes | Object containing the text to insert |

**Entry Text Object:**

| Property | Required | Description |
|----------|----------|-------------|
| `text` | Yes | The text value to insert |
| `font_size` | No | Font size in points (default: auto-calculated) |
| `font_color` | No | Hex color code (default: "#000000") |

**Bounding Box Format:**

All bounding boxes use the format `[x1, y1, x2, y2]` where:
- `x1, y1` = top-left corner coordinates
- `x2, y2` = bottom-right corner coordinates
- Coordinates are in pixels, relative to the image dimensions

### Step 4: Validate Bounding Boxes

#### Automated Intersection Check

Run the bounding box validation script:

```bash
python scripts/check_bounding_boxes.py <fields.json>
```

This script checks for:
- Overlapping bounding boxes that might cause rendering issues
- Bounding boxes that extend outside page boundaries
- Invalid coordinate values

#### Manual Visual Validation

Create validation images to visually verify bounding box positions:

```bash
python scripts/create_validation_image.py <page_number> <path_to_fields.json> <input_image_path> <output_image_path>
```

Example:
```bash
python scripts/create_validation_image.py 1 fields.json page_1.png validation_page_1.png
```

**Validation Image Color Coding:**

| Color | Element |
|-------|---------|
| Red rectangles | Entry bounding boxes (where text will be placed) |
| Blue rectangles | Label bounding boxes (field labels in the document) |

Inspect the validation images to ensure:
- Entry boxes are positioned correctly over blank areas
- Entry boxes do not overlap with existing content
- Label boxes accurately highlight the field labels
- All fields are accounted for

### Step 5: Fill the PDF with Annotations

Once validation passes, generate the filled PDF:

```bash
python scripts/fill_pdf_form_with_annotations.py <input.pdf> <fields.json> <output.pdf>
```

This adds text annotations to the PDF at the specified locations.

---

## Script Reference

| Script | Purpose |
|--------|---------|
| `check_fillable_fields.py` | Detect if PDF has fillable form fields |
| `extract_form_field_info.py` | Extract field metadata from fillable PDF |
| `convert_pdf_to_images.py` | Convert PDF pages to PNG images |
| `fill_fillable_fields.py` | Fill interactive form fields |
| `check_bounding_boxes.py` | Validate bounding box definitions |
| `create_validation_image.py` | Generate visual validation images |
| `fill_pdf_form_with_annotations.py` | Add text annotations to non-fillable PDF |

---

## Troubleshooting

### Fillable PDFs

- **Field not filling**: Verify the `field_id` matches exactly (case-sensitive)
- **Checkbox not checking**: Use the exact `checked_value` from field_info.json
- **Radio button not selecting**: Ensure value matches one of the `radio_options`

### Non-Fillable PDFs

- **Text appears in wrong position**: Re-verify bounding box coordinates against validation image
- **Text is cut off**: Increase the entry_bounding_box size or reduce font_size
- **Overlapping text**: Run check_bounding_boxes.py and resolve intersections
