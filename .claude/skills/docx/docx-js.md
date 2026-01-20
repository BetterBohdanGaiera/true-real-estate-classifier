# DOCX Library - Complete Guide for JavaScript/TypeScript

Comprehensive documentation for generating Word documents (.docx) using the `docx` npm package.

## 1. Setup

### Installation

```bash
npm install docx
# or
yarn add docx
# or
pnpm add docx
```

### Core Imports

```typescript
import {
  Document,
  Packer,
  Paragraph,
  TextRun,
  Table,
  TableRow,
  TableCell,
  WidthType,
  AlignmentType,
  HeadingLevel,
  BorderStyle,
  ShadingType,
  ImageRun,
  ExternalHyperlink,
  InternalHyperlink,
  Bookmark,
  PageBreak,
  Header,
  Footer,
  PageNumber,
  NumberFormat,
  Tab,
  TabStopType,
  TabStopPosition,
  LevelFormat,
  UnderlineType,
  VerticalAlign,
  TableOfContents,
  StyleLevel,
  convertInchesToTwip,
  convertMillimetersToTwip,
} from "docx";
import * as fs from "fs";
```

### Basic Document Structure

```typescript
const doc = new Document({
  sections: [
    {
      properties: {
        // Section properties (margins, orientation, etc.)
      },
      children: [
        // Paragraphs, Tables, etc.
      ],
    },
  ],
});

// Generate and save the document
const buffer = await Packer.toBuffer(doc);
fs.writeFileSync("output.docx", buffer);

// Or generate as Blob (for browser)
const blob = await Packer.toBlob(doc);
```

---

## 2. Text & Formatting

### Basic Paragraph

```typescript
new Paragraph({
  text: "Simple paragraph text",
});
```

### Paragraph with Alignment & Spacing

```typescript
new Paragraph({
  alignment: AlignmentType.CENTER, // LEFT, RIGHT, CENTER, JUSTIFIED, BOTH
  spacing: {
    before: 200, // Space before paragraph (in twips, 1 inch = 1440 twips)
    after: 200,  // Space after paragraph
    line: 276,   // Line spacing (276 = 1.15 lines)
  },
  children: [
    new TextRun("Centered text with custom spacing"),
  ],
});
```

### Text Formatting with TextRun

```typescript
new Paragraph({
  children: [
    // Bold text
    new TextRun({
      text: "Bold text",
      bold: true,
    }),

    // Italic text
    new TextRun({
      text: "Italic text",
      italics: true,
    }),

    // Underlined text
    new TextRun({
      text: "Underlined text",
      underline: {
        type: UnderlineType.SINGLE, // SINGLE, DOUBLE, WAVE, DOTTED, DASH, etc.
        color: "000000",
      },
    }),

    // Colored text
    new TextRun({
      text: "Red text",
      color: "FF0000", // Hex color without #
    }),

    // Highlighted text
    new TextRun({
      text: "Highlighted text",
      highlight: "yellow", // yellow, green, cyan, magenta, blue, red, etc.
    }),

    // Strikethrough
    new TextRun({
      text: "Strikethrough text",
      strike: true,
    }),

    // Double strikethrough
    new TextRun({
      text: "Double strikethrough",
      doubleStrike: true,
    }),

    // Superscript
    new TextRun({
      text: "2",
      superScript: true,
    }),

    // Subscript
    new TextRun({
      text: "2",
      subScript: true,
    }),

    // Font size (half-points, so 24 = 12pt)
    new TextRun({
      text: "Large text",
      size: 48, // 24pt
    }),

    // Font family
    new TextRun({
      text: "Custom font",
      font: "Arial",
    }),

    // All caps
    new TextRun({
      text: "all caps text",
      allCaps: true,
    }),

    // Small caps
    new TextRun({
      text: "Small Caps Text",
      smallCaps: true,
    }),
  ],
});
```

### Combined Formatting

```typescript
new Paragraph({
  children: [
    new TextRun({
      text: "Bold, italic, and underlined",
      bold: true,
      italics: true,
      underline: { type: UnderlineType.SINGLE },
      font: "Georgia",
      size: 28, // 14pt
      color: "1F497D",
    }),
  ],
});
```

---

## 3. Styles & Professional Formatting

### Document-Level Styles

```typescript
const doc = new Document({
  styles: {
    default: {
      document: {
        run: {
          font: "Arial",
          size: 24, // 12pt default
        },
        paragraph: {
          spacing: {
            after: 120,
            line: 276,
          },
        },
      },
    },
    paragraphStyles: [
      {
        id: "Title",
        name: "Title",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: {
          font: "Arial",
          size: 56, // 28pt
          bold: true,
          color: "2E74B5",
        },
        paragraph: {
          spacing: { after: 300 },
          alignment: AlignmentType.CENTER,
        },
      },
      {
        id: "Heading1",
        name: "Heading 1",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: {
          font: "Arial",
          size: 32, // 16pt
          bold: true,
          color: "2E74B5",
        },
        paragraph: {
          spacing: { before: 240, after: 120 },
          outlineLevel: 0, // CRITICAL: Required for TOC inclusion
        },
      },
      {
        id: "Heading2",
        name: "Heading 2",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: {
          font: "Arial",
          size: 28, // 14pt
          bold: true,
          color: "2E74B5",
        },
        paragraph: {
          spacing: { before: 200, after: 100 },
          outlineLevel: 1, // CRITICAL: Required for TOC inclusion
        },
      },
      {
        id: "Heading3",
        name: "Heading 3",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: {
          font: "Arial",
          size: 26, // 13pt
          bold: true,
          italics: true,
          color: "1F4E79",
        },
        paragraph: {
          spacing: { before: 160, after: 80 },
          outlineLevel: 2,
        },
      },
      {
        id: "BodyText",
        name: "Body Text",
        basedOn: "Normal",
        run: {
          font: "Times New Roman",
          size: 24, // 12pt
        },
        paragraph: {
          spacing: { after: 120, line: 276 },
          alignment: AlignmentType.JUSTIFIED,
        },
      },
    ],
    characterStyles: [
      {
        id: "Emphasis",
        name: "Emphasis",
        run: {
          italics: true,
          color: "666666",
        },
      },
      {
        id: "Strong",
        name: "Strong",
        run: {
          bold: true,
        },
      },
      {
        id: "Code",
        name: "Code",
        run: {
          font: "Courier New",
          size: 22, // 11pt
          color: "C7254E",
          shading: {
            type: ShadingType.CLEAR,
            fill: "F9F2F4",
          },
        },
      },
    ],
  },
  sections: [/* ... */],
});
```

### Using Styles

```typescript
// Using paragraph style
new Paragraph({
  style: "Heading1",
  text: "This is a Heading 1",
});

// Using HeadingLevel enum (built-in styles)
new Paragraph({
  heading: HeadingLevel.HEADING_1,
  text: "Built-in Heading 1",
});

// Mixing style with inline formatting
new Paragraph({
  style: "BodyText",
  children: [
    new TextRun("Regular text with "),
    new TextRun({
      text: "emphasized",
      style: "Emphasis",
    }),
    new TextRun(" words."),
  ],
});
```

---

## 4. Professional Font Combinations

### Corporate / Business

```typescript
// Headlines: Arial
// Body: Times New Roman
const corporateStyles = {
  paragraphStyles: [
    {
      id: "CorporateHeading",
      name: "Corporate Heading",
      run: { font: "Arial", size: 32, bold: true },
    },
    {
      id: "CorporateBody",
      name: "Corporate Body",
      run: { font: "Times New Roman", size: 24 },
    },
  ],
};
```

### Modern / Clean

```typescript
// Headlines: Arial Bold
// Body: Arial Regular
const modernStyles = {
  paragraphStyles: [
    {
      id: "ModernHeading",
      name: "Modern Heading",
      run: { font: "Arial", size: 36, bold: true, color: "333333" },
    },
    {
      id: "ModernBody",
      name: "Modern Body",
      run: { font: "Arial", size: 22, color: "444444" },
    },
  ],
};
```

### Traditional / Academic

```typescript
// Headlines: Georgia Bold
// Body: Georgia Regular
const academicStyles = {
  paragraphStyles: [
    {
      id: "AcademicHeading",
      name: "Academic Heading",
      run: { font: "Georgia", size: 28, bold: true },
    },
    {
      id: "AcademicBody",
      name: "Academic Body",
      run: { font: "Georgia", size: 24 },
      paragraph: {
        spacing: { line: 360 }, // Double spaced
        indent: { firstLine: 720 }, // 0.5 inch first line indent
      },
    },
  ],
};
```

---

## 5. Lists

### Bullet Lists

```typescript
const doc = new Document({
  numbering: {
    config: [
      {
        reference: "bullet-list",
        levels: [
          {
            level: 0,
            format: LevelFormat.BULLET,
            text: "\u2022", // Bullet character
            alignment: AlignmentType.LEFT,
            style: {
              paragraph: {
                indent: { left: 720, hanging: 360 },
              },
            },
          },
          {
            level: 1,
            format: LevelFormat.BULLET,
            text: "\u25E6", // White bullet
            alignment: AlignmentType.LEFT,
            style: {
              paragraph: {
                indent: { left: 1440, hanging: 360 },
              },
            },
          },
          {
            level: 2,
            format: LevelFormat.BULLET,
            text: "\u25AA", // Black square
            alignment: AlignmentType.LEFT,
            style: {
              paragraph: {
                indent: { left: 2160, hanging: 360 },
              },
            },
          },
        ],
      },
    ],
  },
  sections: [
    {
      children: [
        new Paragraph({
          text: "First bullet item",
          numbering: { reference: "bullet-list", level: 0 },
        }),
        new Paragraph({
          text: "Second bullet item",
          numbering: { reference: "bullet-list", level: 0 },
        }),
        new Paragraph({
          text: "Nested item",
          numbering: { reference: "bullet-list", level: 1 },
        }),
        new Paragraph({
          text: "Deeply nested item",
          numbering: { reference: "bullet-list", level: 2 },
        }),
        new Paragraph({
          text: "Back to first level",
          numbering: { reference: "bullet-list", level: 0 },
        }),
      ],
    },
  ],
});
```

### Numbered Lists

```typescript
const doc = new Document({
  numbering: {
    config: [
      {
        reference: "numbered-list",
        levels: [
          {
            level: 0,
            format: LevelFormat.DECIMAL,
            text: "%1.",
            alignment: AlignmentType.START,
            style: {
              paragraph: {
                indent: { left: 720, hanging: 360 },
              },
            },
          },
          {
            level: 1,
            format: LevelFormat.LOWER_LETTER,
            text: "%2)",
            alignment: AlignmentType.START,
            style: {
              paragraph: {
                indent: { left: 1440, hanging: 360 },
              },
            },
          },
          {
            level: 2,
            format: LevelFormat.LOWER_ROMAN,
            text: "%3.",
            alignment: AlignmentType.START,
            style: {
              paragraph: {
                indent: { left: 2160, hanging: 360 },
              },
            },
          },
        ],
      },
    ],
  },
  sections: [
    {
      children: [
        new Paragraph({
          text: "First numbered item",
          numbering: { reference: "numbered-list", level: 0 },
        }),
        new Paragraph({
          text: "Second numbered item",
          numbering: { reference: "numbered-list", level: 0 },
        }),
        new Paragraph({
          text: "Sub-item a",
          numbering: { reference: "numbered-list", level: 1 },
        }),
        new Paragraph({
          text: "Sub-item b",
          numbering: { reference: "numbered-list", level: 1 },
        }),
        new Paragraph({
          text: "Third numbered item",
          numbering: { reference: "numbered-list", level: 0 },
        }),
      ],
    },
  ],
});
```

### Available LevelFormat Options

```typescript
LevelFormat.DECIMAL        // 1, 2, 3
LevelFormat.UPPER_ROMAN    // I, II, III
LevelFormat.LOWER_ROMAN    // i, ii, iii
LevelFormat.UPPER_LETTER   // A, B, C
LevelFormat.LOWER_LETTER   // a, b, c
LevelFormat.BULLET         // Custom bullet character
LevelFormat.ORDINAL        // 1st, 2nd, 3rd
LevelFormat.CARDINAL_TEXT  // One, Two, Three
LevelFormat.ORDINAL_TEXT   // First, Second, Third
```

---

## 6. Tables

### Complete Table Example

```typescript
const table = new Table({
  width: {
    size: 100,
    type: WidthType.PERCENTAGE,
  },
  rows: [
    // Header row
    new TableRow({
      tableHeader: true, // Repeat on each page
      children: [
        new TableCell({
          width: { size: 25, type: WidthType.PERCENTAGE },
          shading: {
            type: ShadingType.CLEAR, // CRITICAL: Always use ShadingType.CLEAR
            fill: "2E74B5",
          },
          margins: {
            top: 100,
            bottom: 100,
            left: 100,
            right: 100,
          },
          children: [
            new Paragraph({
              alignment: AlignmentType.CENTER,
              children: [
                new TextRun({
                  text: "Column 1",
                  bold: true,
                  color: "FFFFFF",
                }),
              ],
            }),
          ],
        }),
        new TableCell({
          width: { size: 50, type: WidthType.PERCENTAGE },
          shading: { type: ShadingType.CLEAR, fill: "2E74B5" },
          margins: { top: 100, bottom: 100, left: 100, right: 100 },
          children: [
            new Paragraph({
              alignment: AlignmentType.CENTER,
              children: [
                new TextRun({ text: "Column 2", bold: true, color: "FFFFFF" }),
              ],
            }),
          ],
        }),
        new TableCell({
          width: { size: 25, type: WidthType.PERCENTAGE },
          shading: { type: ShadingType.CLEAR, fill: "2E74B5" },
          margins: { top: 100, bottom: 100, left: 100, right: 100 },
          children: [
            new Paragraph({
              alignment: AlignmentType.CENTER,
              children: [
                new TextRun({ text: "Column 3", bold: true, color: "FFFFFF" }),
              ],
            }),
          ],
        }),
      ],
    }),
    // Data row
    new TableRow({
      children: [
        new TableCell({
          shading: { type: ShadingType.CLEAR, fill: "FFFFFF" },
          margins: { top: 80, bottom: 80, left: 100, right: 100 },
          verticalAlign: VerticalAlign.CENTER,
          children: [
            new Paragraph({ text: "Row 1, Cell 1" }),
          ],
        }),
        new TableCell({
          shading: { type: ShadingType.CLEAR, fill: "FFFFFF" },
          margins: { top: 80, bottom: 80, left: 100, right: 100 },
          children: [
            // Cell with bullet list
            new Paragraph({
              text: "Item A",
              numbering: { reference: "bullet-list", level: 0 },
            }),
            new Paragraph({
              text: "Item B",
              numbering: { reference: "bullet-list", level: 0 },
            }),
          ],
        }),
        new TableCell({
          shading: { type: ShadingType.CLEAR, fill: "FFFFFF" },
          margins: { top: 80, bottom: 80, left: 100, right: 100 },
          children: [
            new Paragraph({ text: "Row 1, Cell 3" }),
          ],
        }),
      ],
    }),
    // Alternating row color
    new TableRow({
      children: [
        new TableCell({
          shading: { type: ShadingType.CLEAR, fill: "F2F2F2" },
          margins: { top: 80, bottom: 80, left: 100, right: 100 },
          children: [new Paragraph({ text: "Row 2, Cell 1" })],
        }),
        new TableCell({
          shading: { type: ShadingType.CLEAR, fill: "F2F2F2" },
          margins: { top: 80, bottom: 80, left: 100, right: 100 },
          children: [new Paragraph({ text: "Row 2, Cell 2" })],
        }),
        new TableCell({
          shading: { type: ShadingType.CLEAR, fill: "F2F2F2" },
          margins: { top: 80, bottom: 80, left: 100, right: 100 },
          children: [new Paragraph({ text: "Row 2, Cell 3" })],
        }),
      ],
    }),
  ],
});
```

### Table with Custom Borders

```typescript
new Table({
  width: { size: 100, type: WidthType.PERCENTAGE },
  borders: {
    top: { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" },
    bottom: { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" },
    left: { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" },
    right: { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" },
    insideHorizontal: { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" },
    insideVertical: { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" },
  },
  rows: [/* ... */],
});
```

### Table Cell Spanning

```typescript
// Column span
new TableCell({
  columnSpan: 2, // Span 2 columns
  children: [new Paragraph({ text: "Spans 2 columns" })],
});

// Row span
new TableCell({
  rowSpan: 3, // Span 3 rows
  children: [new Paragraph({ text: "Spans 3 rows" })],
});
```

### Fixed Column Widths

```typescript
new Table({
  columnWidths: [2000, 4000, 2000], // Widths in twips
  rows: [/* ... */],
});

// Or using conversion helpers
new Table({
  columnWidths: [
    convertInchesToTwip(1.5),
    convertInchesToTwip(3),
    convertInchesToTwip(1.5),
  ],
  rows: [/* ... */],
});
```

---

## 7. Links & Navigation

### Table of Contents

```typescript
const doc = new Document({
  features: {
    updateFields: true, // CRITICAL: Enable field updates for TOC
  },
  styles: {
    paragraphStyles: [
      {
        id: "Heading1",
        name: "Heading 1",
        run: { font: "Arial", size: 32, bold: true },
        paragraph: { outlineLevel: 0 }, // REQUIRED for TOC
      },
      {
        id: "Heading2",
        name: "Heading 2",
        run: { font: "Arial", size: 28, bold: true },
        paragraph: { outlineLevel: 1 }, // REQUIRED for TOC
      },
    ],
  },
  sections: [
    {
      children: [
        new Paragraph({
          text: "Table of Contents",
          heading: HeadingLevel.TITLE,
        }),
        new TableOfContents("Table of Contents", {
          hyperlink: true,
          headingStyleRange: "1-3", // Include Heading 1 through 3
          stylesWithLevels: [
            new StyleLevel("Heading1", 1),
            new StyleLevel("Heading2", 2),
            new StyleLevel("Heading3", 3),
          ],
        }),
        new Paragraph({
          children: [new PageBreak()],
        }),
        new Paragraph({
          style: "Heading1",
          text: "Introduction",
        }),
        new Paragraph({ text: "Introduction content..." }),
        new Paragraph({
          style: "Heading2",
          text: "Background",
        }),
        new Paragraph({ text: "Background content..." }),
      ],
    },
  ],
});
```

### External Hyperlinks

```typescript
new Paragraph({
  children: [
    new TextRun("Visit our website: "),
    new ExternalHyperlink({
      children: [
        new TextRun({
          text: "Click here",
          style: "Hyperlink", // Uses built-in hyperlink style
          color: "0563C1",
          underline: { type: UnderlineType.SINGLE },
        }),
      ],
      link: "https://www.example.com",
    }),
    new TextRun(" for more information."),
  ],
});
```

### Internal Hyperlinks (Bookmarks)

```typescript
// Create a bookmark (target)
new Paragraph({
  children: [
    new Bookmark({
      id: "appendix-a",
      children: [
        new TextRun({
          text: "Appendix A: Detailed Data",
          bold: true,
        }),
      ],
    }),
  ],
});

// Create internal link to the bookmark
new Paragraph({
  children: [
    new TextRun("For more details, see "),
    new InternalHyperlink({
      children: [
        new TextRun({
          text: "Appendix A",
          color: "0563C1",
          underline: { type: UnderlineType.SINGLE },
        }),
      ],
      anchor: "appendix-a",
    }),
    new TextRun("."),
  ],
});
```

---

## 8. Images & Media

### Adding Images

```typescript
import * as fs from "fs";
import * as path from "path";

// Read image file
const imageBuffer = fs.readFileSync(path.join(__dirname, "logo.png"));

new Paragraph({
  children: [
    new ImageRun({
      data: imageBuffer,
      transformation: {
        width: 200, // Width in pixels
        height: 100, // Height in pixels
      },
      altText: {
        title: "Company Logo",
        description: "The company logo displayed at the top of the document",
        name: "logo.png",
      },
    }),
  ],
});
```

### Image from Base64

```typescript
const base64Data = "iVBORw0KGgoAAAANSUhEUgAA..."; // Base64 string
const imageBuffer = Buffer.from(base64Data, "base64");

new Paragraph({
  alignment: AlignmentType.CENTER,
  children: [
    new ImageRun({
      data: imageBuffer,
      transformation: {
        width: 400,
        height: 300,
      },
      altText: {
        title: "Chart Image",
        description: "Sales performance chart for Q4 2024",
        name: "chart.png",
      },
    }),
  ],
});
```

### Image from URL (async)

```typescript
async function getImageFromUrl(url: string): Promise<Buffer> {
  const response = await fetch(url);
  const arrayBuffer = await response.arrayBuffer();
  return Buffer.from(arrayBuffer);
}

// Usage
const imageBuffer = await getImageFromUrl("https://example.com/image.png");

new Paragraph({
  children: [
    new ImageRun({
      data: imageBuffer,
      transformation: { width: 300, height: 200 },
      altText: {
        title: "Remote Image",
        description: "Image fetched from remote URL",
        name: "remote-image.png",
      },
    }),
  ],
});
```

### Floating Image

```typescript
import { TextWrappingType, TextWrappingSide } from "docx";

new Paragraph({
  children: [
    new ImageRun({
      data: imageBuffer,
      transformation: { width: 150, height: 150 },
      floating: {
        horizontalPosition: {
          relative: "column",
          offset: 0,
        },
        verticalPosition: {
          relative: "paragraph",
          offset: 0,
        },
        wrap: {
          type: TextWrappingType.SQUARE,
          side: TextWrappingSide.BOTH_SIDES,
        },
        margins: {
          top: 100,
          bottom: 100,
          left: 100,
          right: 100,
        },
      },
      altText: {
        title: "Floating Image",
        description: "An image with text wrapping",
        name: "floating.png",
      },
    }),
    new TextRun("This text wraps around the floating image..."),
  ],
});
```

---

## 9. Page Breaks

### CRITICAL: PageBreak Must Be Inside Paragraph

```typescript
// CORRECT: PageBreak inside Paragraph
new Paragraph({
  children: [new PageBreak()],
});

// CORRECT: PageBreak after text
new Paragraph({
  children: [
    new TextRun("This is the last line before the page break."),
    new PageBreak(),
  ],
});

// WRONG: Never use PageBreak standalone in section children
// This will NOT work:
// children: [
//   new Paragraph({ text: "Some text" }),
//   new PageBreak(), // ERROR: PageBreak is not a valid section child
//   new Paragraph({ text: "More text" }),
// ]
```

### Section Break (Alternative)

```typescript
// For section-level breaks, use multiple sections
const doc = new Document({
  sections: [
    {
      properties: {
        // First section properties
      },
      children: [
        new Paragraph({ text: "First section content" }),
      ],
    },
    {
      properties: {
        // Second section (starts on new page by default)
      },
      children: [
        new Paragraph({ text: "Second section content" }),
      ],
    },
  ],
});
```

---

## 10. Headers/Footers & Page Setup

### Page Margins

```typescript
const doc = new Document({
  sections: [
    {
      properties: {
        page: {
          margin: {
            top: convertInchesToTwip(1),
            bottom: convertInchesToTwip(1),
            left: convertInchesToTwip(1.25),
            right: convertInchesToTwip(1.25),
            header: convertInchesToTwip(0.5),
            footer: convertInchesToTwip(0.5),
          },
        },
      },
      children: [/* ... */],
    },
  ],
});
```

### Page Orientation

```typescript
import { PageOrientation } from "docx";

const doc = new Document({
  sections: [
    {
      properties: {
        page: {
          size: {
            orientation: PageOrientation.LANDSCAPE,
            // Optional: custom page size
            width: convertInchesToTwip(11),
            height: convertInchesToTwip(8.5),
          },
        },
      },
      children: [/* ... */],
    },
  ],
});
```

### Headers

```typescript
const doc = new Document({
  sections: [
    {
      properties: {
        page: {
          margin: {
            top: convertInchesToTwip(1),
            header: convertInchesToTwip(0.5),
          },
        },
      },
      headers: {
        default: new Header({
          children: [
            new Paragraph({
              alignment: AlignmentType.RIGHT,
              children: [
                new TextRun({
                  text: "Document Title",
                  font: "Arial",
                  size: 20,
                  color: "666666",
                }),
              ],
            }),
          ],
        }),
        first: new Header({
          children: [
            new Paragraph({
              alignment: AlignmentType.CENTER,
              children: [
                new TextRun({
                  text: "CONFIDENTIAL",
                  bold: true,
                  color: "FF0000",
                }),
              ],
            }),
          ],
        }),
      },
      children: [/* ... */],
    },
  ],
});
```

### Footers with Page Numbers

```typescript
const doc = new Document({
  sections: [
    {
      properties: {
        page: {
          margin: {
            bottom: convertInchesToTwip(1),
            footer: convertInchesToTwip(0.5),
          },
        },
      },
      footers: {
        default: new Footer({
          children: [
            new Paragraph({
              alignment: AlignmentType.CENTER,
              children: [
                new TextRun({
                  text: "Page ",
                  font: "Arial",
                  size: 20,
                }),
                new TextRun({
                  children: [PageNumber.CURRENT],
                  font: "Arial",
                  size: 20,
                }),
                new TextRun({
                  text: " of ",
                  font: "Arial",
                  size: 20,
                }),
                new TextRun({
                  children: [PageNumber.TOTAL_PAGES],
                  font: "Arial",
                  size: 20,
                }),
              ],
            }),
          ],
        }),
      },
      children: [/* ... */],
    },
  ],
});
```

### Different First Page Header/Footer

```typescript
const doc = new Document({
  sections: [
    {
      properties: {
        titlePage: true, // Enable different first page
      },
      headers: {
        default: new Header({
          children: [new Paragraph({ text: "Regular Header" })],
        }),
        first: new Header({
          children: [new Paragraph({ text: "First Page Header" })],
        }),
      },
      footers: {
        default: new Footer({
          children: [new Paragraph({ text: "Regular Footer" })],
        }),
        first: new Footer({
          children: [], // No footer on first page
        }),
      },
      children: [/* ... */],
    },
  ],
});
```

---

## 11. Tabs

### Tab Stops

```typescript
new Paragraph({
  tabStops: [
    {
      type: TabStopType.LEFT,
      position: convertInchesToTwip(1),
    },
    {
      type: TabStopType.CENTER,
      position: convertInchesToTwip(3),
    },
    {
      type: TabStopType.RIGHT,
      position: convertInchesToTwip(6),
    },
    {
      type: TabStopType.DECIMAL,
      position: convertInchesToTwip(5),
    },
  ],
  children: [
    new TextRun("Left"),
    new TextRun({ children: [new Tab()] }),
    new TextRun("Center"),
    new TextRun({ children: [new Tab()] }),
    new TextRun("Right"),
  ],
});
```

### Tab with Leader Characters

```typescript
import { LeaderType } from "docx";

new Paragraph({
  tabStops: [
    {
      type: TabStopType.RIGHT,
      position: convertInchesToTwip(6),
      leader: LeaderType.DOT, // Dot leader (like in TOC)
    },
  ],
  children: [
    new TextRun("Chapter 1"),
    new TextRun({ children: [new Tab()] }),
    new TextRun("15"),
  ],
});
// Output: Chapter 1 ..................... 15
```

### LeaderType Options

```typescript
LeaderType.DOT        // .......
LeaderType.HYPHEN     // -------
LeaderType.UNDERSCORE // _______
LeaderType.MIDDLE_DOT // ·······
LeaderType.NONE       // No leader
```

---

## 12. Constants Quick Reference

### AlignmentType

```typescript
AlignmentType.LEFT
AlignmentType.CENTER
AlignmentType.RIGHT
AlignmentType.JUSTIFIED
AlignmentType.BOTH      // Same as JUSTIFIED
AlignmentType.START     // Language-aware left
AlignmentType.END       // Language-aware right
```

### HeadingLevel

```typescript
HeadingLevel.TITLE
HeadingLevel.HEADING_1
HeadingLevel.HEADING_2
HeadingLevel.HEADING_3
HeadingLevel.HEADING_4
HeadingLevel.HEADING_5
HeadingLevel.HEADING_6
```

### BorderStyle

```typescript
BorderStyle.NONE
BorderStyle.SINGLE
BorderStyle.THICK
BorderStyle.DOUBLE
BorderStyle.DOTTED
BorderStyle.DASHED
BorderStyle.DOT_DASH
BorderStyle.DOT_DOT_DASH
BorderStyle.WAVE
BorderStyle.DOUBLE_WAVE
BorderStyle.TRIPLE
```

### WidthType

```typescript
WidthType.AUTO
WidthType.DXA         // Twips (1/20 of a point)
WidthType.NIL         // Zero width
WidthType.PERCENTAGE
```

### VerticalAlign (Table Cells)

```typescript
VerticalAlign.TOP
VerticalAlign.CENTER
VerticalAlign.BOTTOM
```

### UnderlineType

```typescript
UnderlineType.SINGLE
UnderlineType.DOUBLE
UnderlineType.THICK
UnderlineType.DOTTED
UnderlineType.DASH
UnderlineType.DOT_DASH
UnderlineType.DOT_DOT_DASH
UnderlineType.WAVE
UnderlineType.WAVY_HEAVY
UnderlineType.WAVY_DOUBLE
UnderlineType.WORDS     // Underline words only, not spaces
```

### Conversion Helpers

```typescript
convertInchesToTwip(inches: number): number
convertMillimetersToTwip(mm: number): number
// Note: 1 inch = 1440 twips, 1 point = 20 twips
```

---

## 13. Critical Issues & Common Mistakes

### 1. PageBreak Must Be Inside Paragraph

```typescript
// WRONG - Will cause error
children: [
  new Paragraph({ text: "Text" }),
  new PageBreak(), // ERROR!
]

// CORRECT
children: [
  new Paragraph({ text: "Text" }),
  new Paragraph({ children: [new PageBreak()] }),
]
```

### 2. Always Use ShadingType.CLEAR for Table Cell Backgrounds

```typescript
// WRONG - May not render correctly
new TableCell({
  shading: { fill: "FF0000" }, // Missing type!
});

// CORRECT
new TableCell({
  shading: {
    type: ShadingType.CLEAR, // REQUIRED
    fill: "FF0000",
  },
});
```

### 3. outlineLevel Required for TOC

```typescript
// WRONG - Heading won't appear in TOC
{
  id: "Heading1",
  paragraph: {
    // Missing outlineLevel!
  },
}

// CORRECT
{
  id: "Heading1",
  paragraph: {
    outlineLevel: 0, // 0 = Heading 1, 1 = Heading 2, etc.
  },
}
```

### 4. Enable updateFields for TOC

```typescript
// WRONG - TOC won't update
const doc = new Document({
  sections: [/* TOC section */],
});

// CORRECT
const doc = new Document({
  features: {
    updateFields: true, // Required for TOC
  },
  sections: [/* TOC section */],
});
```

### 5. Colors Without Hash

```typescript
// WRONG
color: "#FF0000"

// CORRECT
color: "FF0000" // No hash symbol
```

### 6. Font Size in Half-Points

```typescript
// WRONG - This creates 24pt text, not 12pt
size: 24

// CORRECT - For 12pt text
size: 24 // Because 24 half-points = 12 points

// Common sizes:
// 10pt = size: 20
// 11pt = size: 22
// 12pt = size: 24
// 14pt = size: 28
// 16pt = size: 32
// 18pt = size: 36
// 24pt = size: 48
// 36pt = size: 72
```

### 7. ImageRun Requires altText

```typescript
// WRONG - Missing altText
new ImageRun({
  data: imageBuffer,
  transformation: { width: 100, height: 100 },
});

// CORRECT
new ImageRun({
  data: imageBuffer,
  transformation: { width: 100, height: 100 },
  altText: {
    title: "Image Title",
    description: "Image description for accessibility",
    name: "image.png",
  },
});
```

### 8. Paragraph text vs children

```typescript
// Simple text - use text property
new Paragraph({
  text: "Simple text",
});

// Formatted text - use children with TextRun
new Paragraph({
  children: [
    new TextRun({ text: "Bold", bold: true }),
    new TextRun(" and regular"),
  ],
});

// WRONG - Don't mix text and children
new Paragraph({
  text: "Some text",
  children: [new TextRun("More text")], // Confusing!
});
```

### 9. Numbering Reference Must Match Config

```typescript
const doc = new Document({
  numbering: {
    config: [
      {
        reference: "my-bullets", // This reference...
        levels: [/* ... */],
      },
    ],
  },
  sections: [{
    children: [
      new Paragraph({
        text: "Bullet item",
        numbering: {
          reference: "my-bullets", // ...must match here
          level: 0,
        },
      }),
    ],
  }],
});
```

### 10. Table Cell Must Have Children Array

```typescript
// WRONG
new TableCell({
  // Missing children!
});

// CORRECT - Even empty cells need children
new TableCell({
  children: [], // At minimum, empty array
});

// Or with content
new TableCell({
  children: [new Paragraph({ text: "Cell content" })],
});
```

---

## Complete Example: Professional Report

```typescript
import {
  Document,
  Packer,
  Paragraph,
  TextRun,
  Table,
  TableRow,
  TableCell,
  WidthType,
  AlignmentType,
  HeadingLevel,
  BorderStyle,
  ShadingType,
  PageBreak,
  Header,
  Footer,
  PageNumber,
  LevelFormat,
  TableOfContents,
  StyleLevel,
  convertInchesToTwip,
} from "docx";
import * as fs from "fs";

async function createReport() {
  const doc = new Document({
    features: {
      updateFields: true,
    },
    styles: {
      default: {
        document: {
          run: { font: "Arial", size: 24 },
        },
      },
      paragraphStyles: [
        {
          id: "Heading1",
          name: "Heading 1",
          basedOn: "Normal",
          next: "Normal",
          quickFormat: true,
          run: { font: "Arial", size: 32, bold: true, color: "2E74B5" },
          paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 0 },
        },
        {
          id: "Heading2",
          name: "Heading 2",
          basedOn: "Normal",
          next: "Normal",
          quickFormat: true,
          run: { font: "Arial", size: 28, bold: true, color: "2E74B5" },
          paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 1 },
        },
      ],
    },
    numbering: {
      config: [
        {
          reference: "bullets",
          levels: [
            {
              level: 0,
              format: LevelFormat.BULLET,
              text: "\u2022",
              alignment: AlignmentType.LEFT,
              style: { paragraph: { indent: { left: 720, hanging: 360 } } },
            },
          ],
        },
      ],
    },
    sections: [
      {
        properties: {
          page: {
            margin: {
              top: convertInchesToTwip(1),
              bottom: convertInchesToTwip(1),
              left: convertInchesToTwip(1.25),
              right: convertInchesToTwip(1.25),
            },
          },
        },
        headers: {
          default: new Header({
            children: [
              new Paragraph({
                alignment: AlignmentType.RIGHT,
                children: [
                  new TextRun({ text: "Quarterly Report", size: 20, color: "666666" }),
                ],
              }),
            ],
          }),
        },
        footers: {
          default: new Footer({
            children: [
              new Paragraph({
                alignment: AlignmentType.CENTER,
                children: [
                  new TextRun({ text: "Page ", size: 20 }),
                  new TextRun({ children: [PageNumber.CURRENT], size: 20 }),
                  new TextRun({ text: " of ", size: 20 }),
                  new TextRun({ children: [PageNumber.TOTAL_PAGES], size: 20 }),
                ],
              }),
            ],
          }),
        },
        children: [
          // Title
          new Paragraph({
            alignment: AlignmentType.CENTER,
            spacing: { after: 400 },
            children: [
              new TextRun({
                text: "Q4 2024 Performance Report",
                bold: true,
                size: 56,
                color: "1F497D",
              }),
            ],
          }),

          // Table of Contents
          new Paragraph({
            style: "Heading1",
            text: "Table of Contents",
          }),
          new TableOfContents("TOC", {
            hyperlink: true,
            headingStyleRange: "1-2",
          }),
          new Paragraph({ children: [new PageBreak()] }),

          // Introduction
          new Paragraph({ style: "Heading1", text: "Introduction" }),
          new Paragraph({
            spacing: { after: 120 },
            children: [
              new TextRun("This report summarizes the performance metrics for "),
              new TextRun({ text: "Q4 2024", bold: true }),
              new TextRun("."),
            ],
          }),

          // Key Highlights
          new Paragraph({ style: "Heading2", text: "Key Highlights" }),
          new Paragraph({
            text: "Revenue increased by 15%",
            numbering: { reference: "bullets", level: 0 },
          }),
          new Paragraph({
            text: "Customer satisfaction reached 94%",
            numbering: { reference: "bullets", level: 0 },
          }),
          new Paragraph({
            text: "Market share expanded to 28%",
            numbering: { reference: "bullets", level: 0 },
          }),

          // Data Table
          new Paragraph({ style: "Heading1", text: "Performance Data" }),
          new Table({
            width: { size: 100, type: WidthType.PERCENTAGE },
            rows: [
              new TableRow({
                tableHeader: true,
                children: [
                  new TableCell({
                    shading: { type: ShadingType.CLEAR, fill: "2E74B5" },
                    margins: { top: 100, bottom: 100, left: 100, right: 100 },
                    children: [
                      new Paragraph({
                        alignment: AlignmentType.CENTER,
                        children: [
                          new TextRun({ text: "Metric", bold: true, color: "FFFFFF" }),
                        ],
                      }),
                    ],
                  }),
                  new TableCell({
                    shading: { type: ShadingType.CLEAR, fill: "2E74B5" },
                    margins: { top: 100, bottom: 100, left: 100, right: 100 },
                    children: [
                      new Paragraph({
                        alignment: AlignmentType.CENTER,
                        children: [
                          new TextRun({ text: "Q3 2024", bold: true, color: "FFFFFF" }),
                        ],
                      }),
                    ],
                  }),
                  new TableCell({
                    shading: { type: ShadingType.CLEAR, fill: "2E74B5" },
                    margins: { top: 100, bottom: 100, left: 100, right: 100 },
                    children: [
                      new Paragraph({
                        alignment: AlignmentType.CENTER,
                        children: [
                          new TextRun({ text: "Q4 2024", bold: true, color: "FFFFFF" }),
                        ],
                      }),
                    ],
                  }),
                ],
              }),
              new TableRow({
                children: [
                  new TableCell({
                    shading: { type: ShadingType.CLEAR, fill: "FFFFFF" },
                    margins: { top: 80, bottom: 80, left: 100, right: 100 },
                    children: [new Paragraph({ text: "Revenue ($M)" })],
                  }),
                  new TableCell({
                    shading: { type: ShadingType.CLEAR, fill: "FFFFFF" },
                    margins: { top: 80, bottom: 80, left: 100, right: 100 },
                    children: [
                      new Paragraph({ alignment: AlignmentType.CENTER, text: "45.2" }),
                    ],
                  }),
                  new TableCell({
                    shading: { type: ShadingType.CLEAR, fill: "FFFFFF" },
                    margins: { top: 80, bottom: 80, left: 100, right: 100 },
                    children: [
                      new Paragraph({ alignment: AlignmentType.CENTER, text: "52.0" }),
                    ],
                  }),
                ],
              }),
              new TableRow({
                children: [
                  new TableCell({
                    shading: { type: ShadingType.CLEAR, fill: "F2F2F2" },
                    margins: { top: 80, bottom: 80, left: 100, right: 100 },
                    children: [new Paragraph({ text: "Customers" })],
                  }),
                  new TableCell({
                    shading: { type: ShadingType.CLEAR, fill: "F2F2F2" },
                    margins: { top: 80, bottom: 80, left: 100, right: 100 },
                    children: [
                      new Paragraph({ alignment: AlignmentType.CENTER, text: "12,450" }),
                    ],
                  }),
                  new TableCell({
                    shading: { type: ShadingType.CLEAR, fill: "F2F2F2" },
                    margins: { top: 80, bottom: 80, left: 100, right: 100 },
                    children: [
                      new Paragraph({ alignment: AlignmentType.CENTER, text: "14,890" }),
                    ],
                  }),
                ],
              }),
            ],
          }),
        ],
      },
    ],
  });

  const buffer = await Packer.toBuffer(doc);
  fs.writeFileSync("quarterly-report.docx", buffer);
  console.log("Report generated: quarterly-report.docx");
}

createReport();
```

---

## Additional Resources

- **Official Documentation**: https://docx.js.org/
- **GitHub Repository**: https://github.com/dolanmiu/docx
- **API Reference**: https://docx.js.org/api/
- **Examples**: https://github.com/dolanmiu/docx/tree/master/demo

---

*This documentation covers docx library version 8.x. Always check the official documentation for the latest API changes.*
