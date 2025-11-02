[README_calciumImgTAU.md](https://github.com/user-attachments/files/23291037/README_calciumImgTAU.md)
# calciumImgTAU — Minimal Calcium-Imaging Processing Pipeline

> **calciumImgTAU** is a small pipeline for processing calcium-imaging time‑series from CSV/XLSX files and interactively visualizing the results in a web UI.
> The pipeline loads a matrix of `frames × ROIs`, optionally drops leading frames, applies optional detrending and smoothing, computes a baseline (F0) using several strategies,
> derives either `ΔF/F` or simple `F − F0`, and exposes the results to a browser client for live plotting and CSV export.

---

## Table of Contents

- [Overview](#overview)
- [Repository Layout](#repository-layout)
- [High-Level Architecture](#high-level-architecture)
- [Pipeline Components & Classes](#pipeline-components--classes)
- [Installation](#installation)
- [How to Run](#how-to-run)
  - [Option A — Command Line](#option-a--command-line)
  - [Option B — FastAPI Service (RESTful)](#option-b--fastapi-service-restful)
  - [Option C — Web UI (Frontend)](#option-c--web-ui-frontend)
- [Input & Output](#input--output)
- [Configuration Parameters](#configuration-parameters)
- [Examples](#examples)
- [Development Notes](#development-notes)
- [License](#license)

---

## Overview

`calciumImgTAU` focuses on a lean, reproducible pipeline for calcium‑imaging signals where each ROI’s fluorescence trace is treated as a 1‑D time series. The pipeline emphasizes:

- **Simple I/O**: CSV/XLSX import with headers; convenient CSV export of processed traces.
- **Composable processing**: frame‑dropping → baseline estimation (F0) → detrending  → normalization (`ΔF/F` or `F − F0`) → smoothing.
- **Interactive viz**: a lightweight FastAPI backend feeds a browser client for live plotting and parameter tweaks.
- **Scriptable**: a `run_pipeline.py` entrypoint enables batch runs from the command line.

---

## Repository Layout

```
calciumImgTAU/
├─ pipeline/                 # Core pipeline logic (processing modules & utilities)
├─ api.py                    # FastAPI application (service bootstrap, routes mounting)
├─ pipeline_api.py           # API-layer glue that invokes the pipeline
├─ schemas.py                # Pydantic models (request/response & config schemas)
├─ run_pipeline.py           # CLI entrypoint to run the pipeline on local files
├─ frontend/                 # Optional web UI (static assets or SPA)
└─ .gitignore, venv/, etc.
```

> Note: Exact file/class names may evolve. Check the repo for the latest structure.

---

## High-Level Architecture

```
                              ┌─────────────────────────────── API path ────────────────────────────────┐
Browser UI / Client ── HTTP (multipart/JSON) ──► FastAPI (api.py) ──► pipeline_api ──► run_pipeline()
                                                                        │
                                                                        ▼
                    └──────────────────────────── (invokes pipeline steps below) ─────────────┘


┌────────────────────────────────────────── Data path (exact order) ──────────────────────────────────────────┐
│  CSV/XLSX                                                                                                   │
│     │                                                                                                       │
│  ┌──▼────────────┐                                                                                          │
│  │ SignalLoader  │  (load, numeric sanitize, drop_first)                                                    │
│  └───┬───────────┘                                                                                          │
│      │                                                                                                      │
│  ┌───▼────────────────┐    ┌──────────────┐    ┌──────────────┐    ┌────────────────┐    ┌───────────────┐ │
│  │ BaselineComputer   │ →→ │   Detrender  │ →→ │  Normalizer   │ →→ │  FilterApplier │ →→ │  SignalSaver  │ │
│  │ compute F0         │    │ remove drift │    │ ΔF/F or F−F₀  │    │ smooth signal  │    │  Excel output │ │
│  └─────────┬──────────┘    └──────────────┘    └──────────────┘    └────────────────┘    └─────────┬─────┘ │
│            │                                                                                             │  │
│            │                                      (optional)                                             │  │
│            └──────────────────────────────────────► SignalPlotter ───► PNG plots per ROI                 │  │
└───────────────────────────────────────────────────────────────────────────────────────────────────────────┘

```

- **Core processing** lives under `pipeline/` and is designed as small, testable units.
- **Service layer** (`api.py`, `pipeline_api.py`, `schemas.py`) wraps the pipeline behind a minimal RESTful API.
- **Frontend** (optional) consumes the API for interactive plotting and exporting.

---

## Pipeline Components

Each component in the pipeline is implemented as a standalone class.
Together, they form the processing flow executed by `run_pipeline.py`:

```
SignalLoader → BaselineComputer → Detrender → Normalizer → FilterApplier → SignalSaver → SignalPlotter
```

---

### **1. SignalLoader**

**Purpose:**
Loads calcium-imaging signals from CSV/XLSX files, coerces values to numeric, removes empty rows, assigns column names (`ROI_1`, `ROI_2`, …), and optionally drops the first N frames (`drop_first`).

**Input:**

* `filepath` — path to CSV/XLSX file
* `sheet` — sheet index or name (for Excel files)
* `drop_first` — number of initial frames to skip

**Output:**

* `pd.DataFrame` of shape `(frames × ROIs)` with columns `ROI_i`

**Key Parameters:**

* `drop_first` must be less than the number of frames, otherwise an exception is raised.

**Recommendations:**

* Use numeric-only data; text cells are converted to NaN and dropped.
* Avoid excessive `drop_first` values.
* Include a headerless matrix — the loader automatically assigns ROI names.

---

### **2. BaselineComputer**

**Purpose:**
Computes the baseline fluorescence `F₀` using one of several strategies:

* `pre_stim_median`
* `global_median`
* `global_percentile`
* `rolling_median`
* `rolling_percentile`
* `rolling_mean`

**Input:**

* `df`: raw fluorescence DataFrame
* Configurable parameters:
  `mode`, `stim_frame`, `pre_window`, `rolling_window`,
  `global_percentile_q`, `rolling_percentile_q`, `roll_min_frac`

**Output:**

* `F0_df`: DataFrame (baseline per frame)
* `f0_vec`: Series (representative baseline per ROI)

**Key Parameters:**

* `stim_frame` must be valid for `pre_stim_median`.
* `rolling_window` and `pre_window` must be ≥ 3.

**Recommendations:**

* For stimulation-locked experiments, use `pre_stim_median` with a well-defined `stim_frame`.
* For noisy or nonstationary data, use `rolling_percentile` with low `q` (e.g. 10%).
* Make sure `rolling_window` matches your sampling rate and expected drift duration.

---

### **3. Detrender**

**Purpose:**
Removes slow trends or drift from the fluorescence trace.
Supported methods:

* `none` (skip detrending)
* `linear` (linear regression per ROI)
* `rolling_median` (subtracts rolling median)

**Input:**

* `df`: raw or baseline-aligned DataFrame
* `method`: detrending method
* `rolling_window`: window size (for `rolling_median`)

**Output:**

* Detrended `pd.DataFrame`

**Key Parameters:**

* For `rolling_median`, `rolling_window` must be odd and ≥ 5.

**Recommendations:**

* Start with `none` and inspect the trend visually.
* Use `rolling_median` for fluorescence data with slow baseline drift.
* `linear` detrending is suitable for near-linear drifts.

---

### **4. Normalizer**

**Purpose:**
Performs fluorescence normalization:

* **Subtraction:** `(F − F₀)`
* **Delta-F over F:** `(F − F₀) / F₀`
  Includes robust epsilon handling to avoid division by zero.

**Input:**

* `df`: detrended fluorescence DataFrame
* `baseline`: baseline (`DataFrame`, `Series`, or scalar)

**Output:**

* Normalized `pd.DataFrame`

**Key Parameters:**

* `eps` (default `1e-12`): minimum baseline magnitude
* `as_percent`: multiply by 100 if `True`
* `clip_negatives`: clip values below 0
* `fillna_value`: replace NaN/Inf (default `0.0`)

**Recommendations:**

* Use `eps` between `1e-6`–`1e-9` for stable results.
* Set `clip_negatives=True` if required by downstream analysis.
* For publication plots, consider `as_percent=True` for readability.

---

### **5. FilterApplier**

**Purpose:**
Applies smoothing filters column-wise after normalization:

* `savgol` (Savitzky–Golay, requires SciPy)
* `gaussian` (SciPy or NumPy fallback)

Handles NaNs gracefully by filling temporarily, then restoring them.

**Input:**

* Normalized `pd.DataFrame`
* Parameters:
  `method`, `gaussian_sigma`, `gauss_boundary`,
  `savgol_window`, `savgol_poly`

**Output:**

* Smoothed `pd.DataFrame`

**Key Parameters:**

* Savitzky–Golay: `window` must be odd and > `polyorder + 1`.
* Gaussian: `sigma > 0`, `boundary` mode (`reflect`, `nearest`, `mirror`, `wrap`).

**Recommendations:**

* Start with `savgol_window=21–31` and `poly=3`.
* Use Gaussian (`σ≈1.5–2.5`) for very noisy signals.
* Always smooth **after** normalization to avoid bias in F₀.

---

### **6. SignalSaver**

**Purpose:**
Exports processed results to an Excel file (`.xlsx`), creating folders automatically.

**Input:**

* `df`: processed data (ΔF/F or F−F₀)
* `sheet_name`
* `output_path`

**Output:**

* Excel file on disk

**Recommendations:**

* Save configuration metadata alongside results for reproducibility.
* Use platform-independent paths (`pathlib.Path`).
* Store both ΔF/F and F−F₀ for flexibility in downstream plotting.

---

### **7. SignalPlotter**

**Purpose:**
Generates visualizations for each ROI, showing:

1. Raw trace (RAW)
2. Baseline-subtracted signal (F − F₀)
3. ΔF/F
   Adds a vertical dashed line at the stimulus frame.

**Input:**

* `roi_name`, `raw_df`, `sub_df`, `dff_df`,
  `title_suffix`, `f0_repr`, `stim_frame`, `save_dir`

**Output:**

* PNG file per ROI (if `save_dir` provided)
* or on-screen plots (when run locally)

**Recommendations:**

* Match plot titles to the chosen normalization mode (`dff` vs `subtract`).
* Prefer file export (`save_dir`) for large datasets.
* Include `stim_frame` to visually align responses.

---

### **Execution Order in `run_pipeline.py`**

```
SignalLoader
 → BaselineComputer
 → Detrender
 → Normalizer
 → FilterApplier
 → SignalSaver
 → SignalPlotter
```

Each step’s output is passed to the next, forming a reproducible and modular workflow.
The API layer (`api.py` and `pipeline_api.py`) simply wraps this flow behind FastAPI endpoints, allowing web-based interaction and live visualization.


**Service Layer**

- **`api.py`** — boots a FastAPI app, mounts routes, and serves `/docs` (Swagger) & `/redoc` UIs.
- **`pipeline_api.py`** — binds HTTP requests to pipeline calls, translates `schemas.py` models into `PipelineConfig`.
- **`schemas.py`** — Pydantic models for request/response payloads:
  - `ProcessRequest` (parameters + file handle)
  - `ProcessResponse` (processed traces, F0, metadata)
  - `MethodsResponse` (available options for detrend/smooth/baseline)

---

## Installation

> Requires **Python 3.10+** (recommended).

```bash
# 1) Clone
git clone https://github.com/AnnaOrSol/calciumImgTAU.git
cd calciumImgTAU

# 2) Create & activate a virtualenv
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

# 3) Install dependencies
pip install --upgrade pip
pip install fastapi uvicorn pandas numpy scipy matplotlib openpyxl pydantic python-multipart
# If you plan to use optional features:
# pip install scikit-image
```

> If a `requirements.txt` is added later, you can simply `pip install -r requirements.txt`.

---

## How to Run

### Option A — Command Line

Batch‑process a file without starting a server.

```bash
python run_pipeline.py   --input path/to/data.csv   --drop-leading-frames 10   --detrend rolling_median --detrend-window 101   --smooth savgol --smooth-window 21 --polyorder 3   --baseline percentile --percentile 20 --baseline-window 201   --metric dff   --export-csv out/processed.csv   --save-plots out/plots/
```

Typical flags (names may vary in code):
- `--input`: CSV/XLSX file (ROIs in columns)
- `--drop-leading-frames N`
- `--detrend [none|linear|poly|rolling_median|savgol_hp]` (+ window/order args)
- `--smooth [none|savgol|boxcar|gaussian]` (+ window/order/sigma)
- `--baseline [percentile|rolling_quantile|fixed_window|min]` (+ method‑specific args)
- `--metric [dff|ff0]`
- `--export-csv PATH`
- `--save-plots DIR`

### Option B — FastAPI Service (RESTful)

Run the API and open interactive docs.

```bash
uvicorn api:app --reload --port 8000
# Then open http://localhost:8000/docs  (Swagger UI)
```

Common endpoints (names can differ slightly):
- `POST /process` — multipart file + JSON params → returns processed traces (+ optional CSV)
- `GET  /methods` — lists available detrend/smooth/baseline strategies and defaults
- `GET  /health` — basic health check

> The OpenAPI docs at `/docs` show exact schemas generated from `schemas.py`.

### Option C — Web UI (Frontend)

If `frontend/` is provided, it usually expects the FastAPI service at `http://localhost:8000`:

```bash
# from frontend/
# If this is a simple static build, serve locally; otherwise follow its README.
# Example (Python simple server):
python -m http.server 5173
# Then open http://localhost:5173
```

---

## Input & Output

**Input**

- CSV/XLSX with ROIs as columns; header row required.
- Optional first column for frame/time index (auto‑generated if missing).

**Output**

- **Processed matrix**: `frames × ROIs` after normalization (`ΔF/F` or `F − F0`).
- **F0 table**: baseline per ROI (and optional diagnostics).
- **CSV export**: saved if `--export-csv` is provided or via API param.
- **Plots**: per‑ROI and/or overlay, if `--save-plots` (or API flag) is set.

---

## Configuration Parameters

Key knobs you can tune (mirrored in CLI args and API schemas):

- `drop_leading_frames: int`
- `detrend: {none|linear|poly|rolling_median|savgol_hp}` with window/order/pad options
- `smooth: {none|savgol|boxcar|gaussian}` with window/order/sigma
- `baseline.method: {percentile|rolling_quantile|fixed_window|min}` with `window`, `percentile`, `range`
- `metric: {dff|ff0}` with `epsilon`
- `roi_filter: {method: mad|std, threshold: float}`
- `export: {csv_path: str, plots_dir: str}`
- `viz: {limit_rois, overlay, figsize}`

---

## Examples

**1) Minimal ΔF/F from CSV**

```bash
python run_pipeline.py --input data.csv --metric dff --export-csv out.csv
```

**2) Fixed-window baseline (pre-stim frames 0–200), smoothing & plots**

```bash
python run_pipeline.py   --input data.xlsx   --baseline fixed_window --baseline-range 0 200   --smooth savgol --smooth-window 25 --polyorder 3   --save-plots out/plots/
```

**3) REST call (curl)**

```bash
curl -X POST "http://localhost:8000/process"   -F "file=@data.csv"   -F 'params={
        "drop_leading_frames": 10,
        "detrend": {"name":"rolling_median","window":101},
        "baseline": {"name":"percentile","percentile":20,"window":201},
        "metric": "dff",
        "export_csv": true
      }'
```

> Inspect `/docs` for the exact field names your build expects.

---

## Development Notes

- Prefer odd `window_length` for Savitzky–Golay.
- Ensure `window_length > polyorder`.
- When `F0` can be ~0, set a small `epsilon` (e.g., `1e-6`) before division.
- Keep processing stateless; pass a config object to `Pipeline.run()`.

---

## License

TBD (add your preferred license).

---

**Maintainer**: Anna Solodohin
**Feedback & Issues**: please open a GitHub Issue or PR.
