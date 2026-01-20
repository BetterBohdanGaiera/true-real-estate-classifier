# OOXML Technical Reference

Comprehensive Office Open XML documentation for editing existing Word documents with tracked changes, comments, and direct XML manipulation.

---

## 1. Technical Guidelines

### Schema Compliance

OOXML follows strict XML schema rules defined in ECMA-376. All elements must comply with the WordprocessingML schema (`http://schemas.openxmlformats.org/wordprocessingml/2006/main`).

#### Namespace Declarations

```xml
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
            xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
            xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
            xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"
            xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml"
            xmlns:w15="http://schemas.microsoft.com/office/word/2012/wordml">
```

### Element Ordering in w:pPr (Paragraph Properties)

**CRITICAL**: Child elements within `w:pPr` must appear in a specific order. Incorrect ordering causes document corruption.

Required order:
```
1.  w:pStyle       (paragraph style reference)
2.  w:keepNext     (keep with next paragraph)
3.  w:keepLines    (keep lines together)
4.  w:pageBreakBefore
5.  w:framePr      (frame properties)
6.  w:widowControl
7.  w:numPr        (numbering properties)
8.  w:suppressLineNumbers
9.  w:pBdr         (paragraph borders)
10. w:shd          (shading)
11. w:tabs         (tab stops)
12. w:suppressAutoHyphens
13. w:kinsoku
14. w:wordWrap
15. w:overflowPunct
16. w:topLinePunct
17. w:autoSpaceDE
18. w:autoSpaceDN
19. w:bidi         (bidirectional)
20. w:adjustRightInd
21. w:snapToGrid
22. w:spacing      (line spacing)
23. w:ind          (indentation)
24. w:contextualSpacing
25. w:mirrorIndents
26. w:suppressOverlap
27. w:jc           (justification/alignment)
28. w:textDirection
29. w:textAlignment
30. w:textboxTightWrap
31. w:outlineLvl   (outline level)
32. w:divId
33. w:cnfStyle
34. w:rPr          (run properties for paragraph mark)
35. w:sectPr       (section properties - only in last paragraph)
36. w:pPrChange    (tracked changes to paragraph properties)
```

### Element Ordering in w:rPr (Run Properties)

Required order for `w:rPr` children:
```
1.  w:rStyle       (character style reference)
2.  w:rFonts       (fonts)
3.  w:b            (bold)
4.  w:bCs          (complex script bold)
5.  w:i            (italic)
6.  w:iCs          (complex script italic)
7.  w:caps         (all capitals)
8.  w:smallCaps
9.  w:strike       (strikethrough)
10. w:dstrike      (double strikethrough)
11. w:outline
12. w:shadow
13. w:emboss
14. w:imprint
15. w:noProof
16. w:snapToGrid
17. w:vanish       (hidden text)
18. w:webHidden
19. w:color
20. w:spacing      (character spacing)
21. w:w            (character width)
22. w:kern
23. w:position     (vertical position)
24. w:sz           (font size)
25. w:szCs         (complex script font size)
26. w:highlight
27. w:u            (underline)
28. w:effect
29. w:bdr          (text border)
30. w:shd          (shading)
31. w:fitText
32. w:vertAlign    (subscript/superscript)
33. w:rtl          (right-to-left)
34. w:cs           (complex script)
35. w:em           (emphasis mark)
36. w:lang         (language)
37. w:eastAsianLayout
38. w:specVanish
39. w:oMath
40. w:rPrChange    (tracked changes to run properties)
```

### Whitespace Handling

Preserve whitespace in text elements using `xml:space="preserve"`:

```xml
<!-- Without preserve - leading/trailing spaces may be lost -->
<w:t>Hello World</w:t>

<!-- With preserve - spaces are maintained -->
<w:t xml:space="preserve"> Hello World </w:t>

<!-- CRITICAL: Always use preserve when text has leading/trailing spaces -->
<w:t xml:space="preserve">  Two leading spaces</w:t>
```

**Rules**:
- Use `xml:space="preserve"` when text begins or ends with whitespace
- Use `xml:space="preserve"` for text containing multiple consecutive spaces
- Safe to omit for text with no special whitespace requirements

### Unicode and Entity Encoding

Special characters must be encoded:

| Character | Entity | Description |
|-----------|--------|-------------|
| `<` | `&lt;` | Less than |
| `>` | `&gt;` | Greater than |
| `&` | `&amp;` | Ampersand |
| `"` | `&quot;` | Double quote |
| `'` | `&apos;` | Single quote (apostrophe) |

Unicode characters can be included directly (UTF-8) or as numeric entities:
```xml
<w:t>Price: $100 &amp; tax</w:t>
<w:t>Copyright &#169; 2024</w:t>
<w:t>Em dash: &#x2014;</w:t>
```

### Tracked Changes Configuration

#### RSIDs (Revision Save IDs)

RSIDs are 8-digit hexadecimal identifiers that track editing sessions. They must be unique and consistent.

```xml
<!-- In settings.xml -->
<w:rsids>
    <w:rsidRoot w:val="00A12B3C"/>
    <w:rsid w:val="00A12B3C"/>
    <w:rsid w:val="00D45E6F"/>
    <w:rsid w:val="007890AB"/>
</w:rsids>

<!-- RSID usage in document.xml -->
<w:p w:rsidR="00A12B3C" w:rsidRDefault="00A12B3C" w:rsidP="00A12B3C">
    <w:r w:rsidR="00D45E6F">
        <w:t>Text from editing session</w:t>
    </w:r>
</w:p>
```

**RSID Attributes**:
- `w:rsidR` - Revision ID when paragraph was created
- `w:rsidRDefault` - Default revision ID for runs
- `w:rsidP` - Revision ID for paragraph properties
- `w:rsidRPr` - Revision ID for run properties

**Generating RSIDs**:
```python
import secrets
rsid = secrets.token_hex(4).upper()  # e.g., "00A12B3C"
```

#### Enable Track Revisions in settings.xml

```xml
<!-- word/settings.xml -->
<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
    <w:trackRevisions/>  <!-- Enable tracking -->
    <w:defaultTabStop w:val="720"/>
    <w:rsids>
        <w:rsidRoot w:val="00000001"/>
        <w:rsid w:val="00000001"/>
    </w:rsids>
</w:settings>
```

### Image Handling

Images in OOXML require:
1. Image file in `word/media/` directory
2. Relationship entry in `word/_rels/document.xml.rels`
3. Drawing ML markup in `document.xml`

See Section 2 for complete image XML structure.

---

## 2. Document Content Patterns

### Basic Structure

Every paragraph follows this hierarchy:

```xml
<w:p>                           <!-- Paragraph -->
    <w:pPr>                     <!-- Paragraph Properties (optional) -->
        <w:pStyle w:val="Normal"/>
        <w:jc w:val="left"/>
    </w:pPr>
    <w:r>                       <!-- Run (text container) -->
        <w:rPr>                 <!-- Run Properties (optional) -->
            <w:b/>              <!-- Bold -->
        </w:rPr>
        <w:t>Hello World</w:t>  <!-- Text content -->
    </w:r>
</w:p>
```

### Headings and Styles

```xml
<!-- Heading 1 -->
<w:p>
    <w:pPr>
        <w:pStyle w:val="Heading1"/>
    </w:pPr>
    <w:r>
        <w:t>Chapter 1: Introduction</w:t>
    </w:r>
</w:p>

<!-- Heading 2 -->
<w:p>
    <w:pPr>
        <w:pStyle w:val="Heading2"/>
    </w:pPr>
    <w:r>
        <w:t>1.1 Background</w:t>
    </w:r>
</w:p>

<!-- Custom style reference -->
<w:p>
    <w:pPr>
        <w:pStyle w:val="CustomStyleName"/>
    </w:pPr>
    <w:r>
        <w:t>Text with custom style</w:t>
    </w:r>
</w:p>
```

### Text Formatting

#### Bold

```xml
<w:r>
    <w:rPr>
        <w:b/>          <!-- Bold on -->
        <w:bCs/>        <!-- Bold for complex scripts -->
    </w:rPr>
    <w:t>Bold text</w:t>
</w:r>

<!-- Explicitly turn off bold -->
<w:r>
    <w:rPr>
        <w:b w:val="0"/>
    </w:rPr>
    <w:t>Not bold</w:t>
</w:r>
```

#### Italic

```xml
<w:r>
    <w:rPr>
        <w:i/>          <!-- Italic on -->
        <w:iCs/>        <!-- Italic for complex scripts -->
    </w:rPr>
    <w:t>Italic text</w:t>
</w:r>
```

#### Underline

```xml
<!-- Single underline -->
<w:r>
    <w:rPr>
        <w:u w:val="single"/>
    </w:rPr>
    <w:t>Underlined text</w:t>
</w:r>

<!-- Double underline -->
<w:r>
    <w:rPr>
        <w:u w:val="double"/>
    </w:rPr>
    <w:t>Double underlined</w:t>
</w:r>

<!-- Colored underline -->
<w:r>
    <w:rPr>
        <w:u w:val="single" w:color="FF0000"/>
    </w:rPr>
    <w:t>Red underline</w:t>
</w:r>
```

**Underline values**: `single`, `double`, `thick`, `dotted`, `dash`, `dotDash`, `dotDotDash`, `wave`, `wavyHeavy`, `wavyDouble`, `words`

#### Highlight

```xml
<w:r>
    <w:rPr>
        <w:highlight w:val="yellow"/>
    </w:rPr>
    <w:t>Highlighted text</w:t>
</w:r>
```

**Highlight values**: `yellow`, `green`, `cyan`, `magenta`, `blue`, `red`, `darkBlue`, `darkCyan`, `darkGreen`, `darkMagenta`, `darkRed`, `darkYellow`, `lightGray`, `darkGray`, `black`, `white`

#### Font Color

```xml
<w:r>
    <w:rPr>
        <w:color w:val="FF0000"/>  <!-- Red -->
    </w:rPr>
    <w:t>Red text</w:t>
</w:r>

<!-- Theme color -->
<w:r>
    <w:rPr>
        <w:color w:val="2E74B5" w:themeColor="accent1"/>
    </w:rPr>
    <w:t>Theme colored text</w:t>
</w:r>
```

#### Combined Formatting

```xml
<w:r>
    <w:rPr>
        <w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>
        <w:b/>
        <w:i/>
        <w:sz w:val="28"/>      <!-- 14pt (half-points) -->
        <w:szCs w:val="28"/>
        <w:color w:val="1F497D"/>
        <w:u w:val="single"/>
    </w:rPr>
    <w:t>Bold italic underlined Arial 14pt</w:t>
</w:r>
```

### Lists

#### Numbered List

```xml
<!-- First, define numbering in numbering.xml -->
<!-- Then reference in document.xml -->
<w:p>
    <w:pPr>
        <w:numPr>
            <w:ilvl w:val="0"/>       <!-- Indent level (0 = first level) -->
            <w:numId w:val="1"/>      <!-- Reference to numbering definition -->
        </w:numPr>
    </w:pPr>
    <w:r>
        <w:t>First numbered item</w:t>
    </w:r>
</w:p>
<w:p>
    <w:pPr>
        <w:numPr>
            <w:ilvl w:val="0"/>
            <w:numId w:val="1"/>
        </w:numPr>
    </w:pPr>
    <w:r>
        <w:t>Second numbered item</w:t>
    </w:r>
</w:p>
<w:p>
    <w:pPr>
        <w:numPr>
            <w:ilvl w:val="1"/>       <!-- Nested level -->
            <w:numId w:val="1"/>
        </w:numPr>
    </w:pPr>
    <w:r>
        <w:t>Nested item (a)</w:t>
    </w:r>
</w:p>
```

#### Bullet List

```xml
<w:p>
    <w:pPr>
        <w:numPr>
            <w:ilvl w:val="0"/>
            <w:numId w:val="2"/>      <!-- Different numId for bullets -->
        </w:numPr>
    </w:pPr>
    <w:r>
        <w:t>Bullet point one</w:t>
    </w:r>
</w:p>
```

#### Numbering Definition (numbering.xml)

```xml
<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
    <!-- Abstract numbering definition -->
    <w:abstractNum w:abstractNumId="0">
        <w:lvl w:ilvl="0">
            <w:start w:val="1"/>
            <w:numFmt w:val="decimal"/>
            <w:lvlText w:val="%1."/>
            <w:lvlJc w:val="left"/>
            <w:pPr>
                <w:ind w:left="720" w:hanging="360"/>
            </w:pPr>
        </w:lvl>
        <w:lvl w:ilvl="1">
            <w:start w:val="1"/>
            <w:numFmt w:val="lowerLetter"/>
            <w:lvlText w:val="%2)"/>
            <w:lvlJc w:val="left"/>
            <w:pPr>
                <w:ind w:left="1440" w:hanging="360"/>
            </w:pPr>
        </w:lvl>
    </w:abstractNum>

    <!-- Concrete numbering instance -->
    <w:num w:numId="1">
        <w:abstractNumId w:val="0"/>
    </w:num>
</w:numbering>
```

**numFmt values**: `decimal`, `upperRoman`, `lowerRoman`, `upperLetter`, `lowerLetter`, `ordinal`, `bullet`

### Tables

```xml
<w:tbl>
    <!-- Table Properties -->
    <w:tblPr>
        <w:tblStyle w:val="TableGrid"/>
        <w:tblW w:w="5000" w:type="pct"/>  <!-- 100% width (5000 = 100%) -->
        <w:tblBorders>
            <w:top w:val="single" w:sz="4" w:space="0" w:color="000000"/>
            <w:left w:val="single" w:sz="4" w:space="0" w:color="000000"/>
            <w:bottom w:val="single" w:sz="4" w:space="0" w:color="000000"/>
            <w:right w:val="single" w:sz="4" w:space="0" w:color="000000"/>
            <w:insideH w:val="single" w:sz="4" w:space="0" w:color="000000"/>
            <w:insideV w:val="single" w:sz="4" w:space="0" w:color="000000"/>
        </w:tblBorders>
    </w:tblPr>

    <!-- Column Grid Definition -->
    <w:tblGrid>
        <w:gridCol w:w="3000"/>  <!-- Column 1 width in twips -->
        <w:gridCol w:w="3000"/>  <!-- Column 2 width -->
        <w:gridCol w:w="3000"/>  <!-- Column 3 width -->
    </w:tblGrid>

    <!-- Header Row -->
    <w:tr>
        <w:trPr>
            <w:tblHeader/>  <!-- Repeat on each page -->
        </w:trPr>
        <w:tc>
            <w:tcPr>
                <w:tcW w:w="3000" w:type="dxa"/>
                <w:shd w:val="clear" w:color="auto" w:fill="2E74B5"/>
            </w:tcPr>
            <w:p>
                <w:pPr><w:jc w:val="center"/></w:pPr>
                <w:r>
                    <w:rPr><w:b/><w:color w:val="FFFFFF"/></w:rPr>
                    <w:t>Header 1</w:t>
                </w:r>
            </w:p>
        </w:tc>
        <w:tc>
            <w:tcPr>
                <w:tcW w:w="3000" w:type="dxa"/>
                <w:shd w:val="clear" w:color="auto" w:fill="2E74B5"/>
            </w:tcPr>
            <w:p>
                <w:pPr><w:jc w:val="center"/></w:pPr>
                <w:r>
                    <w:rPr><w:b/><w:color w:val="FFFFFF"/></w:rPr>
                    <w:t>Header 2</w:t>
                </w:r>
            </w:p>
        </w:tc>
        <w:tc>
            <w:tcPr>
                <w:tcW w:w="3000" w:type="dxa"/>
                <w:shd w:val="clear" w:color="auto" w:fill="2E74B5"/>
            </w:tcPr>
            <w:p>
                <w:pPr><w:jc w:val="center"/></w:pPr>
                <w:r>
                    <w:rPr><w:b/><w:color w:val="FFFFFF"/></w:rPr>
                    <w:t>Header 3</w:t>
                </w:r>
            </w:p>
        </w:tc>
    </w:tr>

    <!-- Data Row -->
    <w:tr>
        <w:tc>
            <w:tcPr>
                <w:tcW w:w="3000" w:type="dxa"/>
            </w:tcPr>
            <w:p>
                <w:r><w:t>Cell 1</w:t></w:r>
            </w:p>
        </w:tc>
        <w:tc>
            <w:tcPr>
                <w:tcW w:w="3000" w:type="dxa"/>
            </w:tcPr>
            <w:p>
                <w:r><w:t>Cell 2</w:t></w:r>
            </w:p>
        </w:tc>
        <w:tc>
            <w:tcPr>
                <w:tcW w:w="3000" w:type="dxa"/>
            </w:tcPr>
            <w:p>
                <w:r><w:t>Cell 3</w:t></w:r>
            </w:p>
        </w:tc>
    </w:tr>
</w:tbl>
```

#### Cell Merging

```xml
<!-- Horizontal merge (column span) -->
<w:tc>
    <w:tcPr>
        <w:gridSpan w:val="2"/>  <!-- Span 2 columns -->
    </w:tcPr>
    <w:p><w:r><w:t>Spans 2 columns</w:t></w:r></w:p>
</w:tc>

<!-- Vertical merge (row span) -->
<!-- First cell in merge -->
<w:tc>
    <w:tcPr>
        <w:vMerge w:val="restart"/>  <!-- Start vertical merge -->
    </w:tcPr>
    <w:p><w:r><w:t>Spans multiple rows</w:t></w:r></w:p>
</w:tc>

<!-- Continuation cells -->
<w:tc>
    <w:tcPr>
        <w:vMerge/>  <!-- Continue merge (no val attribute) -->
    </w:tcPr>
    <w:p/>  <!-- Empty paragraph required -->
</w:tc>
```

### Layout

#### Page Break

```xml
<w:p>
    <w:r>
        <w:br w:type="page"/>
    </w:r>
</w:p>

<!-- Alternative: page break before paragraph -->
<w:p>
    <w:pPr>
        <w:pageBreakBefore/>
    </w:pPr>
    <w:r>
        <w:t>This starts on a new page</w:t>
    </w:r>
</w:p>
```

#### Centered Paragraph

```xml
<w:p>
    <w:pPr>
        <w:jc w:val="center"/>
    </w:pPr>
    <w:r>
        <w:t>Centered text</w:t>
    </w:r>
</w:p>
```

**Justification values**: `left`, `center`, `right`, `both` (justified), `distribute`

#### Font Changes

```xml
<w:r>
    <w:rPr>
        <w:rFonts w:ascii="Times New Roman"
                  w:hAnsi="Times New Roman"
                  w:cs="Times New Roman"/>
        <w:sz w:val="24"/>     <!-- 12pt -->
        <w:szCs w:val="24"/>
    </w:rPr>
    <w:t>Times New Roman 12pt</w:t>
</w:r>
```

**Font attributes**:
- `w:ascii` - Latin characters
- `w:hAnsi` - High ANSI characters
- `w:cs` - Complex script (Arabic, Hebrew)
- `w:eastAsia` - East Asian characters

### Images

Full image structure with Drawing ML:

```xml
<w:p>
    <w:r>
        <w:drawing>
            <wp:inline distT="0" distB="0" distL="0" distR="0">
                <!-- Size in EMUs (914400 EMUs = 1 inch) -->
                <wp:extent cx="2743200" cy="1828800"/>  <!-- 3" x 2" -->
                <wp:effectExtent l="0" t="0" r="0" b="0"/>
                <wp:docPr id="1" name="Picture 1" descr="Image description"/>
                <wp:cNvGraphicFramePr>
                    <a:graphicFrameLocks xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
                                         noChangeAspect="1"/>
                </wp:cNvGraphicFramePr>
                <a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
                    <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
                        <pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">
                            <pic:nvPicPr>
                                <pic:cNvPr id="1" name="image1.png"/>
                                <pic:cNvPicPr/>
                            </pic:nvPicPr>
                            <pic:blipFill>
                                <a:blip r:embed="rId4"/>  <!-- Relationship ID -->
                                <a:stretch>
                                    <a:fillRect/>
                                </a:stretch>
                            </pic:blipFill>
                            <pic:spPr>
                                <a:xfrm>
                                    <a:off x="0" y="0"/>
                                    <a:ext cx="2743200" cy="1828800"/>
                                </a:xfrm>
                                <a:prstGeom prst="rect">
                                    <a:avLst/>
                                </a:prstGeom>
                            </pic:spPr>
                        </pic:pic>
                    </a:graphicData>
                </a:graphic>
            </wp:inline>
        </w:drawing>
    </w:r>
</w:p>
```

**EMU Conversion**:
- 1 inch = 914400 EMUs
- 1 cm = 360000 EMUs
- 1 pixel (96 DPI) = 9525 EMUs

### Links and Hyperlinks

#### External Hyperlink

```xml
<!-- In document.xml -->
<w:p>
    <w:hyperlink r:id="rId5" w:history="1">
        <w:r>
            <w:rPr>
                <w:rStyle w:val="Hyperlink"/>
                <w:color w:val="0563C1"/>
                <w:u w:val="single"/>
            </w:rPr>
            <w:t>Click here to visit website</w:t>
        </w:r>
    </w:hyperlink>
</w:p>

<!-- In document.xml.rels -->
<Relationship Id="rId5"
              Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink"
              Target="https://www.example.com"
              TargetMode="External"/>
```

#### Internal Bookmark Link

```xml
<!-- Create bookmark (target) -->
<w:p>
    <w:bookmarkStart w:id="0" w:name="section_intro"/>
    <w:r>
        <w:t>Introduction Section</w:t>
    </w:r>
    <w:bookmarkEnd w:id="0"/>
</w:p>

<!-- Link to bookmark -->
<w:p>
    <w:hyperlink w:anchor="section_intro" w:history="1">
        <w:r>
            <w:rPr>
                <w:color w:val="0563C1"/>
                <w:u w:val="single"/>
            </w:rPr>
            <w:t>Go to Introduction</w:t>
        </w:r>
    </w:hyperlink>
</w:p>
```

---

## 3. File Updates

### document.xml.rels (Relationships)

Location: `word/_rels/document.xml.rels`

```xml
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <!-- Required relationships -->
    <Relationship Id="rId1"
                  Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles"
                  Target="styles.xml"/>
    <Relationship Id="rId2"
                  Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings"
                  Target="settings.xml"/>
    <Relationship Id="rId3"
                  Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/fontTable"
                  Target="fontTable.xml"/>

    <!-- Image relationship -->
    <Relationship Id="rId4"
                  Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
                  Target="media/image1.png"/>

    <!-- Hyperlink relationship -->
    <Relationship Id="rId5"
                  Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink"
                  Target="https://www.example.com"
                  TargetMode="External"/>

    <!-- Comments relationship -->
    <Relationship Id="rId6"
                  Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"
                  Target="comments.xml"/>

    <!-- Numbering relationship -->
    <Relationship Id="rId7"
                  Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering"
                  Target="numbering.xml"/>

    <!-- Header relationship -->
    <Relationship Id="rId8"
                  Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header"
                  Target="header1.xml"/>

    <!-- Footer relationship -->
    <Relationship Id="rId9"
                  Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer"
                  Target="footer1.xml"/>
</Relationships>
```

### [Content_Types].xml

Location: Root of the ZIP archive

```xml
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
    <!-- Default content types by extension -->
    <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
    <Default Extension="xml" ContentType="application/xml"/>
    <Default Extension="png" ContentType="image/png"/>
    <Default Extension="jpeg" ContentType="image/jpeg"/>
    <Default Extension="jpg" ContentType="image/jpeg"/>
    <Default Extension="gif" ContentType="image/gif"/>
    <Default Extension="emf" ContentType="image/x-emf"/>
    <Default Extension="wmf" ContentType="image/x-wmf"/>

    <!-- Override content types for specific parts -->
    <Override PartName="/word/document.xml"
              ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
    <Override PartName="/word/styles.xml"
              ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
    <Override PartName="/word/settings.xml"
              ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
    <Override PartName="/word/fontTable.xml"
              ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.fontTable+xml"/>
    <Override PartName="/word/numbering.xml"
              ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>
    <Override PartName="/word/comments.xml"
              ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"/>
    <Override PartName="/word/commentsExtended.xml"
              ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.commentsExtended+xml"/>
    <Override PartName="/word/header1.xml"
              ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/>
    <Override PartName="/word/footer1.xml"
              ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>
    <Override PartName="/docProps/core.xml"
              ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
    <Override PartName="/docProps/app.xml"
              ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>
```

**When adding images**: Ensure the extension is registered in `<Default>` elements.

**When adding comments**: Add the Override for `comments.xml`.

---

## 4. Document Library (Python)

The `Document` class from `scripts/document.py` provides high-level OOXML manipulation with automatic schema compliance.

### Initialization

```python
from scripts.document import Document

# Load existing document
doc = Document("path/to/document.docx")

# Load with specific author for tracked changes
doc = Document("path/to/document.docx", author="Claude Assistant")

# Load unpacked document directory
doc = Document("path/to/unpacked_docx/", is_directory=True)
```

### Creating Tracked Changes

#### replace_node - Suggest Text Replacement

Replace text with tracked changes (old text marked as deleted, new text marked as inserted).

```python
# Find node by text content
node = doc.get_node_by_text("original text")

# Replace with tracked change
doc.replace_node(
    node=node,
    new_text="replacement text",
    author="Claude Assistant",
    date="2024-01-15T10:30:00Z"  # Optional, defaults to now
)

# Replace with formatting preserved
doc.replace_node(
    node=node,
    new_text="replacement text",
    preserve_formatting=True  # Keep original run properties
)
```

#### suggest_deletion - Mark Text for Deletion

```python
# Find text node to delete
node = doc.get_node_by_text("text to remove")

# Mark as deletion (tracked change)
doc.suggest_deletion(
    node=node,
    author="Claude Assistant"
)
```

#### suggest_insertion - Insert New Text

```python
# Find anchor node (insert after this)
anchor = doc.get_node_by_text("existing text")

# Insert new text as tracked insertion
doc.suggest_insertion(
    after_node=anchor,
    text="new inserted text",
    author="Claude Assistant"
)

# Insert with formatting
doc.suggest_insertion(
    after_node=anchor,
    text="bold inserted text",
    author="Claude Assistant",
    bold=True,
    font="Arial",
    size=24
)
```

### Adding Comments

#### add_comment - Create New Comment

```python
# Find text to comment on
node = doc.get_node_by_text("text requiring comment")

# Add comment
comment_id = doc.add_comment(
    node=node,
    text="This needs clarification.",
    author="Claude Assistant",
    initials="CA"
)

# Add comment with date
comment_id = doc.add_comment(
    node=node,
    text="Please review this section.",
    author="Claude Assistant",
    date="2024-01-15T10:30:00Z"
)
```

#### reply_to_comment - Reply to Existing Comment

```python
# Reply to existing comment by ID
doc.reply_to_comment(
    parent_comment_id=comment_id,
    text="I agree with this observation.",
    author="Second Reviewer"
)

# Get all comments and reply to first
comments = doc.get_comments()
if comments:
    doc.reply_to_comment(
        parent_comment_id=comments[0].id,
        text="Following up on this point...",
        author="Claude Assistant"
    )
```

### Rejecting Tracked Changes

#### revert_insertion - Reject an Insertion

Remove an inserted text (reject the insertion, restoring original state).

```python
# Find insertion node
insertion = doc.get_node_by_text("incorrectly inserted text")

# Revert (delete) the insertion
doc.revert_insertion(insertion)
```

#### revert_deletion - Reject a Deletion

Restore deleted text (reject the deletion, keeping the text).

```python
# Find deletion node (contains w:del)
deletion = doc.get_deletion_by_text("deleted text content")

# Revert (restore) the deletion
doc.revert_deletion(deletion)
```

### Inserting Images

```python
# Insert image after a paragraph
anchor = doc.get_node_by_text("Insert image below this")

doc.insert_image(
    after_node=anchor,
    image_path="path/to/image.png",
    width_inches=3.0,
    height_inches=2.0,
    alt_text="Description of the image"
)

# Insert image from bytes
with open("image.png", "rb") as f:
    image_bytes = f.read()

doc.insert_image(
    after_node=anchor,
    image_bytes=image_bytes,
    image_format="png",
    width_inches=4.0,
    height_inches=3.0
)
```

### Getting Nodes

#### get_node_by_text - Find by Text Content

```python
# Exact match
node = doc.get_node_by_text("exact text to find")

# Partial match
node = doc.get_node_by_text("partial", exact=False)

# Case-insensitive
node = doc.get_node_by_text("TEXT", case_sensitive=False)

# Get all matches
nodes = doc.get_nodes_by_text("repeated phrase", all_matches=True)
```

#### get_node_by_line_number - Find by Line Number

```python
# Get paragraph at specific line
para = doc.get_node_by_line_number(15)

# Get run at line and position
run = doc.get_node_by_line_number(15, position=5)
```

#### get_node_by_attributes - Find by XML Attributes

```python
# Find by style
heading = doc.get_node_by_attributes(
    tag="w:pPr",
    attributes={"w:pStyle": {"w:val": "Heading1"}}
)

# Find by ID
bookmark = doc.get_node_by_attributes(
    tag="w:bookmarkStart",
    attributes={"w:id": "0"}
)

# Find insertion by author
insertion = doc.get_node_by_attributes(
    tag="w:ins",
    attributes={"w:author": "Original Author"}
)
```

#### Additional Getters

```python
# Get all paragraphs
paragraphs = doc.get_paragraphs()

# Get all runs
runs = doc.get_runs()

# Get all tables
tables = doc.get_tables()

# Get all comments
comments = doc.get_comments()

# Get all tracked insertions
insertions = doc.get_insertions()

# Get all tracked deletions
deletions = doc.get_deletions()

# Get document text as string
text = doc.get_text()

# Get text with line numbers
numbered_text = doc.get_text_with_line_numbers()
```

### Saving with Validation

```python
# Save to new file
doc.save("output.docx")

# Save with validation
doc.save("output.docx", validate=True)

# Save to directory (unpacked)
doc.save("output_dir/", as_directory=True)

# Validate without saving
errors = doc.validate()
if errors:
    for error in errors:
        print(f"Validation error: {error}")
```

### Complete Example

```python
from scripts.document import Document

# Load document
doc = Document("contract.docx", author="Legal Review")

# Find and replace with tracked changes
clause = doc.get_node_by_text("30 days notice period")
doc.replace_node(
    node=clause,
    new_text="60 days notice period",
    author="Legal Review"
)

# Add comment explaining change
doc.add_comment(
    node=clause,
    text="Extended notice period per new compliance requirements.",
    author="Legal Review",
    initials="LR"
)

# Find another section to delete
obsolete = doc.get_node_by_text("This clause is no longer applicable")
doc.suggest_deletion(node=obsolete, author="Legal Review")

# Insert new paragraph
anchor = doc.get_node_by_text("Additional Terms")
doc.suggest_insertion(
    after_node=anchor,
    text="All parties agree to binding arbitration for dispute resolution.",
    author="Legal Review"
)

# Save with validation
errors = doc.save("contract_reviewed.docx", validate=True)
if not errors:
    print("Document saved successfully")
```

---

## 5. Tracked Changes (Redlining)

### Text Insertion

New text is wrapped in `w:ins` element:

```xml
<w:ins w:id="0" w:author="Claude Assistant" w:date="2024-01-15T10:30:00Z">
    <w:r>
        <w:rPr>
            <!-- Run properties preserved -->
        </w:rPr>
        <w:t>newly inserted text</w:t>
    </w:r>
</w:ins>
```

**Attributes**:
- `w:id` - Unique identifier for the revision
- `w:author` - Name of person making the change
- `w:date` - ISO 8601 timestamp

### Text Deletion

Deleted text uses `w:del` with `w:delText` instead of `w:t`:

```xml
<w:del w:id="1" w:author="Claude Assistant" w:date="2024-01-15T10:30:00Z">
    <w:r>
        <w:rPr>
            <!-- Original run properties -->
        </w:rPr>
        <w:delText>text being deleted</w:delText>
    </w:r>
</w:del>
```

**CRITICAL**: Use `w:delText` not `w:t` inside `w:del`. Using `w:t` will display the text as normal.

### Text Replacement (Delete + Insert)

A replacement is represented as deletion followed by insertion:

```xml
<w:p>
    <w:r>
        <w:t xml:space="preserve">The contract term is </w:t>
    </w:r>
    <!-- Deletion of old text -->
    <w:del w:id="0" w:author="Claude" w:date="2024-01-15T10:30:00Z">
        <w:r>
            <w:delText>30 days</w:delText>
        </w:r>
    </w:del>
    <!-- Insertion of new text -->
    <w:ins w:id="1" w:author="Claude" w:date="2024-01-15T10:30:00Z">
        <w:r>
            <w:t>60 days</w:t>
        </w:r>
    </w:ins>
    <w:r>
        <w:t>.</w:t>
    </w:r>
</w:p>
```

### Deleting Another Author's Insertion

**CRITICAL VALIDATION RULE**: Never modify content inside another author's tracked changes directly. Use nested deletion structure.

When deleting text that was inserted by another author, wrap the deletion around their insertion:

```xml
<!-- WRONG - Modifying another author's insertion directly -->
<!-- DO NOT DO THIS -->
<w:ins w:id="0" w:author="Original Author" w:date="2024-01-14T09:00:00Z">
    <w:del w:id="1" w:author="Claude" w:date="2024-01-15T10:30:00Z">
        <w:r>
            <w:delText>their inserted text</w:delText>
        </w:r>
    </w:del>
</w:ins>

<!-- CORRECT - Nested deletion structure -->
<w:del w:id="1" w:author="Claude" w:date="2024-01-15T10:30:00Z">
    <w:ins w:id="0" w:author="Original Author" w:date="2024-01-14T09:00:00Z">
        <w:r>
            <w:t>their inserted text</w:t>
        </w:r>
    </w:ins>
</w:del>
```

**Structure explanation**:
- Outer `w:del` indicates Claude is suggesting deletion of this content
- Inner `w:ins` preserves the history that Original Author inserted this text
- The `w:t` (not `w:delText`) is used inside `w:ins` because the original insertion used `w:t`

### Restoring Another Author's Deletion

When you want to reject/restore text that another author deleted:

```xml
<!-- Original deletion by another author -->
<w:del w:id="0" w:author="Original Author" w:date="2024-01-14T09:00:00Z">
    <w:r>
        <w:delText>text they deleted</w:delText>
    </w:r>
</w:del>

<!-- To restore: wrap in insertion (rejecting their deletion) -->
<w:ins w:id="1" w:author="Claude" w:date="2024-01-15T10:30:00Z">
    <w:del w:id="0" w:author="Original Author" w:date="2024-01-14T09:00:00Z">
        <w:r>
            <w:delText>text they deleted</w:delText>
        </w:r>
    </w:del>
</w:ins>
```

**Alternative - Convert deletion to regular text**:

```xml
<!-- Remove w:del wrapper and convert w:delText to w:t -->
<w:ins w:id="1" w:author="Claude" w:date="2024-01-15T10:30:00Z">
    <w:r>
        <w:t>text they deleted</w:t>
    </w:r>
</w:ins>
```

### Complete Tracked Changes Example

Original document:
```xml
<w:p>
    <w:r>
        <w:t>The agreement shall be effective for 12 months.</w:t>
    </w:r>
</w:p>
```

After edits by "Editor A":
```xml
<w:p>
    <w:r>
        <w:t xml:space="preserve">The agreement shall be effective for </w:t>
    </w:r>
    <w:del w:id="0" w:author="Editor A" w:date="2024-01-14T09:00:00Z">
        <w:r>
            <w:delText>12</w:delText>
        </w:r>
    </w:del>
    <w:ins w:id="1" w:author="Editor A" w:date="2024-01-14T09:00:00Z">
        <w:r>
            <w:t>24</w:t>
        </w:r>
    </w:ins>
    <w:r>
        <w:t xml:space="preserve"> months.</w:t>
    </w:r>
</w:p>
```

After review by "Claude" (rejecting Editor A's change to 24, suggesting 18 instead):
```xml
<w:p>
    <w:r>
        <w:t xml:space="preserve">The agreement shall be effective for </w:t>
    </w:r>
    <!-- Original deletion - keep as is (want to delete 12) -->
    <w:del w:id="0" w:author="Editor A" w:date="2024-01-14T09:00:00Z">
        <w:r>
            <w:delText>12</w:delText>
        </w:r>
    </w:del>
    <!-- Delete Editor A's insertion of 24 -->
    <w:del w:id="2" w:author="Claude" w:date="2024-01-15T10:30:00Z">
        <w:ins w:id="1" w:author="Editor A" w:date="2024-01-14T09:00:00Z">
            <w:r>
                <w:t>24</w:t>
            </w:r>
        </w:ins>
    </w:del>
    <!-- Insert Claude's suggestion of 18 -->
    <w:ins w:id="3" w:author="Claude" w:date="2024-01-15T10:30:00Z">
        <w:r>
            <w:t>18</w:t>
        </w:r>
    </w:ins>
    <w:r>
        <w:t xml:space="preserve"> months.</w:t>
    </w:r>
</w:p>
```

---

## Validation Rules Summary

### Must Follow

1. **Never modify content inside another author's tracked changes**
   - Always use nested deletion/insertion structure
   - Preserve the original change history

2. **Always use nested deletions for multi-author edits**
   - Wrap `w:del` around `w:ins` when deleting another's insertion
   - Wrap `w:ins` around `w:del` when restoring another's deletion

3. **Use correct text elements**
   - `w:t` for visible text
   - `w:delText` for deleted text inside `w:del`
   - Never use `w:t` directly inside `w:del`

4. **Maintain element ordering**
   - Follow strict schema order in `w:pPr` and `w:rPr`
   - Incorrect ordering corrupts documents

5. **Preserve whitespace correctly**
   - Use `xml:space="preserve"` for text with leading/trailing spaces
   - Split runs at word boundaries when making changes

6. **Use unique IDs**
   - Each `w:ins`, `w:del`, `w:comment` needs unique `w:id`
   - RSIDs must be valid 8-digit hex values

7. **Include required attributes**
   - `w:author` and `w:date` on all tracked changes
   - `r:id` for all relationship references

### Common Mistakes to Avoid

1. Putting `w:del` inside `w:ins` when deleting another's insertion (should be opposite)
2. Using `w:t` instead of `w:delText` inside `w:del`
3. Forgetting `xml:space="preserve"` on text with spaces
4. Incorrect element order in properties
5. Missing relationship entries in `.rels` files
6. Duplicate IDs for tracked changes
7. Missing content type registrations in `[Content_Types].xml`

---

## Quick Reference

### Namespaces

| Prefix | URI | Usage |
|--------|-----|-------|
| `w` | `http://schemas.openxmlformats.org/wordprocessingml/2006/main` | Main document |
| `r` | `http://schemas.openxmlformats.org/officeDocument/2006/relationships` | Relationships |
| `wp` | `http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing` | Drawing positioning |
| `a` | `http://schemas.openxmlformats.org/drawingml/2006/main` | DrawingML |
| `pic` | `http://schemas.openxmlformats.org/drawingml/2006/picture` | Pictures |

### Units

| Unit | Conversion |
|------|------------|
| Twips | 1 inch = 1440 twips |
| Half-points | 12pt = 24 half-points |
| EMUs | 1 inch = 914400 EMUs |
| Percentage (tables) | 5000 = 100% |

### Common Relationship Types

| Type | URI |
|------|-----|
| Styles | `http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles` |
| Settings | `http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings` |
| Image | `http://schemas.openxmlformats.org/officeDocument/2006/relationships/image` |
| Hyperlink | `http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink` |
| Comments | `http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments` |
| Header | `http://schemas.openxmlformats.org/officeDocument/2006/relationships/header` |
| Footer | `http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer` |
| Numbering | `http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering` |

---

*This documentation covers OOXML manipulation for Word 2007+ (.docx) format based on ECMA-376 standards.*
