# Plan: Video & PDF Knowledge Extraction Pipeline

## Task Description

Extract comprehensive knowledge from a collection of 6 training videos (in Russian) and 1 PDF document related to Bali real estate. The content includes company presentations, market statistics, financial models, Excel walkthroughs, and regional information. The goal is to create a text-based knowledge base with structured information and key visual screenshots.

## Objective

Transform 254+ minutes of Russian-language video content and PDF documents into a structured, text-only knowledge base with:
- Complete transcriptions with timestamps
- Visual context extracted from slides, Excel tables, and presentations
- Key screenshots representing important information blocks
- Structured, organized knowledge articles
- A questions section for any unclear or ambiguous information

## Problem Statement

The source materials contain critical business knowledge about:
- Bali regions and property markets
- Company presentation and offerings
- Estate market statistics and site understanding
- Financial models and tax structures (with Excel walkthroughs)
- Leasehold vs Freehold property differences

This information exists only in video format with visual components (slides, Excel tables) that need to be captured alongside audio transcription. Some videos are audio-sufficient while others require visual analysis for complete understanding.

## Solution Approach

Use a multi-phase parallel processing pipeline:

1. **Phase 1: Audio Extraction & Transcription** - Use ElevenLabs for all videos
2. **Phase 2: Visual Analysis** - Use Gemini video-analysis enriched with transcripts
3. **Phase 3: Screenshot Extraction** - Capture key visual moments
4. **Phase 4: PDF Processing** - Extract text and tables
5. **Phase 5: Knowledge Synthesis** - Combine all sources into structured articles
6. **Phase 6: Quality Review** - Re-evaluate for completeness and questions

## Data Inventory

### Audio-Only Videos (Transcription Sufficient)
| File | Duration | Size | Processing |
|------|----------|------|------------|
| `BaliRegions(text_is_enough).mp4` | 79.0 min | 325MB | ElevenLabs transcription only |
| `LeaseHoldFreeHoldDifference(AudioIsEnough).mp4` | 31.7 min | 112MB | ElevenLabs transcription only |

### Visual Analysis Required Videos
| File | Duration | Size | Visual Content |
|------|----------|------|----------------|
| `CompanyPresentation(PresentationSlidesInclude).mp4` | 21.2 min | 48MB | Presentation slides |
| `EstateMarketSiteUnderstanding.mp4` | 19.3 min | 78MB | Site/market visuals |
| `EstateMarketStatisticWalktrough.mp4` | 40.2 min | 219MB | Statistics/charts |
| `FinantialModels&Taxes(ExcelWalktroughAnalysisInVideo).mp4` | 63.1 min | 172MB | Excel spreadsheets |

### PDF Documents
| File | Size | Content |
|------|------|---------|
| `CompanyPresentationExtra.pdf` | 112KB | Additional presentation materials |

**Total Processing Time:** ~254 minutes of video content

## Relevant Files

### Existing Skills & Scripts
- `.claude/skills/eleven-labs/scripts/transcribe.py` - ElevenLabs transcription with timestamps, diarization
- `.claude/skills/video-analysis/` - Gemini-based video analysis
- `.claude/skills/video-processor/scripts/video_processor.py` - FFmpeg audio extraction, screenshot capture
- `.claude/skills/pdf/` - PDF text and table extraction

### Source Data
- `data/BaliRegions(text_is_enough).mp4`
- `data/LeaseHoldFreeHoldDifference(AudioIsEnough).mp4`
- `data/CompanyPresentation(PresentationSlidesInclude).mp4`
- `data/EstateMarketSiteUnderstanding.mp4`
- `data/EstateMarketStatisticWalktrough.mp4`
- `data/FinantialModels&Taxes(ExcelWalktroughAnalysisInVideo).mp4`
- `data/CompanyPresentationExtra.pdf`

### New Files (Output Structure)
```
knowledge_base/
├── transcripts/           # Raw transcriptions from ElevenLabs
│   ├── bali_regions_transcript.md
│   ├── leasehold_freehold_transcript.md
│   ├── company_presentation_transcript.md
│   ├── estate_market_site_transcript.md
│   ├── estate_market_statistics_transcript.md
│   └── financial_models_transcript.md
├── visual_analysis/       # Gemini enriched analysis
│   ├── company_presentation_analysis.md
│   ├── estate_market_site_analysis.md
│   ├── estate_market_statistics_analysis.md
│   └── financial_models_analysis.md
├── screenshots/           # Key visual captures
│   ├── company_presentation/
│   ├── estate_market_site/
│   ├── estate_market_statistics/
│   └── financial_models/
├── documents/             # Extracted PDF content
│   └── company_presentation_extra.md
├── articles/              # Final structured knowledge articles
│   ├── 01_bali_regions_overview.md
│   ├── 02_company_overview.md
│   ├── 03_estate_market_understanding.md
│   ├── 04_market_statistics.md
│   ├── 05_financial_models_taxes.md
│   └── 06_leasehold_vs_freehold.md
├── questions.md           # Unclear items requiring clarification
└── index.md               # Knowledge base index
```

## Implementation Phases

### Phase 1: Foundation & Setup
- Create output directory structure
- Verify all API keys (ELEVENLABS_API_KEY, GEMINI_API_KEY)
- Validate source files exist and are accessible

### Phase 2: Parallel Transcription
- Run ElevenLabs transcription for ALL 6 videos in parallel
- Use Russian language specification (`--language ru`)
- Enable speaker diarization and timestamps
- Output in markdown format for easy processing

### Phase 3: Visual Analysis (Parallel)
- For each visual-required video:
  - Feed transcription as context to Gemini
  - Analyze visual content with enriched prompts
  - Extract descriptions of slides, tables, charts
  - Generate structured visual summaries

### Phase 4: Screenshot Extraction
- Use FFmpeg to extract key frames at significant moments
- Capture slides, Excel tables, charts at regular intervals
- Name screenshots with timestamps for reference

### Phase 5: Document Processing
- Extract text from CompanyPresentationExtra.pdf
- Extract any tables present
- Format as markdown

### Phase 6: Knowledge Synthesis
- Merge transcripts with visual analysis
- Create structured knowledge articles
- Organize by topic/theme
- Cross-reference between documents

### Phase 7: Quality Review
- Re-evaluate each article for completeness
- Identify any gaps or unclear information
- Populate questions.md with items needing clarification
- Verify all visual information is captured

## Step by Step Tasks

### 1. Create Output Directory Structure
- Create `knowledge_base/` directory
- Create subdirectories: `transcripts/`, `visual_analysis/`, `screenshots/`, `documents/`, `articles/`
- Create empty `questions.md` file with template

### 2. Verify API Keys and Dependencies
- Check ELEVENLABS_API_KEY is set in `.env`
- Check GEMINI_API_KEY is set in `.env`
- Verify FFmpeg is installed
- Test ElevenLabs script connectivity
- Test Gemini video-analysis connectivity

### 3. Transcribe Audio-Only Videos (Parallel)
Run in parallel:
```bash
# BaliRegions
uv run .claude/skills/eleven-labs/scripts/transcribe.py \
  "data/BaliRegions(text_is_enough).mp4" \
  --diarize --format markdown --language ru \
  --output knowledge_base/transcripts/bali_regions_transcript.md

# LeaseHoldFreeHoldDifference
uv run .claude/skills/eleven-labs/scripts/transcribe.py \
  "data/LeaseHoldFreeHoldDifference(AudioIsEnough).mp4" \
  --diarize --format markdown --language ru \
  --output knowledge_base/transcripts/leasehold_freehold_transcript.md
```

### 4. Transcribe Visual Videos (Parallel)
Run in parallel:
```bash
# CompanyPresentation
uv run .claude/skills/eleven-labs/scripts/transcribe.py \
  "data/CompanyPresentation(PresentationSlidesInclude).mp4" \
  --diarize --format markdown --language ru \
  --output knowledge_base/transcripts/company_presentation_transcript.md

# EstateMarketSiteUnderstanding
uv run .claude/skills/eleven-labs/scripts/transcribe.py \
  "data/EstateMarketSiteUnderstanding.mp4" \
  --diarize --format markdown --language ru \
  --output knowledge_base/transcripts/estate_market_site_transcript.md

# EstateMarketStatisticWalktrough
uv run .claude/skills/eleven-labs/scripts/transcribe.py \
  "data/EstateMarketStatisticWalktrough.mp4" \
  --diarize --format markdown --language ru \
  --output knowledge_base/transcripts/estate_market_statistics_transcript.md

# FinantialModels&Taxes
uv run .claude/skills/eleven-labs/scripts/transcribe.py \
  "data/FinantialModels&Taxes(ExcelWalktroughAnalysisInVideo).mp4" \
  --diarize --format markdown --language ru \
  --output knowledge_base/transcripts/financial_models_transcript.md
```

### 5. Visual Analysis with Gemini (Sequential per video due to API limits)

For each visual video, create enriched analysis:

**CompanyPresentation:**
```bash
uv run scripts/analyze_video.py analyze \
  "data/CompanyPresentation(PresentationSlidesInclude).mp4" \
  "Analyze this presentation video. The transcript is provided below for context.

   TRANSCRIPT CONTEXT:
   [Insert transcript from knowledge_base/transcripts/company_presentation_transcript.md]

   TASK:
   1. Describe each slide shown in detail
   2. Extract all text visible on slides
   3. Note timestamps when slides change
   4. Describe any diagrams, charts, or images
   5. List key visual information not captured in audio
   6. Output in Russian
   7. Flag any unclear or ambiguous visual information

   Format as structured markdown with sections for each major topic/slide."
```

**EstateMarketSiteUnderstanding:**
- Similar prompt focusing on website/site navigation, market data visualizations

**EstateMarketStatisticWalktrough:**
- Focus on charts, graphs, statistical tables, data visualizations

**FinantialModels&Taxes (CRITICAL - Excel walkthrough):**
- Detailed prompt for Excel cell references, formulas, table structures
- Extract exact values shown in spreadsheets
- Capture formula logic and calculations demonstrated

### 6. Extract Key Screenshots

For each visual video, extract frames at key moments:
```bash
# Create screenshot directories
mkdir -p knowledge_base/screenshots/company_presentation
mkdir -p knowledge_base/screenshots/estate_market_site
mkdir -p knowledge_base/screenshots/estate_market_statistics
mkdir -p knowledge_base/screenshots/financial_models

# Extract frames every 30 seconds for each video
ffmpeg -i "data/CompanyPresentation(PresentationSlidesInclude).mp4" \
  -vf "fps=1/30,scale=1280:-1" \
  knowledge_base/screenshots/company_presentation/frame_%04d.jpg

# Similar for other videos
```

### 7. Process PDF Document
```python
import pdfplumber

with pdfplumber.open("data/CompanyPresentationExtra.pdf") as pdf:
    text = ""
    for page in pdf.pages:
        text += page.extract_text()
        tables = page.extract_tables()
        # Format tables as markdown
```
- Save to `knowledge_base/documents/company_presentation_extra.md`

### 8. Create Knowledge Articles

Synthesize all extracted information into structured articles:

**Article Template:**
```markdown
# [Topic Title]

## Summary
[2-3 sentence overview]

## Key Points
- [Bullet points of main takeaways]

## Detailed Content
[Full structured content organized by subtopics]

## Visual References
[Links to relevant screenshots]

## Related Articles
[Cross-references to other knowledge base articles]

## Source Materials
- Video: [filename], timestamps [X:XX - Y:YY]
- PDF: [if applicable]
```

### 9. Quality Review and Questions

- Read through each article
- Compare against source transcripts and visual analysis
- Identify gaps, contradictions, or unclear information
- Add items to `questions.md`:

```markdown
# Questions Requiring Clarification

## Financial Models
- [ ] Q1: What is the exact formula used for ROI calculation at timestamp 15:32?
- [ ] Q2: The tax rate mentioned seems inconsistent between slides - which is correct?

## Market Statistics
- [ ] Q3: The chart at 22:15 shows data for which year?

[etc.]
```

### 10. Create Index and Validate

- Create `knowledge_base/index.md` with links to all articles
- Verify all files are properly linked
- Ensure all visual references point to existing screenshots
- Final completeness check

## Testing Strategy

### Validation Checks
1. **Transcription Quality:** Spot-check random 5-minute segments from each video
2. **Visual Coverage:** Verify screenshots capture all unique slides/tables
3. **Article Completeness:** Ensure each article references all relevant source materials
4. **Cross-Reference Accuracy:** Verify links between articles work correctly
5. **Questions Completeness:** Review questions.md for any missed ambiguities

### Quality Metrics
- [ ] All 6 videos fully transcribed
- [ ] All 4 visual videos have Gemini analysis
- [ ] Screenshots exist for all major visual moments
- [ ] PDF fully extracted
- [ ] 6 knowledge articles created
- [ ] Index file complete
- [ ] Questions documented

## Acceptance Criteria

1. **Transcriptions Complete**
   - All 6 videos transcribed in markdown format
   - Russian language properly recognized
   - Timestamps present for all content

2. **Visual Analysis Complete**
   - All 4 visual videos analyzed with Gemini
   - Transcripts used as context for enrichment
   - Slides, tables, and charts described in detail

3. **Screenshots Extracted**
   - Key frames captured from visual videos
   - Named with timestamps for reference
   - Organized by video source

4. **Knowledge Base Structured**
   - 6 topic-based articles created
   - Cross-references between related content
   - Index file for navigation

5. **Quality Verified**
   - No information assumed - only extracted facts
   - Questions section populated with unclear items
   - Re-evaluation performed for completeness

## Validation Commands

Verify output structure:
```bash
# Check directory structure exists
ls -la knowledge_base/

# Verify transcripts
ls -la knowledge_base/transcripts/

# Verify visual analysis
ls -la knowledge_base/visual_analysis/

# Verify screenshots
find knowledge_base/screenshots -type f | wc -l

# Verify articles
ls -la knowledge_base/articles/

# Check questions file
cat knowledge_base/questions.md
```

Verify API connectivity:
```bash
# Test ElevenLabs
uv run .claude/skills/eleven-labs/scripts/transcribe.py --help

# Test Gemini
uv run scripts/analyze_video.py setup
```

## Notes

### Dependencies to Install (if needed)
```bash
# ElevenLabs
uv add python-dotenv httpx

# PDF processing
uv add pdfplumber

# FFmpeg (system)
brew install ffmpeg
```

### Important Considerations

1. **Language:** All content is in Russian - ensure language parameter is set correctly
2. **Visual Priority:** For Excel walkthrough video, visual analysis is CRITICAL - formulas and cell values must be captured
3. **No Assumptions:** Never assume information - if unclear, add to questions
4. **Parallel Processing:** Run transcriptions in parallel, but Gemini analysis may need rate limiting
5. **Large Files:** Some videos are 200MB+ - ensure adequate storage and API limits
6. **Quality Over Speed:** Re-evaluate and re-analyze to ensure completeness

### API Rate Limits
- ElevenLabs: Check plan limits for transcription minutes
- Gemini: Monitor quota for video analysis
- Run critical videos first (FinantialModels, CompanyPresentation)

### Prompts for Gemini Visual Analysis

**Presentation Slides Prompt:**
```
Analyze this video presentation. I will provide the audio transcript for context.

CONTEXT TRANSCRIPT:
{transcript}

YOUR TASK:
1. For each slide shown:
   - Describe the slide title and content
   - Extract ALL visible text exactly as shown
   - Note timestamp when slide appears
   - Describe any logos, images, diagrams
2. Identify key visual information NOT mentioned in audio
3. Flag any text that is partially visible or unclear
4. Output everything in Russian language
5. Structure output with clear markdown headers
```

**Excel Walkthrough Prompt:**
```
Analyze this Excel walkthrough video. The audio transcript is provided for context.

CONTEXT TRANSCRIPT:
{transcript}

YOUR TASK:
1. For each spreadsheet shown:
   - Describe the sheet name/tab visible
   - List column headers and row labels
   - Extract visible cell values
   - Note any formulas shown (bar or cells)
   - Describe color coding or formatting used
2. For calculations demonstrated:
   - Capture the formula logic explained
   - Note input cells and output cells
   - Record any specific numbers/percentages
3. Timestamp each major spreadsheet change
4. Flag cells or values that are unclear/partially visible
5. Output in Russian with structured markdown
```

**Market Statistics Prompt:**
```
Analyze this market statistics video. Audio transcript provided for context.

CONTEXT TRANSCRIPT:
{transcript}

YOUR TASK:
1. For each chart/graph shown:
   - Describe chart type (bar, line, pie, etc.)
   - Extract axis labels and legend
   - Note specific data points/values visible
   - Describe trends shown visually
2. For tables displayed:
   - Extract headers and all visible data
   - Note units of measurement
3. Capture any maps or geographic visualizations
4. Note timestamps for each major visual
5. Flag unclear or partially visible data
6. Output in Russian with structured markdown
```
