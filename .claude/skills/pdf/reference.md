# Advanced PDF Processing Reference

This document provides comprehensive coverage of advanced PDF processing techniques, including specialized libraries, complex workflows, and performance optimization strategies.

---

## Table of Contents

1. [pypdfium2 Library](#pypdfium2-library)
2. [JavaScript Libraries](#javascript-libraries)
3. [Advanced Command-Line Operations](#advanced-command-line-operations)
4. [Advanced Python Techniques](#advanced-python-techniques)
5. [Complex Workflows](#complex-workflows)
6. [Performance Optimization Tips](#performance-optimization-tips)
7. [Troubleshooting Common Issues](#troubleshooting-common-issues)
8. [License Information](#license-information)

---

## pypdfium2 Library

pypdfium2 is a Python binding to PDFium (Google's PDF rendering engine used in Chrome). It excels at rendering PDFs to high-quality images and provides robust text extraction.

### Installation

```bash
pip install pypdfium2
```

### Rendering PDF to Images

#### Basic Page Rendering

```python
import pypdfium2 as pdfium

# Open PDF
pdf = pdfium.PdfDocument("document.pdf")

# Render each page to an image
for i, page in enumerate(pdf):
    # Render at 300 DPI (scale factor of ~4.17 for 72 DPI base)
    bitmap = page.render(scale=300/72)
    pil_image = bitmap.to_pil()
    pil_image.save(f"page_{i+1}.png")

pdf.close()
```

#### High-Resolution Rendering with Custom Options

```python
import pypdfium2 as pdfium

pdf = pdfium.PdfDocument("document.pdf")

for i, page in enumerate(pdf):
    # Get page dimensions
    width = page.get_width()
    height = page.get_height()

    # Render with specific options
    bitmap = page.render(
        scale=4.0,              # 4x scale (288 DPI equivalent)
        rotation=0,             # 0, 90, 180, or 270 degrees
        crop=(0, 0, 0, 0),      # (left, bottom, right, top) margins to crop
        grayscale=False,        # Render in grayscale
        fill_color=0xFFFFFFFF,  # White background (ARGB format)
    )

    # Convert to PIL Image
    image = bitmap.to_pil()

    # Optionally convert to different format
    image.save(f"output_{i+1}.jpg", "JPEG", quality=95)

pdf.close()
```

#### Rendering Specific Page Regions

```python
import pypdfium2 as pdfium

pdf = pdfium.PdfDocument("document.pdf")
page = pdf[0]  # First page

# Define region to render (in PDF points, origin at bottom-left)
# crop = (left, bottom, right, top) - margins to exclude
width = page.get_width()
height = page.get_height()

# Render only the top half of the page
bitmap = page.render(
    scale=2.0,
    crop=(0, height/2, 0, 0)  # Exclude bottom half
)

image = bitmap.to_pil()
image.save("top_half.png")

pdf.close()
```

#### Batch Rendering with Multi-threading

```python
import pypdfium2 as pdfium
from concurrent.futures import ThreadPoolExecutor
import os

def render_page(args):
    pdf_path, page_index, output_dir, scale = args
    pdf = pdfium.PdfDocument(pdf_path)
    page = pdf[page_index]
    bitmap = page.render(scale=scale)
    image = bitmap.to_pil()
    output_path = os.path.join(output_dir, f"page_{page_index + 1:04d}.png")
    image.save(output_path)
    pdf.close()
    return output_path

def batch_render_pdf(pdf_path, output_dir, scale=2.0, max_workers=4):
    os.makedirs(output_dir, exist_ok=True)

    # Get page count
    pdf = pdfium.PdfDocument(pdf_path)
    page_count = len(pdf)
    pdf.close()

    # Prepare arguments
    args_list = [
        (pdf_path, i, output_dir, scale)
        for i in range(page_count)
    ]

    # Render in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(render_page, args_list))

    return results

# Usage
rendered_files = batch_render_pdf("large_document.pdf", "output_images", scale=3.0)
```

### Text Extraction

#### Basic Text Extraction

```python
import pypdfium2 as pdfium

pdf = pdfium.PdfDocument("document.pdf")

full_text = ""
for page in pdf:
    textpage = page.get_textpage()
    text = textpage.get_text_range()
    full_text += text + "\n\n"

print(full_text)
pdf.close()
```

#### Text Extraction with Character Positions

```python
import pypdfium2 as pdfium

pdf = pdfium.PdfDocument("document.pdf")
page = pdf[0]
textpage = page.get_textpage()

# Get character count
char_count = textpage.count_chars()

# Extract each character with position
for i in range(char_count):
    char = textpage.get_text_range(i, 1)

    # Get character bounding box (left, bottom, right, top)
    try:
        box = textpage.get_charbox(i)
        print(f"Char: '{char}' at ({box[0]:.1f}, {box[1]:.1f}, {box[2]:.1f}, {box[3]:.1f})")
    except Exception:
        # Some characters may not have valid positions
        pass

pdf.close()
```

#### Search Text in PDF

```python
import pypdfium2 as pdfium

def search_text_in_pdf(pdf_path, search_term):
    pdf = pdfium.PdfDocument(pdf_path)
    results = []

    for page_index, page in enumerate(pdf):
        textpage = page.get_textpage()

        # Search for the term
        searcher = textpage.search(search_term, match_case=False, match_whole_word=False)

        while searcher.search():
            # Get the found text position
            index = searcher.get_start_index()
            count = searcher.get_count()

            # Get bounding boxes for the found text
            rects = textpage.get_rectboxes(index, count)

            results.append({
                "page": page_index + 1,
                "text": textpage.get_text_range(index, count),
                "char_index": index,
                "char_count": count,
                "rects": rects
            })

    pdf.close()
    return results

# Usage
matches = search_text_in_pdf("document.pdf", "important term")
for match in matches:
    print(f"Page {match['page']}: Found '{match['text']}'")
```

#### Extract Text by Region

```python
import pypdfium2 as pdfium

def extract_text_from_region(pdf_path, page_num, left, bottom, right, top):
    """Extract text from a specific rectangular region of a page."""
    pdf = pdfium.PdfDocument(pdf_path)
    page = pdf[page_num - 1]  # 0-indexed
    textpage = page.get_textpage()

    # Get text bounded by the rectangle
    text = textpage.get_text_bounded(left, bottom, right, top)

    pdf.close()
    return text

# Usage - extract text from top-left quadrant
text = extract_text_from_region(
    "document.pdf",
    page_num=1,
    left=0,
    bottom=400,  # PDF coordinates start from bottom
    right=300,
    top=800
)
print(text)
```

---

## JavaScript Libraries

### pdf-lib (MIT License)

pdf-lib is a powerful JavaScript library for creating and modifying PDF documents. It works in both Node.js and browser environments.

#### Installation

```bash
npm install pdf-lib
```

#### Loading and Manipulating Existing PDFs

```javascript
const { PDFDocument, rgb, StandardFonts } = require('pdf-lib');
const fs = require('fs');

async function modifyPdf(inputPath, outputPath) {
    // Load existing PDF
    const existingPdfBytes = fs.readFileSync(inputPath);
    const pdfDoc = await PDFDocument.load(existingPdfBytes);

    // Get the first page
    const pages = pdfDoc.getPages();
    const firstPage = pages[0];
    const { width, height } = firstPage.getSize();

    // Embed a standard font
    const helveticaFont = await pdfDoc.embedFont(StandardFonts.Helvetica);

    // Add text to the page
    firstPage.drawText('Modified with pdf-lib!', {
        x: 50,
        y: height - 50,
        size: 24,
        font: helveticaFont,
        color: rgb(0.2, 0.2, 0.8),
    });

    // Add a rectangle
    firstPage.drawRectangle({
        x: 50,
        y: height - 100,
        width: 200,
        height: 30,
        borderColor: rgb(0, 0, 0),
        borderWidth: 1,
    });

    // Save the modified PDF
    const pdfBytes = await pdfDoc.save();
    fs.writeFileSync(outputPath, pdfBytes);
}

modifyPdf('input.pdf', 'output.pdf');
```

#### Creating Complex PDFs from Scratch

```javascript
const { PDFDocument, rgb, StandardFonts, PageSizes } = require('pdf-lib');
const fs = require('fs');

async function createComplexPdf(outputPath) {
    // Create a new PDF document
    const pdfDoc = await PDFDocument.create();

    // Embed fonts
    const helvetica = await pdfDoc.embedFont(StandardFonts.Helvetica);
    const helveticaBold = await pdfDoc.embedFont(StandardFonts.HelveticaBold);
    const timesRoman = await pdfDoc.embedFont(StandardFonts.TimesRoman);

    // Add first page (Letter size)
    const page1 = pdfDoc.addPage(PageSizes.Letter);
    const { width, height } = page1.getSize();

    // Draw title
    page1.drawText('Annual Report 2026', {
        x: 50,
        y: height - 80,
        size: 32,
        font: helveticaBold,
        color: rgb(0.1, 0.1, 0.5),
    });

    // Draw subtitle
    page1.drawText('Financial Summary', {
        x: 50,
        y: height - 120,
        size: 18,
        font: helvetica,
        color: rgb(0.3, 0.3, 0.3),
    });

    // Draw horizontal line
    page1.drawLine({
        start: { x: 50, y: height - 140 },
        end: { x: width - 50, y: height - 140 },
        thickness: 2,
        color: rgb(0.1, 0.1, 0.5),
    });

    // Draw table header
    const tableTop = height - 180;
    const colWidths = [200, 100, 100, 100];
    const headers = ['Department', 'Q1', 'Q2', 'Q3'];
    let xPos = 50;

    headers.forEach((header, i) => {
        page1.drawText(header, {
            x: xPos + 5,
            y: tableTop,
            size: 12,
            font: helveticaBold,
        });
        xPos += colWidths[i];
    });

    // Draw table rows
    const data = [
        ['Engineering', '$1.2M', '$1.4M', '$1.5M'],
        ['Marketing', '$800K', '$750K', '$900K'],
        ['Operations', '$500K', '$520K', '$480K'],
    ];

    let rowY = tableTop - 25;
    data.forEach(row => {
        xPos = 50;
        row.forEach((cell, i) => {
            page1.drawText(cell, {
                x: xPos + 5,
                y: rowY,
                size: 11,
                font: timesRoman,
            });
            xPos += colWidths[i];
        });
        rowY -= 20;
    });

    // Draw table borders
    page1.drawRectangle({
        x: 50,
        y: rowY,
        width: colWidths.reduce((a, b) => a + b, 0),
        height: tableTop - rowY + 20,
        borderColor: rgb(0, 0, 0),
        borderWidth: 1,
    });

    // Add second page
    const page2 = pdfDoc.addPage(PageSizes.Letter);

    page2.drawText('Page 2 - Additional Details', {
        x: 50,
        y: page2.getHeight() - 80,
        size: 24,
        font: helveticaBold,
    });

    // Save the PDF
    const pdfBytes = await pdfDoc.save();
    fs.writeFileSync(outputPath, pdfBytes);
}

createComplexPdf('complex_report.pdf');
```

#### Advanced Merge and Split Operations

```javascript
const { PDFDocument } = require('pdf-lib');
const fs = require('fs');

// Advanced merge with page selection
async function mergeSelectedPages(sources, outputPath) {
    /**
     * sources: Array of { path: string, pages: number[] | 'all' }
     * Example: [
     *   { path: 'doc1.pdf', pages: [0, 1, 2] },
     *   { path: 'doc2.pdf', pages: 'all' },
     *   { path: 'doc3.pdf', pages: [5, 6] }
     * ]
     */
    const mergedPdf = await PDFDocument.create();

    for (const source of sources) {
        const pdfBytes = fs.readFileSync(source.path);
        const pdf = await PDFDocument.load(pdfBytes);

        let pageIndices;
        if (source.pages === 'all') {
            pageIndices = pdf.getPageIndices();
        } else {
            pageIndices = source.pages;
        }

        const copiedPages = await mergedPdf.copyPages(pdf, pageIndices);
        copiedPages.forEach(page => mergedPdf.addPage(page));
    }

    const pdfBytes = await mergedPdf.save();
    fs.writeFileSync(outputPath, pdfBytes);
}

// Split PDF by page ranges
async function splitPdfByRanges(inputPath, ranges, outputDir) {
    /**
     * ranges: Array of { name: string, start: number, end: number }
     * Example: [
     *   { name: 'intro', start: 0, end: 2 },
     *   { name: 'chapter1', start: 3, end: 10 },
     *   { name: 'appendix', start: 11, end: 15 }
     * ]
     */
    const pdfBytes = fs.readFileSync(inputPath);
    const pdf = await PDFDocument.load(pdfBytes);

    for (const range of ranges) {
        const newPdf = await PDFDocument.create();
        const pageIndices = [];

        for (let i = range.start; i <= range.end; i++) {
            pageIndices.push(i);
        }

        const copiedPages = await newPdf.copyPages(pdf, pageIndices);
        copiedPages.forEach(page => newPdf.addPage(page));

        const outputBytes = await newPdf.save();
        fs.writeFileSync(`${outputDir}/${range.name}.pdf`, outputBytes);
    }
}

// Interleave pages from two PDFs (useful for duplex scanning)
async function interleavePages(frontPath, backPath, outputPath, reverseBack = true) {
    const frontBytes = fs.readFileSync(frontPath);
    const backBytes = fs.readFileSync(backPath);

    const frontPdf = await PDFDocument.load(frontBytes);
    const backPdf = await PDFDocument.load(backBytes);

    const frontPages = frontPdf.getPages();
    let backIndices = backPdf.getPageIndices();

    if (reverseBack) {
        backIndices = backIndices.reverse();
    }

    const mergedPdf = await PDFDocument.create();

    for (let i = 0; i < frontPages.length; i++) {
        // Copy front page
        const [frontPage] = await mergedPdf.copyPages(frontPdf, [i]);
        mergedPdf.addPage(frontPage);

        // Copy corresponding back page if exists
        if (i < backIndices.length) {
            const [backPage] = await mergedPdf.copyPages(backPdf, [backIndices[i]]);
            mergedPdf.addPage(backPage);
        }
    }

    const pdfBytes = await mergedPdf.save();
    fs.writeFileSync(outputPath, pdfBytes);
}

// Insert pages from one PDF into another
async function insertPages(basePath, insertPath, insertAfterPage, outputPath) {
    const baseBytes = fs.readFileSync(basePath);
    const insertBytes = fs.readFileSync(insertPath);

    const basePdf = await PDFDocument.load(baseBytes);
    const insertPdf = await PDFDocument.load(insertBytes);

    const insertedPages = await basePdf.copyPages(insertPdf, insertPdf.getPageIndices());

    // Insert pages after the specified page
    insertedPages.forEach((page, index) => {
        basePdf.insertPage(insertAfterPage + index + 1, page);
    });

    const pdfBytes = await basePdf.save();
    fs.writeFileSync(outputPath, pdfBytes);
}
```

#### Embedding Images and Custom Fonts

```javascript
const { PDFDocument, rgb } = require('pdf-lib');
const fontkit = require('@pdf-lib/fontkit');
const fs = require('fs');

async function createPdfWithCustomAssets(outputPath) {
    const pdfDoc = await PDFDocument.create();

    // Register fontkit for custom font embedding
    pdfDoc.registerFontkit(fontkit);

    // Embed custom font
    const customFontBytes = fs.readFileSync('fonts/Roboto-Regular.ttf');
    const customFont = await pdfDoc.embedFont(customFontBytes);

    // Embed images
    const pngBytes = fs.readFileSync('images/logo.png');
    const jpgBytes = fs.readFileSync('images/photo.jpg');

    const pngImage = await pdfDoc.embedPng(pngBytes);
    const jpgImage = await pdfDoc.embedJpg(jpgBytes);

    // Create page
    const page = pdfDoc.addPage([612, 792]);
    const { width, height } = page.getSize();

    // Draw logo (scaled to fit)
    const logoDims = pngImage.scale(0.5);
    page.drawImage(pngImage, {
        x: 50,
        y: height - 100,
        width: logoDims.width,
        height: logoDims.height,
    });

    // Draw photo with custom dimensions
    page.drawImage(jpgImage, {
        x: 50,
        y: height - 400,
        width: 200,
        height: 150,
    });

    // Draw text with custom font
    page.drawText('Custom Font Text', {
        x: 50,
        y: height - 450,
        size: 24,
        font: customFont,
        color: rgb(0.2, 0.2, 0.2),
    });

    const pdfBytes = await pdfDoc.save();
    fs.writeFileSync(outputPath, pdfBytes);
}
```

### pdfjs-dist (Apache License)

pdfjs-dist is Mozilla's PDF.js library for JavaScript. It excels at rendering and extracting structured content from PDFs.

#### Installation

```bash
npm install pdfjs-dist
```

#### Basic PDF Loading and Rendering

```javascript
const pdfjsLib = require('pdfjs-dist/legacy/build/pdf.js');
const { createCanvas } = require('canvas');
const fs = require('fs');

// Set worker source (required)
pdfjsLib.GlobalWorkerOptions.workerSrc = require.resolve(
    'pdfjs-dist/legacy/build/pdf.worker.js'
);

async function renderPdfToImage(pdfPath, outputPath, pageNum = 1, scale = 2.0) {
    // Load PDF
    const data = new Uint8Array(fs.readFileSync(pdfPath));
    const pdf = await pdfjsLib.getDocument({ data }).promise;

    // Get page
    const page = await pdf.getPage(pageNum);

    // Get viewport
    const viewport = page.getViewport({ scale });

    // Create canvas
    const canvas = createCanvas(viewport.width, viewport.height);
    const context = canvas.getContext('2d');

    // Render page
    await page.render({
        canvasContext: context,
        viewport: viewport,
    }).promise;

    // Save as PNG
    const buffer = canvas.toBuffer('image/png');
    fs.writeFileSync(outputPath, buffer);

    return { width: viewport.width, height: viewport.height };
}

renderPdfToImage('document.pdf', 'page1.png', 1, 2.0);
```

#### Extracting Text with Coordinates

```javascript
const pdfjsLib = require('pdfjs-dist/legacy/build/pdf.js');
const fs = require('fs');

pdfjsLib.GlobalWorkerOptions.workerSrc = require.resolve(
    'pdfjs-dist/legacy/build/pdf.worker.js'
);

async function extractTextWithPositions(pdfPath) {
    const data = new Uint8Array(fs.readFileSync(pdfPath));
    const pdf = await pdfjsLib.getDocument({ data }).promise;

    const allPageData = [];

    for (let pageNum = 1; pageNum <= pdf.numPages; pageNum++) {
        const page = await pdf.getPage(pageNum);
        const viewport = page.getViewport({ scale: 1.0 });
        const textContent = await page.getTextContent();

        const pageData = {
            pageNumber: pageNum,
            width: viewport.width,
            height: viewport.height,
            textItems: [],
        };

        for (const item of textContent.items) {
            if (item.str.trim() === '') continue;

            // Transform coordinates
            const tx = pdfjsLib.Util.transform(
                viewport.transform,
                item.transform
            );

            pageData.textItems.push({
                text: item.str,
                x: tx[4],
                y: tx[5],
                width: item.width,
                height: item.height,
                fontName: item.fontName,
                direction: item.dir,
            });
        }

        allPageData.push(pageData);
    }

    return allPageData;
}

async function main() {
    const result = await extractTextWithPositions('document.pdf');
    console.log(JSON.stringify(result, null, 2));
}

main();
```

#### Extracting Structured Text Blocks

```javascript
async function extractTextBlocks(pdfPath) {
    const data = new Uint8Array(fs.readFileSync(pdfPath));
    const pdf = await pdfjsLib.getDocument({ data }).promise;

    const blocks = [];

    for (let pageNum = 1; pageNum <= pdf.numPages; pageNum++) {
        const page = await pdf.getPage(pageNum);
        const textContent = await page.getTextContent();
        const viewport = page.getViewport({ scale: 1.0 });

        // Group text items into lines based on Y position
        const lineThreshold = 5; // pixels
        const lines = [];
        let currentLine = [];
        let lastY = null;

        for (const item of textContent.items) {
            const tx = pdfjsLib.Util.transform(viewport.transform, item.transform);
            const y = tx[5];

            if (lastY !== null && Math.abs(y - lastY) > lineThreshold) {
                if (currentLine.length > 0) {
                    // Sort by X position
                    currentLine.sort((a, b) => a.x - b.x);
                    lines.push({
                        y: lastY,
                        text: currentLine.map(i => i.text).join(' '),
                        items: currentLine,
                    });
                }
                currentLine = [];
            }

            currentLine.push({
                text: item.str,
                x: tx[4],
                y: y,
            });
            lastY = y;
        }

        // Don't forget the last line
        if (currentLine.length > 0) {
            currentLine.sort((a, b) => a.x - b.x);
            lines.push({
                y: lastY,
                text: currentLine.map(i => i.text).join(' '),
                items: currentLine,
            });
        }

        // Sort lines by Y position (top to bottom)
        lines.sort((a, b) => b.y - a.y);

        blocks.push({
            pageNumber: pageNum,
            lines: lines,
        });
    }

    return blocks;
}
```

#### Extracting Annotations and Forms

```javascript
const pdfjsLib = require('pdfjs-dist/legacy/build/pdf.js');
const fs = require('fs');

pdfjsLib.GlobalWorkerOptions.workerSrc = require.resolve(
    'pdfjs-dist/legacy/build/pdf.worker.js'
);

async function extractAnnotations(pdfPath) {
    const data = new Uint8Array(fs.readFileSync(pdfPath));
    const pdf = await pdfjsLib.getDocument({ data }).promise;

    const allAnnotations = [];

    for (let pageNum = 1; pageNum <= pdf.numPages; pageNum++) {
        const page = await pdf.getPage(pageNum);
        const annotations = await page.getAnnotations();

        const pageAnnotations = annotations.map(annot => ({
            pageNumber: pageNum,
            type: annot.subtype,
            rect: annot.rect,  // [x1, y1, x2, y2]
            contents: annot.contents,
            fieldName: annot.fieldName,
            fieldType: annot.fieldType,
            fieldValue: annot.fieldValue,
            alternativeText: annot.alternativeText,
            defaultAppearance: annot.defaultAppearance,
            url: annot.url,  // For link annotations
            dest: annot.dest,  // For internal links
            borderStyle: annot.borderStyle,
            color: annot.color,
        }));

        allAnnotations.push(...pageAnnotations);
    }

    return allAnnotations;
}

async function extractFormFields(pdfPath) {
    const annotations = await extractAnnotations(pdfPath);

    // Filter to form fields only
    const formFields = annotations.filter(a =>
        a.type === 'Widget' && a.fieldName
    );

    return formFields.map(field => ({
        name: field.fieldName,
        type: field.fieldType,
        value: field.fieldValue,
        page: field.pageNumber,
        rect: field.rect,
    }));
}

async function main() {
    const annotations = await extractAnnotations('document.pdf');
    console.log('All Annotations:', JSON.stringify(annotations, null, 2));

    const formFields = await extractFormFields('document.pdf');
    console.log('Form Fields:', JSON.stringify(formFields, null, 2));
}

main();
```

---

## Advanced Command-Line Operations

### poppler-utils Advanced Features

#### pdftotext with Bounding Boxes (bbox)

```bash
# Extract text with bounding box information (HTML format)
pdftotext -bbox input.pdf output.html

# Extract text with bounding boxes including layout information
pdftotext -bbox-layout input.pdf output.html

# Extract specific page range
pdftotext -f 1 -l 10 -bbox input.pdf output.html

# Set resolution for coordinate calculations
pdftotext -r 300 -bbox input.pdf output.html
```

The bbox output format:

```html
<!DOCTYPE html>
<html>
<head><title>output</title></head>
<body>
<doc>
  <page width="612.000000" height="792.000000">
    <word xMin="72.0" yMin="72.0" xMax="120.0" yMax="84.0">Hello</word>
    <word xMin="125.0" yMin="72.0" xMax="170.0" yMax="84.0">World</word>
  </page>
</doc>
</body>
</html>
```

Parsing bbox output with Python:

```python
from bs4 import BeautifulSoup
import subprocess
import json

def extract_text_with_bbox(pdf_path):
    # Run pdftotext with bbox option
    result = subprocess.run(
        ['pdftotext', '-bbox', pdf_path, '-'],
        capture_output=True,
        text=True
    )

    soup = BeautifulSoup(result.stdout, 'html.parser')
    pages = []

    for page in soup.find_all('page'):
        page_data = {
            'width': float(page.get('width')),
            'height': float(page.get('height')),
            'words': []
        }

        for word in page.find_all('word'):
            page_data['words'].append({
                'text': word.get_text(),
                'xMin': float(word.get('xmin')),
                'yMin': float(word.get('ymin')),
                'xMax': float(word.get('xmax')),
                'yMax': float(word.get('ymax'))
            })

        pages.append(page_data)

    return pages

# Usage
pages = extract_text_with_bbox('document.pdf')
print(json.dumps(pages, indent=2))
```

#### pdftoppm for High-Quality Image Conversion

```bash
# Convert all pages to PNG at 300 DPI
pdftoppm -png -r 300 input.pdf output_prefix

# Convert specific page range
pdftoppm -png -r 300 -f 1 -l 5 input.pdf output_prefix

# Convert to JPEG with quality setting
pdftoppm -jpeg -jpegopt quality=95 -r 300 input.pdf output_prefix

# Convert to TIFF (good for archival)
pdftoppm -tiff -tiffcompression lzw -r 300 input.pdf output_prefix

# Grayscale conversion
pdftoppm -png -gray -r 300 input.pdf output_prefix

# Scale to specific dimensions
pdftoppm -png -scale-to 1920 input.pdf output_prefix  # Scale width to 1920px

# Crop region (in pixels at given resolution)
pdftoppm -png -r 300 -x 100 -y 100 -W 500 -H 400 input.pdf output_prefix

# Single page conversion
pdftoppm -png -r 300 -f 3 -singlefile input.pdf page3
```

#### pdfimages for Image Extraction

```bash
# Extract all images (native format)
pdfimages input.pdf output_prefix

# Extract as JPEG only
pdfimages -j input.pdf output_prefix

# Extract as PNG only
pdfimages -png input.pdf output_prefix

# Extract all images preserving original format where possible
pdfimages -all input.pdf output_prefix

# List images without extracting
pdfimages -list input.pdf

# Extract from specific pages
pdfimages -f 1 -l 10 -png input.pdf output_prefix
```

The `-list` option provides detailed image information:

```
page   num  type   width height color comp bpc  enc interp  object ID x-ppi y-ppi size ratio
--------------------------------------------------------------------------------------------
   1     0 image    1200   800  rgb    3   8  jpeg   no        12  0   150   150  200K  14%
   1     1 image     400   300  gray   1   8  image  no        15  0   150   150   25K  21%
```

### qpdf Advanced Features

#### Complex Page Manipulation

```bash
# Reverse all pages
qpdf input.pdf --pages . z-1 -- reversed.pdf

# Extract odd pages only
qpdf input.pdf --pages . 1,3,5,7,9 -- odd_pages.pdf

# Extract even pages only
qpdf input.pdf --pages . 2,4,6,8,10 -- even_pages.pdf

# Duplicate pages
qpdf input.pdf --pages . 1,1,2,2,3,3 -- duplicated.pdf

# Complex page reordering (move last page to front)
qpdf input.pdf --pages . z . 1-r2 -- reordered.pdf

# Combine pages from multiple PDFs with complex selection
qpdf --empty --pages \
    doc1.pdf 1-5 \
    doc2.pdf z \
    doc3.pdf 1,3,5 \
    doc1.pdf 6-z \
    -- combined.pdf

# N-up printing (2 pages per sheet)
qpdf --underlay input.pdf --to=1 --from=2 -- input.pdf nup.pdf
```

#### PDF Optimization

```bash
# Linearize for fast web viewing
qpdf --linearize input.pdf linearized.pdf

# Object stream optimization
qpdf --object-streams=generate input.pdf optimized.pdf

# Compress streams
qpdf --compress-streams=y input.pdf compressed.pdf

# Remove unreferenced objects
qpdf --optimize-images input.pdf optimized.pdf

# Full optimization
qpdf --linearize --object-streams=generate --compress-streams=y input.pdf fully_optimized.pdf

# Recompress images (requires Ghostscript)
gs -sDEVICE=pdfwrite -dCompatibilityLevel=1.4 \
   -dPDFSETTINGS=/ebook \
   -dNOPAUSE -dQUIET -dBATCH \
   -sOutputFile=compressed.pdf input.pdf
```

#### PDF Repair

```bash
# Check PDF for errors
qpdf --check input.pdf

# Detailed check with JSON output
qpdf --check --json input.pdf

# Attempt repair
qpdf --replace-input input.pdf

# Repair and save to new file
qpdf input.pdf repaired.pdf

# Force repair even with serious errors
qpdf --ignore-xref-streams input.pdf repaired.pdf

# Rebuild xref table
qpdf --qdf input.pdf repaired.pdf
```

#### Encryption and Decryption

```bash
# Encrypt with 256-bit AES
qpdf --encrypt userpass ownerpass 256 -- input.pdf encrypted.pdf

# Encrypt with restrictions
qpdf --encrypt userpass ownerpass 256 \
    --print=none \
    --modify=none \
    --extract=n \
    -- input.pdf restricted.pdf

# Allow printing but restrict modifications
qpdf --encrypt "" ownerpass 256 \
    --print=full \
    --modify=none \
    -- input.pdf print_only.pdf

# Decrypt (requires password)
qpdf --password=ownerpass --decrypt encrypted.pdf decrypted.pdf

# Change password
qpdf --password=oldpass --encrypt newuser newowner 256 -- encrypted.pdf reencrypted.pdf

# Remove encryption (if you have owner password)
qpdf --password=ownerpass --decrypt encrypted.pdf decrypted.pdf
```

---

## Advanced Python Techniques

### pdfplumber Advanced Features

#### Text Extraction with Coordinates

```python
import pdfplumber
import json

def extract_text_with_positions(pdf_path):
    """Extract all text with detailed position information."""
    results = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            page_data = {
                "page": page_num,
                "width": page.width,
                "height": page.height,
                "chars": [],
                "words": [],
                "lines": []
            }

            # Extract characters with positions
            for char in page.chars:
                page_data["chars"].append({
                    "text": char["text"],
                    "x0": char["x0"],
                    "y0": char["top"],
                    "x1": char["x1"],
                    "y1": char["bottom"],
                    "fontname": char.get("fontname"),
                    "size": char.get("size")
                })

            # Extract words with positions
            words = page.extract_words(
                x_tolerance=3,
                y_tolerance=3,
                keep_blank_chars=False,
                use_text_flow=True
            )
            for word in words:
                page_data["words"].append({
                    "text": word["text"],
                    "x0": word["x0"],
                    "y0": word["top"],
                    "x1": word["x1"],
                    "y1": word["bottom"]
                })

            results.append(page_data)

    return results

# Usage
text_data = extract_text_with_positions("document.pdf")
print(json.dumps(text_data, indent=2))
```

#### Custom Table Extraction Settings

```python
import pdfplumber

def extract_tables_custom(pdf_path, page_num=1):
    """Extract tables with custom detection settings."""

    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[page_num - 1]

        # Custom table detection settings
        table_settings = {
            # Vertical strategy: "lines", "lines_strict", "text", or explicit lines
            "vertical_strategy": "text",

            # Horizontal strategy: "lines", "lines_strict", "text", or explicit lines
            "horizontal_strategy": "text",

            # Minimum words to form a table
            "min_words_vertical": 3,
            "min_words_horizontal": 1,

            # Snap tolerance for aligning cell boundaries
            "snap_tolerance": 3,
            "snap_x_tolerance": 3,
            "snap_y_tolerance": 3,

            # Join tolerance for connecting broken lines
            "join_tolerance": 3,
            "join_x_tolerance": 3,
            "join_y_tolerance": 3,

            # Edge tolerances
            "edge_min_length": 3,

            # Text settings
            "text_tolerance": 3,
            "text_x_tolerance": 3,
            "text_y_tolerance": 3,

            # Intersection tolerance
            "intersection_tolerance": 3,
            "intersection_x_tolerance": 3,
            "intersection_y_tolerance": 3,
        }

        # Find tables
        tables = page.find_tables(table_settings=table_settings)

        results = []
        for i, table in enumerate(tables):
            # Extract table data
            data = table.extract()

            results.append({
                "table_index": i,
                "bbox": table.bbox,  # (x0, y0, x1, y1)
                "rows": len(data),
                "cols": len(data[0]) if data else 0,
                "data": data
            })

        return results

# Extract tables using explicit line coordinates
def extract_table_with_explicit_lines(pdf_path, page_num, vertical_lines, horizontal_lines):
    """Extract table using manually specified line positions."""

    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[page_num - 1]

        table_settings = {
            "vertical_strategy": "explicit",
            "horizontal_strategy": "explicit",
            "explicit_vertical_lines": vertical_lines,
            "explicit_horizontal_lines": horizontal_lines,
        }

        tables = page.find_tables(table_settings=table_settings)

        if tables:
            return tables[0].extract()
        return None

# Usage with explicit lines
vertical_lines = [50, 150, 250, 350, 450]  # x coordinates
horizontal_lines = [100, 130, 160, 190, 220]  # y coordinates
table_data = extract_table_with_explicit_lines(
    "document.pdf",
    page_num=1,
    vertical_lines=vertical_lines,
    horizontal_lines=horizontal_lines
)
```

#### Visual Debugging for Table Extraction

```python
import pdfplumber
from PIL import Image

def debug_table_extraction(pdf_path, page_num=1, output_path="debug.png"):
    """Create a visual debug image showing detected table elements."""

    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[page_num - 1]

        # Convert page to image
        im = page.to_image(resolution=150)

        # Draw detected lines
        im.draw_lines(page.lines, stroke="red", stroke_width=1)

        # Draw detected rectangles (potential cell borders)
        im.draw_rects(page.rects, stroke="blue", stroke_width=1)

        # Draw detected curves
        if page.curves:
            im.draw_curves(page.curves, stroke="green", stroke_width=1)

        # Find and highlight tables
        tables = page.find_tables()
        for table in tables:
            im.draw_rect(table.bbox, stroke="purple", stroke_width=2)

            # Highlight cells
            for cell in table.cells:
                im.draw_rect(cell, stroke="orange", stroke_width=1)

        # Save debug image
        im.save(output_path, format="PNG")

        return len(tables)

# Usage
num_tables = debug_table_extraction("document.pdf", page_num=1, output_path="table_debug.png")
print(f"Found {num_tables} tables")
```

### reportlab Advanced Features

#### Professional Reports with Tables

```python
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, KeepTogether, ListFlowable, ListItem
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

def create_professional_report(output_path, data):
    """Create a professional report with tables and styling."""

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )

    # Custom styles
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name='CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#1a365d')
    ))

    styles.add(ParagraphStyle(
        name='SectionHeader',
        parent=styles['Heading2'],
        fontSize=14,
        spaceBefore=20,
        spaceAfter=10,
        textColor=colors.HexColor('#2c5282'),
        borderPadding=5,
        borderWidth=0,
        borderColor=colors.HexColor('#e2e8f0'),
    ))

    story = []

    # Title
    story.append(Paragraph("Financial Report Q4 2025", styles['CustomTitle']))
    story.append(Spacer(1, 20))

    # Executive Summary
    story.append(Paragraph("Executive Summary", styles['SectionHeader']))
    story.append(Paragraph(
        "This report provides a comprehensive overview of our financial "
        "performance for Q4 2025, highlighting key metrics, trends, and "
        "strategic recommendations.",
        styles['Normal']
    ))
    story.append(Spacer(1, 15))

    # Financial Data Table
    story.append(Paragraph("Financial Overview", styles['SectionHeader']))

    table_data = [
        ['Metric', 'Q3 2025', 'Q4 2025', 'Change'],
        ['Revenue', '$2.4M', '$2.8M', '+16.7%'],
        ['Expenses', '$1.8M', '$1.9M', '+5.6%'],
        ['Net Profit', '$600K', '$900K', '+50.0%'],
        ['Gross Margin', '42%', '45%', '+3%'],
    ]

    # Create table with professional styling
    table = Table(table_data, colWidths=[2*inch, 1.25*inch, 1.25*inch, 1*inch])

    table.setStyle(TableStyle([
        # Header row
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5282')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),

        # Data rows
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),

        # Alternating row colors
        ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#f7fafc')),
        ('BACKGROUND', (0, 4), (-1, 4), colors.HexColor('#f7fafc')),

        # Grid
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor('#1a365d')),

        # Padding
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))

    story.append(table)
    story.append(Spacer(1, 20))

    # Bullet list
    story.append(Paragraph("Key Highlights", styles['SectionHeader']))

    bullet_items = [
        "Revenue increased 16.7% quarter-over-quarter",
        "Net profit margin improved to 32%",
        "Customer acquisition costs reduced by 12%",
        "Employee productivity up 8%",
    ]

    bullet_list = ListFlowable(
        [ListItem(Paragraph(item, styles['Normal'])) for item in bullet_items],
        bulletType='bullet',
        start='circle',
        bulletFontSize=8,
        leftIndent=20,
    )
    story.append(bullet_list)

    # Build document
    doc.build(story)

# Usage
create_professional_report("financial_report.pdf", {})
```

#### Advanced Page Templates with Headers and Footers

```python
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfgen import canvas
from datetime import datetime

class NumberedCanvas(canvas.Canvas):
    """Custom canvas that adds page numbers and headers/footers."""

    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            self.draw_header()
            self.draw_footer()
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        self.setFont("Helvetica", 9)
        self.drawRightString(
            letter[0] - 0.75*inch,
            0.5*inch,
            f"Page {self._pageNumber} of {page_count}"
        )

    def draw_header(self):
        self.setFont("Helvetica-Bold", 10)
        self.drawString(0.75*inch, letter[1] - 0.5*inch, "Company Name")
        self.setFont("Helvetica", 9)
        self.drawRightString(
            letter[0] - 0.75*inch,
            letter[1] - 0.5*inch,
            "Confidential Document"
        )
        # Draw header line
        self.setStrokeColorRGB(0.7, 0.7, 0.7)
        self.line(0.75*inch, letter[1] - 0.6*inch, letter[0] - 0.75*inch, letter[1] - 0.6*inch)

    def draw_footer(self):
        self.setFont("Helvetica", 8)
        self.setFillColorRGB(0.5, 0.5, 0.5)
        self.drawString(
            0.75*inch,
            0.5*inch,
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        # Draw footer line
        self.setStrokeColorRGB(0.7, 0.7, 0.7)
        self.line(0.75*inch, 0.65*inch, letter[0] - 0.75*inch, 0.65*inch)


def create_document_with_headers(output_path):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=1*inch,
        bottomMargin=1*inch
    )

    styles = getSampleStyleSheet()
    story = []

    # Add content
    for i in range(1, 6):
        story.append(Paragraph(f"Chapter {i}", styles['Heading1']))
        for j in range(5):
            story.append(Paragraph(
                "Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 10,
                styles['Normal']
            ))
            story.append(Spacer(1, 12))
        story.append(PageBreak())

    # Build with custom canvas
    doc.build(story, canvasmaker=NumberedCanvas)

create_document_with_headers("document_with_headers.pdf")
```

---

## Complex Workflows

### Extracting Figures/Images from PDF

#### Python-based Image Extraction

```python
import fitz  # PyMuPDF
import os
from PIL import Image
import io

def extract_images_from_pdf(pdf_path, output_dir, min_width=100, min_height=100):
    """
    Extract all images from a PDF with size filtering.

    Args:
        pdf_path: Path to the PDF file
        output_dir: Directory to save extracted images
        min_width: Minimum image width to extract
        min_height: Minimum image height to extract

    Returns:
        List of extracted image paths with metadata
    """
    os.makedirs(output_dir, exist_ok=True)

    doc = fitz.open(pdf_path)
    extracted_images = []

    for page_num, page in enumerate(doc, 1):
        image_list = page.get_images(full=True)

        for img_index, img_info in enumerate(image_list):
            xref = img_info[0]

            try:
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]
                width = base_image["width"]
                height = base_image["height"]

                # Filter by size
                if width < min_width or height < min_height:
                    continue

                # Generate filename
                filename = f"page{page_num:03d}_img{img_index:03d}.{image_ext}"
                output_path = os.path.join(output_dir, filename)

                # Save image
                with open(output_path, "wb") as f:
                    f.write(image_bytes)

                extracted_images.append({
                    "path": output_path,
                    "page": page_num,
                    "width": width,
                    "height": height,
                    "format": image_ext,
                    "size_bytes": len(image_bytes)
                })

            except Exception as e:
                print(f"Error extracting image {xref} from page {page_num}: {e}")

    doc.close()
    return extracted_images

def extract_images_with_positions(pdf_path, output_dir):
    """Extract images along with their positions on each page."""
    os.makedirs(output_dir, exist_ok=True)

    doc = fitz.open(pdf_path)
    results = []

    for page_num, page in enumerate(doc, 1):
        page_rect = page.rect

        for img_index, img_info in enumerate(page.get_images(full=True)):
            xref = img_info[0]

            try:
                # Get image position on page
                img_rects = page.get_image_rects(xref)

                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]

                filename = f"page{page_num:03d}_img{img_index:03d}.{image_ext}"
                output_path = os.path.join(output_dir, filename)

                with open(output_path, "wb") as f:
                    f.write(image_bytes)

                for rect in img_rects:
                    results.append({
                        "path": output_path,
                        "page": page_num,
                        "page_width": page_rect.width,
                        "page_height": page_rect.height,
                        "x0": rect.x0,
                        "y0": rect.y0,
                        "x1": rect.x1,
                        "y1": rect.y1,
                        "width": rect.width,
                        "height": rect.height
                    })

            except Exception as e:
                print(f"Error: {e}")

    doc.close()
    return results

# Usage
images = extract_images_from_pdf("document.pdf", "extracted_images", min_width=50, min_height=50)
for img in images:
    print(f"Page {img['page']}: {img['path']} ({img['width']}x{img['height']})")
```

### Batch PDF Processing with Error Handling

```python
import os
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Callable, Any
from concurrent.futures import ProcessPoolExecutor, as_completed
import traceback
import json
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class ProcessingResult:
    """Result of processing a single PDF."""
    file_path: str
    success: bool
    output_path: Optional[str] = None
    error_message: Optional[str] = None
    error_traceback: Optional[str] = None
    processing_time: float = 0.0
    metadata: dict = field(default_factory=dict)

class PDFBatchProcessor:
    """Batch processor for PDFs with comprehensive error handling."""

    def __init__(
        self,
        input_dir: str,
        output_dir: str,
        max_workers: int = 4,
        continue_on_error: bool = True
    ):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.max_workers = max_workers
        self.continue_on_error = continue_on_error

        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.results: List[ProcessingResult] = []

    def get_pdf_files(self) -> List[Path]:
        """Get all PDF files in the input directory."""
        return list(self.input_dir.glob("**/*.pdf"))

    def process_single(
        self,
        pdf_path: Path,
        processor_func: Callable[[Path, Path], Any]
    ) -> ProcessingResult:
        """Process a single PDF file with error handling."""
        start_time = datetime.now()

        try:
            # Generate output path
            relative_path = pdf_path.relative_to(self.input_dir)
            output_path = self.output_dir / relative_path.with_suffix('.processed.pdf')
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Process the PDF
            metadata = processor_func(pdf_path, output_path)

            processing_time = (datetime.now() - start_time).total_seconds()

            return ProcessingResult(
                file_path=str(pdf_path),
                success=True,
                output_path=str(output_path),
                processing_time=processing_time,
                metadata=metadata or {}
            )

        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()

            return ProcessingResult(
                file_path=str(pdf_path),
                success=False,
                error_message=str(e),
                error_traceback=traceback.format_exc(),
                processing_time=processing_time
            )

    def process_batch(
        self,
        processor_func: Callable[[Path, Path], Any],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[ProcessingResult]:
        """Process all PDFs in the input directory."""
        pdf_files = self.get_pdf_files()
        total = len(pdf_files)

        logger.info(f"Found {total} PDF files to process")

        self.results = []
        completed = 0

        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_pdf = {
                executor.submit(self.process_single, pdf, processor_func): pdf
                for pdf in pdf_files
            }

            for future in as_completed(future_to_pdf):
                pdf = future_to_pdf[future]

                try:
                    result = future.result()
                    self.results.append(result)

                    if result.success:
                        logger.info(f"Processed: {pdf.name}")
                    else:
                        logger.error(f"Failed: {pdf.name} - {result.error_message}")

                        if not self.continue_on_error:
                            logger.error("Stopping batch processing due to error")
                            executor.shutdown(wait=False)
                            break

                except Exception as e:
                    logger.error(f"Unexpected error processing {pdf.name}: {e}")

                completed += 1
                if progress_callback:
                    progress_callback(completed, total)

        return self.results

    def generate_report(self, output_path: Optional[str] = None) -> dict:
        """Generate a processing report."""
        successful = [r for r in self.results if r.success]
        failed = [r for r in self.results if not r.success]

        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_files": len(self.results),
                "successful": len(successful),
                "failed": len(failed),
                "success_rate": len(successful) / len(self.results) * 100 if self.results else 0,
                "total_processing_time": sum(r.processing_time for r in self.results)
            },
            "successful_files": [
                {
                    "input": r.file_path,
                    "output": r.output_path,
                    "time": r.processing_time,
                    "metadata": r.metadata
                }
                for r in successful
            ],
            "failed_files": [
                {
                    "input": r.file_path,
                    "error": r.error_message,
                    "traceback": r.error_traceback
                }
                for r in failed
            ]
        }

        if output_path:
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2)

        return report


# Example processor function
def extract_text_processor(input_path: Path, output_path: Path) -> dict:
    """Example processor that extracts text from PDFs."""
    import pdfplumber

    text_content = []
    page_count = 0

    with pdfplumber.open(input_path) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_content.append(text)

    # Save extracted text
    text_output = output_path.with_suffix('.txt')
    with open(text_output, 'w') as f:
        f.write('\n\n'.join(text_content))

    return {
        "page_count": page_count,
        "text_length": sum(len(t) for t in text_content),
        "text_file": str(text_output)
    }


# Usage
if __name__ == "__main__":
    processor = PDFBatchProcessor(
        input_dir="./pdfs_to_process",
        output_dir="./processed_pdfs",
        max_workers=4,
        continue_on_error=True
    )

    def progress(completed, total):
        print(f"Progress: {completed}/{total} ({completed/total*100:.1f}%)")

    results = processor.process_batch(
        processor_func=extract_text_processor,
        progress_callback=progress
    )

    report = processor.generate_report("processing_report.json")
    print(f"\nCompleted: {report['summary']['successful']}/{report['summary']['total_files']}")
```

### Advanced PDF Cropping

```python
import fitz  # PyMuPDF
from dataclasses import dataclass
from typing import Tuple, Optional, List

@dataclass
class CropBox:
    """Define a crop region."""
    left: float
    top: float
    right: float
    bottom: float

    def to_rect(self, page_width: float, page_height: float) -> fitz.Rect:
        """Convert to fitz.Rect (coordinates from top-left)."""
        return fitz.Rect(
            self.left,
            self.top,
            page_width - self.right,
            page_height - self.bottom
        )

def crop_pdf_margins(
    input_path: str,
    output_path: str,
    margins: Tuple[float, float, float, float]
) -> None:
    """
    Crop PDF by removing margins.

    Args:
        input_path: Input PDF path
        output_path: Output PDF path
        margins: (left, top, right, bottom) margins to remove in points
    """
    doc = fitz.open(input_path)

    for page in doc:
        # Get current page size
        rect = page.rect

        # Calculate new crop box
        new_rect = fitz.Rect(
            margins[0],
            margins[1],
            rect.width - margins[2],
            rect.height - margins[3]
        )

        # Apply crop
        page.set_cropbox(new_rect)

    doc.save(output_path)
    doc.close()

def auto_crop_whitespace(
    input_path: str,
    output_path: str,
    margin: float = 10.0
) -> None:
    """
    Automatically crop whitespace from PDF pages.

    Args:
        input_path: Input PDF path
        output_path: Output PDF path
        margin: Additional margin to keep around content
    """
    doc = fitz.open(input_path)

    for page in doc:
        # Get page content bounding box
        # This finds the rectangle containing all page content
        blocks = page.get_text("dict")["blocks"]

        if not blocks:
            continue

        # Find content bounds
        min_x = float('inf')
        min_y = float('inf')
        max_x = 0
        max_y = 0

        for block in blocks:
            if "bbox" in block:
                bbox = block["bbox"]
                min_x = min(min_x, bbox[0])
                min_y = min(min_y, bbox[1])
                max_x = max(max_x, bbox[2])
                max_y = max(max_y, bbox[3])

        # Also consider images
        for img in page.get_images():
            rects = page.get_image_rects(img[0])
            for rect in rects:
                min_x = min(min_x, rect.x0)
                min_y = min(min_y, rect.y0)
                max_x = max(max_x, rect.x1)
                max_y = max(max_y, rect.y1)

        if min_x != float('inf'):
            # Apply margin
            crop_rect = fitz.Rect(
                max(0, min_x - margin),
                max(0, min_y - margin),
                min(page.rect.width, max_x + margin),
                min(page.rect.height, max_y + margin)
            )

            page.set_cropbox(crop_rect)

    doc.save(output_path)
    doc.close()

def crop_to_region(
    input_path: str,
    output_path: str,
    region: Tuple[float, float, float, float],
    pages: Optional[List[int]] = None
) -> None:
    """
    Crop PDF to a specific region.

    Args:
        input_path: Input PDF path
        output_path: Output PDF path
        region: (x0, y0, x1, y1) region to keep (in points from top-left)
        pages: List of page numbers to crop (0-indexed), None for all pages
    """
    doc = fitz.open(input_path)

    crop_rect = fitz.Rect(*region)

    for i, page in enumerate(doc):
        if pages is None or i in pages:
            page.set_cropbox(crop_rect)

    doc.save(output_path)
    doc.close()

def extract_region_as_new_pdf(
    input_path: str,
    output_path: str,
    page_num: int,
    region: Tuple[float, float, float, float],
    scale: float = 2.0
) -> None:
    """
    Extract a region from a page as a new single-page PDF.

    Args:
        input_path: Input PDF path
        output_path: Output PDF path
        page_num: Page number (0-indexed)
        region: (x0, y0, x1, y1) region to extract
        scale: Scale factor for quality
    """
    doc = fitz.open(input_path)
    page = doc[page_num]

    # Define the clip rectangle
    clip = fitz.Rect(*region)

    # Create a pixmap of the region
    mat = fitz.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=mat, clip=clip)

    # Create new PDF with the extracted region
    new_doc = fitz.open()
    new_page = new_doc.new_page(
        width=clip.width * scale,
        height=clip.height * scale
    )

    # Insert the image
    new_page.insert_image(
        new_page.rect,
        pixmap=pix
    )

    new_doc.save(output_path)
    new_doc.close()
    doc.close()

# Usage examples
if __name__ == "__main__":
    # Remove 1 inch margins from all sides
    crop_pdf_margins("input.pdf", "cropped_margins.pdf", (72, 72, 72, 72))

    # Auto-crop whitespace
    auto_crop_whitespace("input.pdf", "auto_cropped.pdf", margin=20)

    # Crop to specific region (top-left quarter)
    crop_to_region("input.pdf", "region_cropped.pdf", (0, 0, 306, 396))

    # Extract region as new PDF
    extract_region_as_new_pdf(
        "input.pdf",
        "extracted_region.pdf",
        page_num=0,
        region=(100, 100, 400, 300),
        scale=3.0
    )
```

---

## Performance Optimization Tips

### Large PDF Processing

```python
# Memory-efficient page iteration
import fitz

def process_large_pdf_efficiently(pdf_path: str):
    """Process large PDFs without loading all pages into memory."""

    doc = fitz.open(pdf_path)

    for page_num in range(len(doc)):
        # Load only one page at a time
        page = doc.load_page(page_num)

        # Process the page
        text = page.get_text()

        # Explicitly clear page from memory
        page = None

    doc.close()

# Streaming text extraction for very large files
def stream_text_extraction(pdf_path: str, output_path: str, chunk_size: int = 10):
    """Extract text in chunks to avoid memory issues."""

    doc = fitz.open(pdf_path)
    total_pages = len(doc)

    with open(output_path, 'w', encoding='utf-8') as f:
        for start in range(0, total_pages, chunk_size):
            end = min(start + chunk_size, total_pages)

            for page_num in range(start, end):
                page = doc.load_page(page_num)
                text = page.get_text()
                f.write(f"--- Page {page_num + 1} ---\n")
                f.write(text)
                f.write("\n\n")
                page = None

            # Force garbage collection between chunks
            import gc
            gc.collect()

    doc.close()
```

### Text Extraction Optimization

```python
import pdfplumber
from concurrent.futures import ThreadPoolExecutor
import multiprocessing

def parallel_text_extraction(pdf_path: str, max_workers: int = None):
    """Extract text from pages in parallel."""

    if max_workers is None:
        max_workers = multiprocessing.cpu_count()

    with pdfplumber.open(pdf_path) as pdf:
        page_count = len(pdf.pages)

    def extract_page_text(page_num: int) -> tuple:
        with pdfplumber.open(pdf_path) as pdf:
            page = pdf.pages[page_num]
            return page_num, page.extract_text()

    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(extract_page_text, i) for i in range(page_count)]
        for future in futures:
            page_num, text = future.result()
            results[page_num] = text

    # Combine in order
    return '\n\n'.join(results[i] for i in sorted(results.keys()))
```

### Image Extraction Optimization

```python
import fitz
from PIL import Image
import io

def optimized_image_extraction(
    pdf_path: str,
    output_dir: str,
    max_dimension: int = 2000,
    quality: int = 85
):
    """Extract images with size limiting and compression."""
    import os
    os.makedirs(output_dir, exist_ok=True)

    doc = fitz.open(pdf_path)

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)

        for img_index, img_info in enumerate(page.get_images()):
            xref = img_info[0]

            try:
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]

                # Load with PIL
                img = Image.open(io.BytesIO(image_bytes))

                # Resize if too large
                if max(img.size) > max_dimension:
                    ratio = max_dimension / max(img.size)
                    new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                    img = img.resize(new_size, Image.LANCZOS)

                # Convert to RGB if necessary (for JPEG)
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')

                # Save as optimized JPEG
                output_path = os.path.join(
                    output_dir,
                    f"page{page_num+1:03d}_img{img_index:03d}.jpg"
                )
                img.save(output_path, 'JPEG', quality=quality, optimize=True)

            except Exception as e:
                print(f"Error processing image: {e}")

        page = None

    doc.close()
```

### Form Filling Optimization

```python
from pypdf import PdfReader, PdfWriter
import io

def batch_fill_forms(
    template_path: str,
    data_list: list,
    output_dir: str
):
    """Efficiently fill multiple copies of a form template."""
    import os
    os.makedirs(output_dir, exist_ok=True)

    # Read template once
    with open(template_path, 'rb') as f:
        template_bytes = f.read()

    for i, data in enumerate(data_list):
        # Create fresh reader from bytes (not file)
        reader = PdfReader(io.BytesIO(template_bytes))
        writer = PdfWriter()

        # Copy all pages
        for page in reader.pages:
            writer.add_page(page)

        # Fill form fields
        writer.update_page_form_field_values(
            writer.pages[0],
            data
        )

        # Write output
        output_path = os.path.join(output_dir, f"filled_{i+1:04d}.pdf")
        with open(output_path, 'wb') as f:
            writer.write(f)

# Usage
data_list = [
    {"name": "John Doe", "date": "2026-01-14"},
    {"name": "Jane Smith", "date": "2026-01-14"},
    # ... more entries
]
batch_fill_forms("template.pdf", data_list, "filled_forms")
```

### Memory Management

```python
import gc
import sys

class PDFMemoryManager:
    """Context manager for memory-efficient PDF processing."""

    def __init__(self, aggressive_gc: bool = True):
        self.aggressive_gc = aggressive_gc
        self.initial_memory = None

    def __enter__(self):
        if self.aggressive_gc:
            gc.collect()
        self.initial_memory = self._get_memory_usage()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.aggressive_gc:
            gc.collect()
        final_memory = self._get_memory_usage()
        print(f"Memory delta: {final_memory - self.initial_memory:.2f} MB")
        return False

    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        import psutil
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024

    def checkpoint(self, label: str = ""):
        """Force garbage collection and report memory."""
        gc.collect()
        current = self._get_memory_usage()
        print(f"Memory at {label}: {current:.2f} MB")

# Usage
with PDFMemoryManager() as mm:
    # Process PDFs
    mm.checkpoint("after loading")
    # More processing
    mm.checkpoint("after extraction")
```

---

## Troubleshooting Common Issues

### Encrypted PDFs

```python
from pypdf import PdfReader
import fitz

def check_pdf_encryption(pdf_path: str) -> dict:
    """Check PDF encryption status and details."""
    result = {
        "is_encrypted": False,
        "encryption_method": None,
        "permissions": {},
        "requires_password": False
    }

    try:
        # Try with pypdf
        reader = PdfReader(pdf_path)
        result["is_encrypted"] = reader.is_encrypted

        if reader.is_encrypted:
            # Try to decrypt with empty password
            if reader.decrypt(""):
                result["requires_password"] = False
            else:
                result["requires_password"] = True

    except Exception as e:
        result["error"] = str(e)

    return result

def open_encrypted_pdf(pdf_path: str, password: str = ""):
    """Open an encrypted PDF with password handling."""

    # Try pypdf first
    try:
        reader = PdfReader(pdf_path)
        if reader.is_encrypted:
            if not reader.decrypt(password):
                raise ValueError("Incorrect password")
        return reader
    except Exception as e:
        print(f"pypdf failed: {e}")

    # Try PyMuPDF
    try:
        doc = fitz.open(pdf_path)
        if doc.is_encrypted:
            if not doc.authenticate(password):
                raise ValueError("Incorrect password")
        return doc
    except Exception as e:
        print(f"PyMuPDF failed: {e}")

    raise RuntimeError("Could not open encrypted PDF")

def remove_encryption(input_path: str, output_path: str, password: str = ""):
    """Remove encryption from a PDF."""

    doc = fitz.open(input_path)

    if doc.is_encrypted:
        if not doc.authenticate(password):
            raise ValueError("Incorrect password")

    # Save without encryption
    doc.save(output_path, encryption=fitz.PDF_ENCRYPT_NONE)
    doc.close()
```

### Corrupted PDFs

```python
import subprocess
import fitz

def check_pdf_validity(pdf_path: str) -> dict:
    """Check if a PDF is valid and report issues."""
    result = {
        "valid": False,
        "issues": [],
        "recoverable": False
    }

    # Try qpdf check
    try:
        check_result = subprocess.run(
            ['qpdf', '--check', pdf_path],
            capture_output=True,
            text=True
        )

        if check_result.returncode == 0:
            result["valid"] = True
        else:
            result["issues"].append(check_result.stderr)

    except FileNotFoundError:
        result["issues"].append("qpdf not installed")

    # Try to open with PyMuPDF
    try:
        doc = fitz.open(pdf_path)
        result["page_count"] = len(doc)
        result["valid"] = True
        doc.close()
    except Exception as e:
        result["issues"].append(f"PyMuPDF error: {str(e)}")

    return result

def repair_pdf(input_path: str, output_path: str) -> bool:
    """Attempt to repair a corrupted PDF."""

    # Method 1: Use qpdf
    try:
        result = subprocess.run(
            ['qpdf', '--replace-input', input_path],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return True
    except FileNotFoundError:
        pass

    # Method 2: Use PyMuPDF's garbage collection
    try:
        doc = fitz.open(input_path)
        doc.save(
            output_path,
            garbage=4,  # Maximum garbage collection
            deflate=True,
            clean=True
        )
        doc.close()
        return True
    except Exception as e:
        print(f"PyMuPDF repair failed: {e}")

    # Method 3: Use Ghostscript
    try:
        result = subprocess.run([
            'gs', '-o', output_path,
            '-sDEVICE=pdfwrite',
            '-dPDFSETTINGS=/prepress',
            input_path
        ], capture_output=True, text=True)

        return result.returncode == 0
    except FileNotFoundError:
        pass

    return False

def extract_pages_from_corrupted_pdf(
    input_path: str,
    output_dir: str
) -> list:
    """Extract individual pages from a partially corrupted PDF."""
    import os
    os.makedirs(output_dir, exist_ok=True)

    extracted = []

    try:
        doc = fitz.open(input_path)

        for i in range(len(doc)):
            try:
                # Try to extract single page
                new_doc = fitz.open()
                new_doc.insert_pdf(doc, from_page=i, to_page=i)

                output_path = os.path.join(output_dir, f"page_{i+1:04d}.pdf")
                new_doc.save(output_path)
                new_doc.close()

                extracted.append({
                    "page": i + 1,
                    "path": output_path,
                    "status": "success"
                })

            except Exception as e:
                extracted.append({
                    "page": i + 1,
                    "path": None,
                    "status": "failed",
                    "error": str(e)
                })

        doc.close()

    except Exception as e:
        print(f"Could not open PDF: {e}")

    return extracted
```

### Text Extraction Issues

```python
import pdfplumber
import fitz
import pytesseract
from pdf2image import convert_from_path

def diagnose_text_extraction(pdf_path: str) -> dict:
    """Diagnose text extraction issues."""
    result = {
        "has_text": False,
        "is_scanned": False,
        "encoding_issues": False,
        "recommended_method": None
    }

    # Try pdfplumber extraction
    try:
        with pdfplumber.open(pdf_path) as pdf:
            first_page = pdf.pages[0]
            text = first_page.extract_text()

            if text and len(text.strip()) > 50:
                result["has_text"] = True
                result["text_sample"] = text[:200]
                result["recommended_method"] = "pdfplumber"

            # Check for strange characters (encoding issues)
            if text:
                strange_chars = sum(1 for c in text if ord(c) > 65535 or c == '\ufffd')
                if strange_chars > len(text) * 0.1:
                    result["encoding_issues"] = True

    except Exception as e:
        result["pdfplumber_error"] = str(e)

    # Try PyMuPDF extraction
    try:
        doc = fitz.open(pdf_path)
        page = doc[0]
        text = page.get_text()

        if not result["has_text"] and text and len(text.strip()) > 50:
            result["has_text"] = True
            result["text_sample"] = text[:200]
            result["recommended_method"] = "pymupdf"

        doc.close()

    except Exception as e:
        result["pymupdf_error"] = str(e)

    # If no text found, likely a scanned document
    if not result["has_text"]:
        result["is_scanned"] = True
        result["recommended_method"] = "ocr"

    return result

def extract_text_with_fallback(pdf_path: str) -> str:
    """Extract text using multiple methods with fallback."""

    # Method 1: pdfplumber
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text_parts = []
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)

            if text_parts:
                full_text = '\n\n'.join(text_parts)
                if len(full_text.strip()) > 100:
                    return full_text
    except Exception:
        pass

    # Method 2: PyMuPDF
    try:
        doc = fitz.open(pdf_path)
        text_parts = []
        for page in doc:
            text = page.get_text()
            if text:
                text_parts.append(text)
        doc.close()

        if text_parts:
            full_text = '\n\n'.join(text_parts)
            if len(full_text.strip()) > 100:
                return full_text
    except Exception:
        pass

    # Method 3: OCR
    try:
        images = convert_from_path(pdf_path)
        text_parts = []
        for img in images:
            text = pytesseract.image_to_string(img)
            text_parts.append(text)

        return '\n\n'.join(text_parts)
    except Exception as e:
        raise RuntimeError(f"All extraction methods failed: {e}")

def fix_encoding_issues(text: str) -> str:
    """Attempt to fix common encoding issues in extracted text."""

    # Common substitutions for encoding errors
    replacements = {
        '\ufffd': '',  # Replacement character
        '\x00': '',    # Null bytes
        '\u2022': '-', # Bullet
        '\u2013': '-', # En dash
        '\u2014': '--', # Em dash
        '\u2018': "'", # Left single quote
        '\u2019': "'", # Right single quote
        '\u201c': '"', # Left double quote
        '\u201d': '"', # Right double quote
        '\xa0': ' ',   # Non-breaking space
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    # Remove other non-printable characters
    text = ''.join(char for char in text if char.isprintable() or char in '\n\t')

    # Normalize whitespace
    import re
    text = re.sub(r' +', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()
```

---

## License Information

| Library | License | Commercial Use | Modification | Distribution |
|---------|---------|----------------|--------------|--------------|
| **pypdfium2** | Apache 2.0 / BSD | Yes | Yes | Yes |
| **pypdf** | BSD-3-Clause | Yes | Yes | Yes |
| **pdfplumber** | MIT | Yes | Yes | Yes |
| **reportlab** | BSD | Yes | Yes | Yes |
| **PyMuPDF (fitz)** | AGPL-3.0 or Commercial | Requires license | Requires license | Requires license |
| **pdf-lib** | MIT | Yes | Yes | Yes |
| **pdfjs-dist** | Apache 2.0 | Yes | Yes | Yes |
| **poppler-utils** | GPL-2.0+ | Yes (tools only) | Yes | Yes (with source) |
| **qpdf** | Apache 2.0 | Yes | Yes | Yes |
| **pytesseract** | Apache 2.0 | Yes | Yes | Yes |
| **Tesseract OCR** | Apache 2.0 | Yes | Yes | Yes |

### License Notes

1. **PyMuPDF (fitz)**: The AGPL license requires that any application using it must also be open source. For proprietary/commercial applications, a commercial license is required from Artifex.

2. **poppler-utils**: Tools are GPL-licensed, meaning any modifications to poppler itself must be distributed with source. However, simply using the command-line tools does not affect your application's license.

3. **pdf-lib**: The most permissive license for JavaScript PDF manipulation. Suitable for any commercial or open-source project.

4. **reportlab**: The open-source version is BSD-licensed. There is also a commercial "ReportLab PLUS" with additional features.

5. **All Apache 2.0 / MIT / BSD libraries**: These can be freely used in commercial projects with minimal restrictions (typically just attribution).

### Choosing the Right Library by License

For **commercial/proprietary projects**:
- Text extraction: pypdfium2, pdfplumber, pypdf
- PDF manipulation: pypdf, pdf-lib (JS)
- PDF creation: reportlab
- Command-line: qpdf

For **open-source projects**:
- All of the above, plus PyMuPDF for advanced features

### Attribution Requirements

Most permissive licenses require attribution. Include license notices in your documentation or about section:

```
This software uses the following open-source libraries:
- pypdf (BSD-3-Clause) - https://github.com/py-pdf/pypdf
- pdfplumber (MIT) - https://github.com/jsvine/pdfplumber
- pdf-lib (MIT) - https://github.com/Hopding/pdf-lib
- pdfjs-dist (Apache 2.0) - https://github.com/nicholasrafalski/pdfjs-dist
```
