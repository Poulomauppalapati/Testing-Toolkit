# Testing Toolkit v2.0.0 - Technical Documentation

A unified Azure DevOps desktop application (PySide6, dark glass UI) that
consolidates test case generation, bulk defect upload, and work-item PDF
packaging into a single board-driven experience.

---

## Quick Start

### From Source (connected machine with Python 3.10+)

```bash
cd src
python build.py     # one command: cleans, installs, checks, builds
```

`build.py` handles everything automatically in one command:

- Cleans old build/dist artifacts
- Installs all required packages (no manual pip)
- Runs environment verification + auto-resolves issues
- Produces a one-folder build in `src/dist/TestingToolkit/`

To run from source instead: `cd src && python main.py`

To run the test suite: `cd src && python tests/test_full_e2e.py`

### Portable Zero-Install (air-gapped / restricted machines)

```
Windows:    double-click install.cmd
macOS:      ./install.sh
Linux:      ./install.sh
```

Each launcher does a full clean-install-build-launch cycle on every run:

1. Cleans old `build/` and `dist/` directories + all `__pycache__`
2. Installs all packages from offline wheelhouse (pip + app deps + PyInstaller)
3. Builds the `.exe` via PyInstaller (bundles models, assets, all backends)
4. Launches the built `TestingToolkit.exe`

`install.cmd` is native cmd.exe (NO Git Bash dependency). `install.sh` is
for macOS/Linux. No Python, pip, or network access required on the target
machine - everything is bundled.

---

## What It Does

1. **Generate Test Cases** - Recursive Language Model with extended thinking,
   requirement decomposition, and coverage verification produces ADO Test
   Cases with per-client template support. Iterative regeneration with user
   feedback (up to 10 iterations per session).
2. **Bulk Defect Upload** - Parse defect documents (Word, Excel, PowerPoint,
   PDF) with adaptive heading detection and LLM fallback, generate a review
   Excel, then upload Bug work items to ADO with inherited board positions.
3. **Package PDFs** - bundles work items into per-WI PDFs, a combined PDF,
   and a KB-ready chunk folder.

---

## Architecture

### VS Code-Style Navigation

The app uses a dual-state navigation pattern:

- **Expanded**: Full nav panel with Projects list, Boards list, and action
  buttons (Settings, KB, Collapse)
- **Collapsed**: Thin activity bar (44px) with center-aligned SVG icon
  buttons (folder, board, gear, brain, expand chevron)

Toggle between states via the chevron button or keyboard shortcut. All buttons
auto-size to content - no hardcoded dimensions anywhere in the UI.

### Three-Pane Layout

```
+---+----------+----------------------------------------------+-----------+
| A | PROJECTS |  Kanban Board (columns x iterations)         |  Detail   |
| c |  (list)  |  [cards with id, title, state, assignee]     |  (HTML)   |
| t +----------+                                              |           |
| i | BOARDS   |  [Generate TC] [Package PDFs] [Bulk Defects] |           |
| v |  (list)  |  [Upload to ADO] [Manual Mode]              |           |
| i | [Gear]   |  log/progress panel (collapsible)            |           |
| t | [Brain]  |                                              |           |
| y | [Chevron]|                                              |           |
+---+----------+----------------------------------------------+-----------+
| status bar: connection state, TLS mode, build info                       |
+--------------------------------------------------------------------------+
```

### Package Structure

```
Testing Toolkit/
    install.cmd             # Windows native launcher (cmd.exe, no Git Bash)
    install.sh              # macOS/Linux launcher (clean + build + launch)
    python-embed/           # Portable Python (~27MB, created by make_portable.py)
    docs/
        DOCS.md             # This file
        Working_Reference.md # Local models & search technical overview
        rule_list.md        # Canonical bug/enhancement/constraint reference
    src/
        main.py             # Entry point (hardware init + bootstrap)
        build.py            # One-command OS-agnostic build pipeline
        doctor.py           # Environment preflight checks
        make_portable.py    # Downloads portable Python for offline deployment
        make_wheelhouse.py  # Wheel bundle builder for air-gapped installs
        requirements.txt    # Pinned dependencies
        clean_old_installs.py   # Remove old build artifacts safely
        fetch_models.py     # Offline model downloader
        assets/             # SVG icons (folder, board, gear, brain, chevrons)
        core/               # Configuration, logging, storage, TLS, API client, hardware
        ui/                 # PySide6 GUI: windows, dialogs, theming, animations
        ado/                # Azure DevOps API: boards, extraction, upload
        kb/                 # Knowledge base: storage, indexing, retrieval, OCR
        testgen/            # Test case generation: RLM, templates, Excel I/O
        defects/            # Bulk defect parsing: doc extraction, review Excel, ADO upload
        tools/              # PDF packaging, office conversion, Visio conversion
        wheelhouse/         # Pre-downloaded .whl files (created by make_wheelhouse.py)
        tests/              # E2E test suite + fixture generator
        build/              # PyInstaller build artifacts
        dist/               # Built distribution output
```

### Key Design Principles

- **Modular** - clean package separation with explicit boundaries between concerns
- **Dark-only** Material Design 3 theme with Apple HIG motion design
- **Animated** - all dialogs fade-in, buttons pulse on press, progress bars animate
- **Offline-first** - works behind air-gapped networks with bundled models
- **Zero-install portable** - bundled Python + pip + wheels; runs on bare machines
- **Blazing fast startup** - one-folder build, lazy imports, no splash screen
- **Hardware-aware** - auto-detects CPU cores, GPU (CUDA/DML/Metal), RAM; scales
  thread pools, batch sizes, and execution providers accordingly
- **Cross-platform** - Windows (x64/ARM64), macOS (Intel/Apple Silicon), Linux (x64)
- **Cross-architecture** - ARM/Apple Silicon native support with Metal/CoreML detection
- **LLM-provider neutral** - works with any API-compatible LLM provider
- **OS keyring** for credential storage (no plaintext secrets)
- **Combined TLS bundle** for corporate proxy compatibility (Zscaler)
- **Deterministic** - same inputs produce same outputs
- **Memory-agnostic** - streaming and chunked processing; works on 4GB RAM

### Dependency Flow (No Circular Imports)

```
core  <-  ado  <-  kb  <-  testgen  <-  tools
  ^                                       ^
  +---------------- ui -------------------+
```

- core imports NOTHING from other internal packages
- ado imports from core only
- kb imports from core + tools (for office_convert)
- testgen imports from core + kb + ado
- tools imports from core only
- ui imports from EVERYTHING (it's the integration layer)

---

## Features

### 1. Test Case Generation (Recursive Language Model)

The RLM pipeline maximizes test case quality through multiple stages:

1. **Navigate** - fast model examines a chunk map and selects relevant
   chunks for the work items.
2. **Map** - each selected chunk is distilled to relevant facts.
3. **Decompose** - fast model enumerates atomic testable requirements as
   a numbered checklist (field validations, boundaries, state transitions,
   error conditions).
4. **Generate** - primary model with **Extended Thinking** (10k token
   reasoning budget) plans test strategy before producing JSON. The
   decomposed requirements are included as an explicit coverage target.
5. **Verify + Gap-Fill** - a second pass maps requirements to generated
   test cases, identifies uncovered acceptance criteria, and produces
   additional test cases for gaps. Always-on by default.

KBs up to ~375 pages (150k tokens) skip navigate/map and are passed
whole for 100% information coverage. Projects with no KB generate from
work items alone.

**Quality Features:**
- Extended Thinking (temperature=1.0, cached for determinism)
- Few-Shot Examples (3 gold-standard TCs in system prompt)
- Requirement Decomposition (atomic coverage checklist)
- Coverage Verification + Gap-Fill (always-on)
- Context Prioritization (longer=more relevant, sorted first)
- Query Decomposition (multi-sub-query retrieval for multi-criteria stories)
- Contextual Retrieval (LLM-generated situating prefixes per chunk, 49-67%
  fewer retrieval misses)
- Cache-first determinism (first run non-deterministic with thinking;
  result cached; re-runs are byte-identical)

**Regeneration with Feedback:**
After generation, users can provide change instructions (paragraph input)
and the entire test set is regenerated incorporating the feedback. Up to
10 regeneration iterations per session per set of work items.

**Models used:**
- Primary: configurable (generation quality + extended thinking)
- Fast: configurable (retrieval navigation, decomposition, contextual retrieval)

### 2. Per-Client Template Support

Upload a client's Excel test-script template (one per testing phase:
Implementation / SIT / UAT). Templates are typically workbooks with
existing test data for another scenario — the app analyzes the
**structure, formatting, styling, sheet organization, merged cells,
column widths, and data patterns** to understand the layout.

**LLM-Assisted Analysis (automatic on upload):**

- The template's full structure is sent to the LLM for semantic analysis
- The LLM identifies the header row, column purposes, and row organization
  even with non-English headers, custom abbreviations, or unconventional layouts
- The analysis examines data patterns to confirm field mappings (e.g., a
  column titled "Description" containing step-by-step actions maps to "action")
- The result is saved as a deterministic spec — all subsequent renders use
  the cached spec with zero LLM calls
- Falls back to heuristic detection if no API key is configured

**Deterministic Rendering:**
Once analyzed, the spec drives a deterministic renderer that fills a *copy
of the original template* (preserving its headers, branding, column widths,
and styles) with generated test cases. Same inputs = same outputs, always.

**Flow:** Project KB dialog > Templates tab > Upload template (auto-analyzed
by AI) > Generate test cases > template version auto-rendered.

### 3. PDF Packaging

**Per-WI PDFs** contain:
- Cover page (title, metadata, description with inline images,
  acceptance criteria, comments)
- Attachments separator
- All attachments converted to PDF (Office, images, existing PDFs)

**Combined PDF** (`All_WIs_Combined.pdf`) merges all selected WI PDFs.

**KB Bundle** (`Upload to KB/` folder) splits the combined PDF into
AI knowledge base-ready chunks:
- Text chunks (each < 700 KB / ~175k tokens)
- Image-lookup PDFs (one image per page, labeled)
- index.json + README.md

### 4. Hybrid Retrieval

For KBs exceeding the 150k-token direct threshold, hybrid retrieval
selects the top 32 most relevant chunks (from a pool of 96 candidates):

- **BM25** lexical search (always active)
- **Dense vectors** (fastembed ONNX, bge-small-en-v1.5)
- **Reciprocal Rank Fusion** combining both
- **Cross-encoder reranking** (ms-marco-MiniLM-L-6-v2)
- **Contextual Retrieval** (LLM-generated situating prefixes per chunk,
  applied at index time, improves retrieval accuracy 49-67%)
- **Query Decomposition** (heuristic sub-query extraction from acceptance
  criteria; multi-query retrieval unions results for better recall)

Falls back to BM25-only when dense models are absent.

### 5. Knowledge Base Management

Per-project KB supports:
- Documents: .md .txt .pdf .docx .xlsx .pptx .html .csv .json
- Scanned PDFs: automatic OCR via RapidOCR + PyMuPDF rasterizer
- Images: OCR text extraction
- Audio/Video: transcription via faster-whisper (optional)
- Legacy formats: .doc .ppt .msg .odt .eml .epub via olefile

Index rebuilds automatically when documents change. Resumable
background indexing with progress reporting.

### 6. Upload to ADO

Push reviewed test cases to Azure DevOps:

- Creates Test Cases as children of parent stories
- ADO-compliant Steps XML
- Re-reads the reviewed Excel (honors Skip=Yes edits)

### 7. Bulk Defect Upload

Parse defect documents and create Bug work items in ADO:

1. **Select** - one or more documents (Word, Excel, PowerPoint, PDF)
2. **Parse** - adaptive heading detection extracts parent ID, title,
   description, repro steps, severity, expected/actual results, images.
   Falls back to LLM parsing silently when programmatic parsing fails.
3. **Review** - generates an Excel with all defects + embedded images.
   User edits (mark Skip=Yes to exclude).
4. **Upload** - creates Bug work items in ADO. Area Path, Iteration Path,
   and Board Column are automatically derived from the parent work item.
   Bugs are placed in "Ready for Triage" or equivalent column.

**Supported heading patterns** (case-insensitive, adaptive):

- Title: "Bug Title", "Defect Summary", "Issue Name", etc.
- Repro Steps: "Steps to Reproduce", "Repro Steps", "Scenario", etc.
- Severity: "Severity", "Priority", "Impact", etc.
- Parent: "Parent Work Item", "User Story ID", "Linked WI", etc.

### 8. Manual Mode

When no API key is set (or key is rejected mid-run):

- Copy system prompt + work-item dump into any LLM session
- Paste JSON back into the app
- Same review > push flow

---

## Installation & Deployment

### Option 1: Portable Zero-Install (Recommended for restricted machines)

For machines that cannot install Python, cannot reach PyPI, or are behind
Zscaler/air-gap. Two machines involved:

- **Machine A - connected** (your work box; reaches PyPI through Zscaler).
  Used once to prepare the portable bundle.
- **Machine B - restricted** (the target laptop). Runs with NO Python,
  NO pip, NO network access required for installation.

#### What is bundled

| Item | How it travels | Where |
|------|----------------|-------|
| Python interpreter | Portable distribution (no installer) | `python-embed/` (~27 MB) |
| pip + setuptools | Offline wheels + get-pip.py | `python-embed/` + `src/wheelhouse/` |
| All Python dependencies | `.whl` files you build once | `src/wheelhouse/` |
| Dense + reranker models | Pre-downloaded, committed | `models/` (~152 MB) |
| OCR models (RapidOCR) | Inside the `rapidocr-onnxruntime` wheel | `src/wheelhouse/` |

#### Step 1: Prepare portable Python (Machine A)

```bash
cd src
python make_portable.py                         # auto-detect this platform
python make_portable.py --platform win_amd64    # cross-build for Windows x64
python make_portable.py --platform win_arm64    # cross-build for Windows ARM
python make_portable.py --platform macosx_11_0_arm64   # macOS Apple Silicon
python make_portable.py --platform linux_x86_64        # Linux x64
```

This downloads:
- Python embeddable zip (Windows) or python-build-standalone (macOS/Linux)
- `get-pip.py` for offline pip bootstrap
- pip/setuptools/wheel into the wheelhouse

#### Step 2: Build the wheelhouse (Machine A)

```bash
cd src
python make_wheelhouse.py
python make_wheelhouse.py --plat win_amd64 --pyver 3.12  # cross-build
```

Downloads every dependency in `requirements.txt` as platform-specific wheels.

#### Step 3: Transfer and run (Machine B)

```bash
# Zip entire project folder, transfer via USB/share/network
# On target machine, unzip and run:
./install.sh    # macOS / Linux
# or in Git Bash on Windows:
./install.sh
```

Every run: cleans, installs packages, builds .exe, launches (~2-3 min).
No sentinel or skip logic - always a guaranteed clean build.

#### Supported platforms

| Platform | Python Source | Architecture |
|----------|--------------|--------------|
| `win_amd64` | python.org embeddable zip | Intel/AMD x64 |
| `win_arm64` | python.org embeddable zip | Snapdragon ARM64 |
| `macosx_11_0_arm64` | python-build-standalone | Apple Silicon (M1-M4) |
| `macosx_10_9_x86_64` | python-build-standalone | Intel Mac |
| `linux_x86_64` | python-build-standalone | Linux x64 |

### Option 2: From Source (connected machine with Python 3.10+)

```bash
cd src
python build.py          # fully automated one-folder build
```

### Build Options

```bash
cd src
python build.py              # default: cleans + builds one-folder
python build.py --onefile    # single exe (slower startup)
python build.py --console    # keep console for debugging
```

### Option 3: Wheelhouse-Only (Python pre-installed, no network)

If Machine B already has Python but cannot reach PyPI:

```bash
# Machine A:
cd src && python make_wheelhouse.py

# Machine B (Python 3.10+ already installed):
cd src
python -m venv .venv
.venv\Scripts\activate       # Windows
python -m pip install --no-index --find-links wheelhouse -r requirements.txt
python main.py
```

### Dense Model Cache (Optional)

```bash
cd src
python fetch_models.py   # downloads embedding + reranker models
```

Models are bundled into the build automatically if present in `models/`.

---

## Hardware Utilization

The app auto-detects and uses all available hardware:

| Resource | Detection | Usage |
| -------- | --------- | ----- |
| CPU cores (physical) | `os.sched_getaffinity` / `psutil` / ARM heuristic | CPU-bound workers (embeddings, OCR) |
| CPU cores (logical) | `os.cpu_count()` | I/O-bound workers (HTTP, file ops) |
| Architecture | `platform.machine()` | ARM vs x86 detection |
| Apple Silicon | `sysctl machdep.cpu.brand_string` | M1/M2/M3/M4 chip identification |
| GPU (CUDA) | `torch.cuda` / onnxruntime providers | float16 inference, whisper STT |
| GPU (DirectML) | onnxruntime DML provider | Windows GPU fallback |
| GPU (Metal/CoreML) | Apple MPS / CoreML detection | macOS GPU acceleration |
| System RAM | `psutil` / `sysctl hw.memsize` / `/proc/meminfo` | Embedding batch sizing (32/64/128) |

All detection is fail-safe with conservative fallbacks. Missing GPU = CPU mode
with identical features (just slower). Set at startup via `core/hardware.py`.

**ONNX Provider Priority:** CUDA > CoreML (macOS) > DirectML (Windows) > CPU

Environment variables auto-set: `OMP_NUM_THREADS`, `MKL_NUM_THREADS`,
`OPENBLAS_NUM_THREADS`, `VECLIB_MAXIMUM_THREADS`, `NUMEXPR_NUM_THREADS`,
`ORT_NUM_THREADS`, `ACCELERATE_NUM_THREADS` (Apple Silicon).

---

## First-Run Setup

On first launch a wizard collects:

- **LLM API**: API key, base URL, primary model, fast model
- **Azure DevOps**: PAT, organization
- **TLS mode** and **display prefix**

Everything is editable later from Settings (gear icon in activity bar or
nav panel).

---

## Workspace Layout

```
~/TestingToolkit/
    settings.json              # base URL, model, org, prefix, TLS
    ui_prefs.json              # theme, window geometry, splitter state
    projects/
        <project>/
            system_prompt.txt  # custom RLM prompt
            kb/                # requirement documents
            kb_index.json      # cached chunk index
            templates/         # client Excel templates + specs
            generated/         # output payloads + review xlsx
    outputs/
        <project>/
            packets/           # PDF packaging output
                WI_123.pdf
                All_WIs_Combined.pdf
                Upload to KB/
                manifest.json
            testcases/         # test case review xlsx
    logs/                      # rotating debug logs
```

---

## Runtime Dependencies

### Required (auto-installed by build.py)

| Package | Purpose |
|---------|---------|
| PySide6 | GUI framework |
| httpx | ADO + LLM API HTTP |
| certifi | TLS root certificates |
| truststore | OS trust store (Zscaler) |
| keyring | Secure credential storage |
| openpyxl | Excel read/write |
| selectolax | HTML parsing |
| pypdf | PDF text extraction |
| reportlab | PDF generation |
| Pillow | Image handling |
| python-docx | Word documents |
| python-pptx | PowerPoint documents |
| xlrd | Legacy .xls files |
| striprtf | RTF documents |
| numpy | BM25 + vector math |

### Feature Set (auto-installed by build.py)

| Package | Purpose |
|---------|---------|
| fastembed | Dense ONNX embeddings + reranker |
| onnxruntime | CPU inference backend |
| rapidocr-onnxruntime | OCR for scanned PDFs |
| PyMuPDF | PDF rasterizer for OCR pipeline |
| olefile | Legacy .doc/.ppt/.msg extraction |

### Optional (not bundled by default)

| Package | Purpose |
|---------|---------|
| faster-whisper | Audio/video transcription |
| pytesseract | Alternative image OCR |

---

## Security

- API key and PAT in OS keyring (Windows Credential Manager / macOS
  Keychain / Secret Service)
- Combined CA trust bundle for TLS-intercepting proxies
- No plaintext secrets on disk
- All API calls at temperature=0 for repeatability

---

## Preflight Verification

Run `cd src && python doctor.py` to verify:

1. Python version (>= 3.10)
2. Hardware resources (CPU cores, RAM, GPU)
3. All required packages present
4. Feature packages active/inactive
5. OCR pipeline end-to-end (builds scanned PDF, runs OCR, verifies)
6. Multimedia backends (image OCR, audio STT, video processing)
7. Offline model cache

---

## Testing

```bash
cd src
python tests/generate_test_data.py   # generate 50+ fixture files (run once)
python tests/test_full_e2e.py        # run 57-check comprehensive E2E suite
```

The test suite covers:

- Hardware detection and thread environment (including ARM/Apple Silicon)
- Core modules (runtime config, LLM aliases, settings store)
- KB indexing (all file types: txt, md, csv, json, html, docx, xlsx, rtf)
- Testgen (payload parsing, validation, normalization, Excel round-trip)
- Defects (review Excel round-trip, uploader imports)
- ADO (auth headers, dataclasses, extract functions)
- Tools (office conversion, PDF packaging)
- UI (theme, main window, settings dialog, board grid, artifacts browser)
- Branding (no provider-specific labels in UI)
- Settings scenarios (env var overrides)

---

## Requirements

- **Portable mode**: Nothing pre-installed (Python bundled via `install.sh`)
- **Source mode**: Python 3.10+ (3.12 recommended)
- Windows 10/11 (x64/ARM64), macOS (Intel/Apple Silicon), or Linux (x64)
- Azure DevOps PAT + LLM API key (entered on first launch)
- Optional: NVIDIA GPU with CUDA / Apple Metal for accelerated inference

---

## Offline Troubleshooting

- **install.sh says "No Python 3.10+ found"** - the `python-embed/` folder
  is missing. Run `cd src && python make_portable.py` on a connected machine.

- **"get-pip.py not found"** - `make_portable.py` was not run or failed
  partway. Re-run it on Machine A (`cd src && python make_portable.py`).

- **doctor.py says "OCR engine MISSING"** - the wheelhouse did not include the
  OCR wheels, or the venv was not activated. Run:
  `pip install --no-index --find-links wheelhouse rapidocr-onnxruntime PyMuPDF`

- **"no matching distribution" / wheel won't install** - the wheelhouse was
  built for a different OS or Python. Rebuild on Machine A with `--plat` /
  `--pyver` matching Machine B exactly.

- **doctor.py warns "models/ cache not found"** - dense retrieval falls back
  to lexical BM25 (the app still works). To enable dense offline, run
  `cd src && python fetch_models.py` on Machine A and include `models/` in zip.

- **App starts but ADO / model fetch fails at runtime** - network reachability
  issue for the corporate ADO / LLM API gateway. Confirm those endpoints are
  allowlisted on Machine B.

---

## Portable Deployment Constraints (Hard-Won)

These constraints were discovered during production deployment and MUST be
respected in any future changes to the install/build pipeline:

### Python Embeddable Distribution

| Constraint | Reason |
|------------|--------|
| `python312._pth` must be PATCHED, never deleted | Deleting it breaks pip (site-packages becomes unreachable) |
| `._pth` must contain `..\src` entry | Relative to `python-embed/` dir; puts `src/` on sys.path for `from core.xxx` |
| `._pth` must contain `import site` | Required for pip/site-packages to work |
| `._pth` must contain `Lib\site-packages` | Without this, installed packages are invisible |
| Correct `._pth` content (exact): | `python312.zip`, `.`, `..\src`, `Lib\site-packages`, `import site` |

### PySide6 / Qt on Windows

| Constraint | Reason |
|------------|--------|
| NEVER run Qt apps in Git Bash (mintty) | PySide6 SEGFAULTS (0xC0000005) in mintty terminal |
| `install.cmd` must be native cmd.exe only | Git Bash dependency breaks Qt; cmd.exe works |
| `pythonw.exe` hides ALL errors | Window closes silently on crash; use `python.exe` for debugging |
| Exit code `-1073740791` (0xC0000409) | Qt STATUS_STACK_BUFFER_OVERRUN - usually plugin path issue |
| Exit code `-1073741819` (0xC0000005) | Access violation - Qt in mintty or missing DLL |
| Set `QT_PLUGIN_PATH` for embedded Python | Qt may not find plugins in non-standard install locations |

### Wheelhouse and Offline Install

| Constraint | Reason |
|------------|--------|
| Wheels are Python-version-specific | cp312 wheels do NOT work on Python 3.13 - must match exactly |
| `--no-index --find-links wheelhouse` required | Prevents pip from reaching the network |
| `--no-warn-script-location` suppresses noise | Scripts/ not on PATH in embedded Python - expected |
| `--force-reinstall` ensures clean state | Without it, pip skips "already installed" packages |
| PyInstaller must also be in wheelhouse | It is a build-time dep, not just runtime |
| `get-pip.py` must be in `python-embed/` | First-run bootstrap needs it before pip exists |

### Build Pipeline (install.cmd / install.sh)

| Constraint | Reason |
|------------|--------|
| No sentinel / skip logic | User expects guaranteed clean install every run |
| Always clean `build/` + `dist/` + `__pycache__` first | Stale bytecode causes import errors |
| `build.py --quiet` for clean output | Only show progress bar + errors; suppress verbose cleanup |
| Build bundles `models/` and `assets/` | PyInstaller `--add-data` for offline dense retrieval |
| Console stays open on error (`pause`) | So user can read the error before window closes |
| `start "" "%EXE%"` for final launch | Detaches from console; does NOT use pythonw.exe |

---

## File Reference

### Root (project root)

| File | Role |
| ---- | ---- |
| `install.sh` | macOS/Linux portable launcher (clean + install + build + launch) |
| `install.cmd` | Windows native launcher (clean + install + build + launch, no Git Bash) |

### docs/

| File | Role |
| ---- | ---- |
| `DOCS.md` | This file (full technical documentation) |
| `Working_Reference.md` | Local models, indexing, and search technical overview |
| `rule_list.md` | Canonical bug/enhancement/constraint reference |

### src/ Scripts

| File | Role |
| ---- | ---- |
| `main.py` | Entry point (hardware init + bootstrap) |
| `build.py` | One-command OS-agnostic build (cleans + installs + checks + builds) |
| `doctor.py` | Environment preflight checks |
| `make_portable.py` | Downloads portable Python for offline deployment |
| `make_wheelhouse.py` | Wheel bundle builder for air-gapped installs |
| `requirements.txt` | Pinned dependency list |
| `clean_old_installs.py` | Remove old build artifacts safely |
| `fetch_models.py` | Offline model downloader |

### src/assets/ - SVG Icons

| File | Role |
| ---- | ---- |
| `icon_folder.svg` | Projects (white folder outline) |
| `icon_board.svg` | Boards (white 4-tile grid) |
| `icon_gear.svg` | Settings (white gear/cog) |
| `icon_brain.svg` | Project KB (white brain) |
| `icon_chevron_left.svg` | Collapse nav (white left chevron) |
| `icon_chevron_right.svg` | Expand nav (white right chevron) |

### src/core/ - Configuration, Logging, Storage, TLS, API Client, Hardware

| File | Role |
| ---- | ---- |
| `core/__init__.py` | Package init and public exports |
| `core/app_config.py` | Constants, paths, defaults |
| `core/app_logging.py` | Rotating log configuration |
| `core/anthropic_client.py` | LLM API client wrapper |
| `core/orchestrator.py` | Extract + package + KB bundle pipeline |
| `core/pat_store.py` | PAT credential storage (keyring) |
| `core/prefs_store.py` | UI preferences persistence |
| `core/project_store.py` | Per-project storage + KB management |
| `core/runtime_config.py` | Runtime state and environment detection |
| `core/settings_store.py` | Settings persistence |
| `core/hardware.py` | Hardware detection (CPU/GPU/RAM/ARM/Metal) + thread env setup |
| `core/tls_helper.py` | Combined TLS bundle for proxy compatibility |

### src/ui/ - PySide6 GUI: Main Window, Dialogs, Theming, Animations

| File | Role |
| ---- | ---- |
| `ui/__init__.py` | Package init and public exports |
| `ui/main_window.py` | Three-pane GUI shell with VS Code-style activity bar |
| `ui/theme.py` | Material Design 3 dark theme (Apple HIG) |
| `ui/animations.py` | Qt property animations (fade, slide, pulse) |
| `ui/gui_common.py` | Shared widgets and utility functions |
| `ui/board_grid.py` | Kanban board grid display |
| `ui/generate_dialog.py` | Test case generation dialog |
| `ui/upload_dialog.py` | Upload to ADO dialog |
| `ui/global_settings_dialog.py` | Application settings dialog (auto-fits to content) |
| `ui/project_kb_dialog.py` | Project knowledge base management dialog |
| `ui/retrieval_preview_dialog.py` | Hybrid retrieval preview dialog |
| `ui/setup_wizard.py` | First-run setup wizard |
| `ui/artifacts_browser.py` | Artifacts browsing dialog |

### src/ado/ - Azure DevOps API: Boards, Work-Item Extraction, Test Case Creation

| File | Role |
| ---- | ---- |
| `ado/__init__.py` | Package init and public exports |
| `ado/api.py` | Azure DevOps HTTP API client |
| `ado/boards.py` | Board and iteration queries |
| `ado/extract.py` | Work-item field and attachment extraction |
| `ado/testcase_creator.py` | Test case validation + ADO upload |

### src/kb/ - Knowledge Base: Storage, Indexing, Hybrid Retrieval, OCR, Embeddings

| File | Role |
| ---- | ---- |
| `kb/__init__.py` | Package init and public exports |
| `kb/store.py` | Document extraction + chunking |
| `kb/indexer.py` | Resumable background indexing |
| `kb/retrieval.py` | Hybrid retrieval orchestration (BM25 + dense + rerank) |
| `kb/bm25.py` | BM25 lexical search implementation |
| `kb/embeddings.py` | Dense vector embedding (fastembed ONNX) |
| `kb/vector_store.py` | Vector storage and similarity search |
| `kb/reranker.py` | Cross-encoder reranking (ms-marco-MiniLM) |
| `kb/contextual.py` | Contextual chunking and relevance scoring |
| `kb/ocr.py` | Scanned PDF OCR pipeline (RapidOCR + PyMuPDF) |
| `kb/bundle.py` | Combined PDF + KB chunk bundle output |
| `kb/legacy_docs.py` | Legacy format extraction (.doc .ppt .msg .odt) |
| `kb/multimedia.py` | Audio/video transcription (faster-whisper) |
| `kb/model_bundle.py` | Offline model cache management |

### src/testgen/ - Test Case Generation: RLM, Types, Excel I/O, Templates, Cache

| File | Role |
| ---- | ---- |
| `testgen/__init__.py` | Package init and public exports |
| `testgen/rlm.py` | Recursive Language Model (navigate/map/reduce) |
| `testgen/tc_types.py` | Test case data structures and validation |
| `testgen/testcase_excel.py` | Test case Excel output generation |
| `testgen/testcase_template.py` | Client template analysis + rendering |
| `testgen/template_analyzer.py` | LLM-assisted template structure analysis |
| `testgen/gen_cache.py` | Generation result caching |

### src/tools/ - PDF Packaging, Office Conversion, Visio Conversion

| File | Role |
| ---- | ---- |
| `tools/__init__.py` | Package init and public exports |
| `tools/pdf_packager.py` | Per-WI PDF packaging (cover + attachments) |
| `tools/combine_pdf.py` | Combined PDF merging |
| `tools/office_convert.py` | Office -> PDF conversion (pure Python) |
| `tools/visio_convert.py` | Visio -> PDF conversion |

### src/defects/ - Bulk Defect Upload: Parsing, Review, ADO Upload

| File | Role |
| ---- | ---- |
| `defects/__init__.py` | Package init |
| `defects/parser.py` | Defect document parsing (programmatic + LLM fallback) |
| `defects/review_excel.py` | Review Excel generation and read-back |
| `defects/ado_uploader.py` | Bug work item creation in ADO |
| `ui/defect_dialog.py` | Bulk defect upload dialog (Select > Parse > Upload) |

### src/tests/

| File | Role |
| ---- | ---- |
| `tests/generate_test_data.py` | Generates 50+ synthetic test fixtures |
| `tests/test_full_e2e.py` | Comprehensive 57-check E2E test suite |
