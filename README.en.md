<div align="center">

<h1>hitran-mcp</h1>

<p><b>An AI toolchain for the HITRAN spectroscopic database: MCP server + HitranLab desktop workstation</b><br>
Retrieval · spectral calculation · plotting · provenance in one pipeline. Data is fetched live from HITRANonline via the official HAPI; the repository ships no data files.</p>

<a href="LICENSE"><img src="https://img.shields.io/badge/License-GPLv3-blue.svg" alt="GPLv3"></a>
<a href="https://github.com/LKF0402/hitran-mcp/releases/latest"><img src="https://img.shields.io/github/v/release/LKF0402/hitran-mcp?color=6B8FD4" alt="Release"></a>
<a href="https://github.com/LKF0402/hitran-mcp/releases"><img src="https://img.shields.io/github/downloads/LKF0402/hitran-mcp/total" alt="Downloads"></a>
<img src="https://img.shields.io/badge/Platform-Windows%20x64-0078D6" alt="Platform">
<img src="https://img.shields.io/badge/Python-3.10%2B-3776AB" alt="Python">
<img src="https://img.shields.io/badge/MCP-stdio%20JSON--RPC-6B8FD4" alt="MCP">
<img src="https://img.shields.io/badge/Data-HITRAN2024-red" alt="HITRAN2024">
<a href="https://github.com/LKF0402/hitran-mcp/stargazers"><img src="https://img.shields.io/github/stars/LKF0402/hitran-mcp?color=yellow" alt="Stars"></a>
<a href="https://github.com/LKF0402/hitran-mcp/issues"><img src="https://img.shields.io/github/issues/LKF0402/hitran-mcp" alt="Issues"></a>
<img src="https://img.shields.io/github/commit-activity/m/LKF0402/hitran-mcp" alt="Commit Activity">
[![CI](https://github.com/LKF0402/hitran-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/LKF0402/hitran-mcp/actions/workflows/ci.yml)

</div>

[English](./README.en.md) | [中文](./README.md)

## Preview

**HitranLab desktop workstation** — CH4 + H2O mixture absorption spectrum (CH4 2000 ppm, H2O 1%, 296 K, 1 atm):

![HitranLab main window](docs/images/hitranlab.png)

**Cross-section online search & one-click download** — fuzzy match by name, tick the T/P cases, download in batch:

![Cross-section download window](docs/images/xsc-download.png)

## Table of Contents

- [Preview](#preview)
- [Overview](#overview)
- [Features](#features)
- [Repository Layout](#repository-layout)
- [HitranLab Desktop Workstation](#hitranlab-desktop-workstation)
  - [Download & Run](#download--run)
  - [Features](#features-1)
  - [Build from Source / Release](#build-from-source--release)
- [Quick Start (MCP Server)](#quick-start-mcp-server)
  - [Requirements](#requirements)
  - [Installation](#installation)
  - [API Key (Optional)](#api-key-optional)
- [MCP Client Setup](#mcp-client-setup)
- [Tool Reference](#tool-reference)
- [Data Architecture & Molecular Coverage](#data-architecture--molecular-coverage)
  - [Line-By-Line (LBL) Database](#line-by-line-lbl-database)
  - [Cross-Section (XSC) Database](#cross-section-xsc-database)
  - [Bridging the Two Channels](#bridging-the-two-channels)
- [Usage Conventions](#usage-conventions)
- [Self-Test](#self-test)
- [FAQ](#faq)

## Overview

`hitran-mcp` is a complete toolchain for the HITRAN spectroscopic database, featuring two frontends:

1. **MCP Server** (`tools/hitran_mcp.py`): stdio JSON-RPC implementation, exposing 12 tools for AI clients to perform retrieval, spectral computation, plotting, and cross-section file discovery/download.
2. **HitranLab Desktop Workstation** (`app/hitran_app.py`): Tkinter + matplotlib GUI for multi-component absorption spectrum computation, overlay plotting, strong-line analysis, partition sum queries, CSV/PNG export, and more — no programming required.

Both frontends share the same physical computation engine (`tools/hitran.py`), ensuring fully consistent results.

- **Transport**: MCP server uses stdio JSON-RPC (protocol 2024-11-05), pure Python standard library, no framework dependency.
- **Data source**: fetched live from HITRANonline. The computation layer uses the official HAPI 1.3.0.0; downloads go through the official v2 API first (HAPI2, API key in URL) and fall back to the HAPI 1.x legacy endpoint automatically. The species table and isotope abundances are read from the HAPI official ISO table — no hard-coded whitelist.
- **Coverage**: MCP server has 12 tools spanning both HITRAN2024 databases (line-by-line + cross-section); desktop workstation covers the full daily spectral analysis workflow.
- **Repository boundary**: code and documentation only. Line-table caches (`Hitran_Data/`), outputs (`tmp/`), user-downloaded cross-section data (`xsc_data/`), build artifacts (`dist/`/`build/`) and API keys are all runtime artifacts under `.gitignore` — never committed.

## Features

| Feature | Description |
|---|---|
| Full pipeline | Species lookup → line-table fetch → strong-line list → absorption/transmittance spectrum → plot → partition sum → cross-section analysis |
| Dual-database bridge | LBL via HAPI online API; XSC (600+ heavy molecules) via official-API discovery + one-click download (no Portal login), or local file ingestion — unified output pipeline |
| Physical safeguards | Mixtures computed as `α_i = x_i · α_pure_i(T, P, bath)`; windows not covered are auto-refetched; zero-line/failure raise explicit errors instead of silently returning a flat spectrum |
| Full provenance | Every CSV/PNG carries HITRAN2024 + HAPI + TIPS version watermarks, traceable to the original references |
| Computation cache | Results for identical parameters are automatically cached (200-entry cap, LRU eviction); repeated computations return instantly |
| Desktop GUI | HitranLab workstation: multi-component overlay plotting, layer management, strong-line list (with molecule source labels), Q(T) curves, wavelength↔wavenumber converter, cross-section search & download, CSV/PNG export |
| Data-free repository | Caches, outputs, personal cross-section files and build artifacts are gitignored — the repo stays lightweight |

## Repository Layout

```
hitran-mcp/
├─ README.md                 # Chinese documentation
├─ README.en.md              # English documentation (this file)
├─ docs/images/              # README screenshots
├─ CHANGELOG.md              # Changelog
├─ LICENSE                   # GPLv3 License
├─ requirements.txt          # Python dependencies
├─ mcp.config.example.json   # MCP client registration snippet (adjust paths)
├─ app/
│  ├─ hitran_app.py          # HitranLab desktop workstation (Tkinter + matplotlib GUI)
│  └─ hitranlab.ico          # Application icon
└─ tools/
   ├─ hitran_mcp.py          # MCP server (stdio JSON-RPC, pure stdlib)
   ├─ hitran.py              # Thin wrapper over official HAPI (guards + provenance + cache)
   └─ __init__.py
```

Generated at runtime (safe to delete; regenerated by the tools):

- `Hitran_Data/` — line-table cache
- `tmp/mcp_out/` — MCP tool outputs (CSV/PNG with provenance watermark)
- `tmp/` — desktop workstation temp files and self-test outputs
- `xsc_data/` — cross-section files downloaded on demand (personal data, not committed)
- `dist/` / `build/` — PyInstaller build artifacts (not committed)

## HitranLab Desktop Workstation

HitranLab is a no-programming-required desktop application for spectral analysis, suitable for daily research use.

### Download & Run

**Option 1: Download pre-built release (recommended)**

1. Go to [GitHub Releases](https://github.com/LKF0402/hitran-mcp/releases) and download the latest `HitranLab-windows-x64.zip`
2. Extract to any directory (paths without Chinese characters or spaces are recommended)
3. Double-click `HitranLab.exe` to run

> On first run, a `Hitran_Data/` cache directory is automatically created in the same folder as the executable. Computed line tables are cached automatically — no need to re-download next time.

**Option 2: Run from source**

```bash
git clone https://github.com/LKF0402/hitran-mcp.git
cd hitran-mcp
pip install -r requirements.txt
python app/hitran_app.py
```

### Features

| Module | Description |
|---|---|
| Spectrum computation | Four output modes: absorption coefficient α, cross-section σ, line strength S(296K), transmittance T |
| Multi-component overlay | Overlay plotting by default; multiple molecules/conditions can be overlaid on the same canvas; individual layers can be deleted |
| Strong-line list | Shows the top N strongest lines in the window (ν, S, γ_air, E″); with multiple molecules, each line is labeled with its source molecule |
| Q(T) curve | Partition sum vs. temperature curve, for evaluating temperature effects on line strength |
| Partition sum | Query Q(T) at a specified temperature (TIPS-2025) |
| Cross-section file | Search XSC molecules by Chinese name/formula and download in one click (no Portal login); read native `.xsc` / two-column `.txt`, plot and export provenance CSV |
| Unit converter | Real-time wavelength ↔ wavenumber converter |
| Species table | Query the official HITRAN table of 61 line-by-line molecules |
| Data export | Spectrum PNG (300 DPI), spectrum data CSV (with provenance watermark), complete line-list CSV |
| Computation cache | Results for identical parameters are cached automatically; repeated computations return instantly |

**Workflow**:
1. Select molecule(s) (multi-component mixture supported), wavenumber window, temperature, pressure, step
2. Select output mode (absorption / cross-section / line strength / transmittance)
3. Click「Compute & Plot」
4. Adjust parameters and compute again — spectra are automatically overlaid on the same canvas
5. Click「Clear Plot」to reset the canvas; click「Export CSV/PNG」to save results

### Build from Source / Release

**Use the one-click release script** — it binds "build the exe" and "produce the zip asset" into a single step with a consistency check:

```bash
pip install pyinstaller
python tools/build_release.py
```

The script performs, in order:

1. Build the exe from `HitranLab.spec` (HAPI2 / sqlalchemy / numba / llvmlite / pyparsing included);
2. Replace `dist/HitranLab/` (**keeping** the exe-side line-table cache and `hitran_api_key.txt`);
3. Run a headless self-test on the packaged build (molecule count / spectrum points / peak / download engine);
4. Generate the GitHub release asset `dist/HitranLab-windows-x64.zip`;
5. **Verify that the exe inside the zip matches `dist/HitranLab/HitranLab.exe` in size and CRC32**
   — mismatches abort with an error, so "stale zip with a new exe" can no longer happen.

Optional flags:

```bash
python tools/build_release.py --zip-only      # rebuild the zip only (reuse existing dist)
python tools/build_release.py --no-selftest   # skip the post-build self-test
```

The build directory is ~245 MB (one-dir mode, HAPI2 / numba / llvmlite included); the compressed zip is ~100 MB. Upload the zip from step 4 as the release asset.

> Close all running HitranLab windows before building, otherwise file locking will fail the build (the script reports this clearly).
>
> **Do not hand-write `pyinstaller` commands**: `HitranLab.spec` includes required dependencies
> (HAPI2 / sqlalchemy / numba / llvmlite / pyparsing) that hand-written flags easily miss,
> breaking HAPI2 in the packaged build.

## Quick Start (MCP Server)

### Requirements

- Python ≥ 3.10
- Dependencies: `hitran-api` (official HAPI), `numpy`, `matplotlib` (lazy-loaded for computation/plotting)

### Installation

```bash
git clone https://github.com/LKF0402/hitran-mcp.git
pip install -r hitran-mcp/requirements.txt
```

Or place the repository at any fixed path (the rest of this document uses `D:\hitran-mcp\` as an example).

### API Key (Optional)

Register at [hitran.org](https://hitran.org) to get an API key. Write it to `tools/hitran_api_key.txt` (same directory as `hitran_mcp.py`), or set the environment variable `HITRAN_API_KEY`.

> Note: with a key configured, line-table downloads go through the HITRAN official v2 API (key in URL), and the cross-section file listing (`/api/v2/<key>/cross-sections`) and downloads need it too; without a key, the tool falls back to the HAPI 1.x legacy endpoint (which does not validate the key). HITRANonline enforces a daily quota on fetch; exceeding it returns 403. This tool automatically reuses cache and does not re-download.

## MCP Client Setup

Any MCP-compatible client works. Merge the contents of `mcp.config.example.json` into your client configuration (usually in Settings → MCP/Tools), and **replace with your actual path**:

```json
"hitran": {
  "command": "python",
  "args": ["D:/hitran-mcp/tools/hitran_mcp.py"],
  "type": "stdio",
  "timeout": 600000,
  "disabled": false
}
```

> On Windows, if `python` is not in PATH, use the full path to the interpreter (forward slashes or double backslashes both work).

Save and restart the client. You should see the `hitran` server with 12 tools — that means it's connected.


## Tool Reference

| Tool | Purpose | Key Inputs |
|---|---|---|
| `hitran_species` | Official species table: molecule number M, main isotope, natural abundance and mass of each isotope | `name` (formula or M number; omit for full table) |
| `hitran_fetch` | Fetch line table for a wavenumber window to local cache; windows not covered are auto-refetched | `name`, `numin`, `numax`, `iso` |
| `hitran_lines` | Top N strongest lines in window (ν, S, γ_air, E″) for line selection/interference analysis | `name`, `numin`, `numax`, `top_n` |
| `hitran_spectrum` | Absorption coefficient α / transmittance spectrum, CSV with provenance watermark; multi-species overlay via `specs_csv` | `specs_csv` or `name`; `numin`, `numax` required |
| `hitran_plot` | Spectrum PNG (multi-species overlay + total, `ylog` optional) | Same as `hitran_spectrum`, plus `title/ylog/dpi` |
| `hitran_partition_sum` | Partition sum Q(T), TIPS 2025/2021/2017/2011 selectable | `name` or `M`; `T` |
| `hitran_cross_section` | Read a local XSC file (native `.xsc` or ν–σ two columns) → window/plot/provenance CSV | `file_path` (omitting lists available files in `xsc_data/`) |
| `hitran_xsc_search` | Online probe of cross-section sub-database molecule file list (login-free, read-only, no filenames) | `name` (Portal display name) |
| `hitran_xsc_molecules` | XSC molecule search: fuzzy match on Chinese name/formula/English name/synonym, returns candidates and `id` (~670 molecules) | `query` (empty = all); `limit` |
| `hitran_xsc_files` | List **directly downloadable** files for an XSC molecule (T/P/wavenumber range/resolution/points/size/filename; needs API key) | `name` or `molecule_id`; `include_all` |
| `hitran_xsc_download` | Download selected files into `xsc_data/` (official API + public data path, no Portal login, default cap 300 MB) | `name`, `filenames`/`ids`; `dry_run`, `overwrite`, `max_total_mb` |
| `hitran_apikey_status` | Quick status check: API key / cache / outputs / cross-section files | — |

Multi-species overlay example (`specs_csv`, mutually exclusive with `name`):

```
hitran_spectrum(specs_csv="CH4:0.01,C2H6:1e-5", numin=2950, numax=3120, T=296, P=1.0)
```

## Data Architecture & Molecular Coverage

HITRAN2024 uses a **dual-database distribution architecture** — the two data channels have different access mechanisms. This is the root cause of "why can't I find molecule X in the line-by-line tools?"

### Line-By-Line (LBL) Database

- Covers **61 molecules** (H₂O / CO₂ / CH₄ / C₂H₆ / N₂O…) and 130+ isotopologues, with **per-transition line parameters** (ν, S, γ_air, E″…).
- Stored in the HITRANonline relational database, served via the official **HAPI** (HITRAN Application Programming Interface, Kochanov et al., JQSRT 177, 15–30, 2016) **online API** — corresponding to this MCP's `hitran_fetch / lines / spectrum / plot` channels: live retrieval, local caching, reproducible.

### Cross-Section (XSC) Database

- Covers **600+ heavy molecules** (alkanes, VOCs, refrigerants, etc.): mostly dense vibrational band structures lacking validated line-by-line parameters, distributed as **measured spectrum files** — native `.xsc` (one fixed-width header + a σ series, units cm²/molecule) or two-column ν–σ text (units cm⁻¹ / cm²·molecule⁻¹).
- Access mechanism: the official v2 API (`/api/v2/<key>/cross-sections`) provides the **file listing**, and the public data path `/data/xsec/` serves the **file bodies** — both directly reachable, **no Web Portal login required** (a local HITRAN API key is needed). HAPI 1.x only offers the `read_hotw()` local file reader.

### Bridging the Two Channels

- The line-by-line channel (per-transition parameters) and the cross-section channel (measured spectra) are two different data structures that HITRAN distributes separately; this tool merges them into one output pipeline.
- **One-click download (recommended, no Portal login)**:
  1. `hitran_xsc_molecules(query="propane")` finds the molecule and returns its `id` (Chinese name/formula/English name/synonym all supported);
  2. `hitran_xsc_files(molecule_id=<id>)` lists the directly downloadable files (T/P/wavenumber range/points/size);
  3. `hitran_xsc_download(name=..., filenames=[...])` downloads them into `xsc_data/` (gitignored, not committed; default cap 300 MB);
  4. `hitran_cross_section(file_path=...)` reads it in, performs windowing, plotting, and provenance CSV export, sharing the `tmp/mcp_out/` output pipeline with line-by-line spectra.
- **Manual download (when no API key)**: `hitran_xsc_search(name=...)` probes the list login-free → download from hitran.org/xsc into `xsc_data/` → read with `hitran_cross_section`.
- When line-by-line tools encounter a molecule covered by the cross-section database, the error message explicitly explains this architectural difference and the correct path.

## Usage Conventions

1. **Units**: Returns absorption coefficient α (cm⁻¹) by default; `hitran_units=true` returns cross-section σ (cm²/molecule, not scaled by mole fraction).
2. **Mixtures**: Computed as `α_i = x_i · α_pure_i(T, P, bath)`, not `x·P` as partial pressure; if concentration is not provided, pure gas is assumed with a confirmation prompt.
3. **Parameter clarification**: Missing parameters fall back to defaults that are honestly listed (when `needs_confirm=true`, the user must confirm T/P/window/concentration); `strict=true` raises an error if T/P is missing.
4. **Line profiles**: `profile` options: voigt (default) / lorentz / gauss / doppler / ht / sdvoigt — all call official HAPI profile functions directly.
5. **Provenance**: Every CSV/plot is traceable to HITRAN2024 (Gordon et al., JQSRT 2026, doi:10.1016/j.jqsrt.2026.109807) + HAPI (Kochanov et al., JQSRT 2016) + TIPS version; for paper citation, use the `citation` field in the response.
6. **Isotope convention**: Main isotope by default (pure gas weight 1.0); `iso="all"` weights by official natural abundance.

## Self-Test

**MCP server self-test**:

```bash
python tools/hitran_mcp.py --selftest
```

Runs a real network fetch of a small CO window and plots, plus cross-section pipeline (synthetic file), online probe and status check.

**Desktop workstation self-test**:

```bash
python app/hitran_app.py --selftest selftest.json
```

Verifies that the engine + data + network are fully usable in the packaged environment; outputs JSON with molecule count, spectrum point count, peak values, etc.

## FAQ

- **Fetch fails with "daily limit"**: Official daily quota exceeded — try again tomorrow. If cache is not deleted, most windows don't need re-fetching.
- **Code changes don't take effect**: Restart the AI client (MCP process starts with the client); desktop workstation requires restarting the program.
- **Clear cache**: Delete `Hitran_Data/*.data|*.header` — they will be auto-refetched when needed.
- **Can't find XSC molecules (e.g., propane C₃H₈)**: it belongs to the cross-section database, distributed separately from the line-by-line database. Use `hitran_xsc_molecules` to search → `hitran_xsc_files` to list → `hitran_xsc_download` to fetch in one click, then read with `hitran_cross_section`; without an API key, follow the [Bridging the Two Channels](#bridging-the-two-channels) workflow to download manually.
- **exe flagged by antivirus**: PyInstaller-packaged Python programs occasionally trigger false positives — add to trust list or run from source.


## Disclaimer

This software is provided "AS IS" without warranty of any kind. The author shall not be liable for any direct or indirect damages arising from the use of this software.

- This software is intended for research, educational, and learning purposes only. It does not constitute professional advice or product commitment.
- Spectral calculation results are based on the HITRAN database and HAPI library, which may have data update delays, calculation approximations, or errors.
- Users should independently verify the accuracy of calculation results. For critical applications, please refer to official data and professional software.
- The author does not guarantee that the software is defect-free, uninterrupted, or meets specific requirements.
- By using this software, you agree to assume all risks associated with its use.

## References

- https://github.com/hitranonline/hapi
- https://github.com/hitranonline/hapi2
- https://github.com/hitranonline/hapiest
- https://hitran.org

## License

This project is licensed under the **GNU General Public License v3.0 (GPLv3)**. See [LICENSE](LICENSE) for details.
