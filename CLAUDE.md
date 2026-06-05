# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build System

FreeCAD uses CMake with [Pixi](https://pixi.sh) for dependency management (conda-based environments). The recommended workflow uses Pixi tasks:

```bash
# First-time setup (initializes git submodules)
pixi run initialize

# Configure → build → install (debug by default)
pixi run configure-debug
pixi run build-debug
pixi run install-debug

# Launch
pixi run freecad-debug          # Linux/macOS: build/debug/bin/FreeCAD
# Windows: .pixi/envs/default/Library/bin/FreeCAD.exe

# Release builds
pixi run configure-release
pixi run build-release
pixi run install-release
```

Direct CMake (within a pixi shell):
```bash
cmake --preset conda-linux-debug    # or conda-macos-debug / conda-windows-debug
cmake --build build/debug
cmake --install build/debug
```

Key CMake flags: `ENABLE_DEVELOPER_TESTS=ON` (required to compile C++ unit tests), `FREECAD_USE_CCACHE=ON` (default).

## Testing

```bash
# Run all CTest tests
pixi run test-debug
# or: ctest --test-dir build/debug

# Run a single named test
ctest --test-dir build/debug -R <TestName>

# FreeCAD Python self-tests (headless)
build/debug/bin/FreeCADCmd -t 0

# GUI Python tests
python3 .github/scripts/run_gui_tests.py build/release
```

C++ tests live in `tests/src/` mirroring the source layout (`tests/src/Base/`, `tests/src/App/`, `tests/src/Mod/Part/`, etc.). They use Google Test and require `ENABLE_DEVELOPER_TESTS=ON` at configure time.

## Code Style

**C++**: Enforced by `.clang-format` (LLVM-based, 4-space indent, 100-char column limit, braces always on new lines for classes/functions/namespaces). Run `clang-format -i <file>` before committing.

**Python**: Black (line length 100) via pre-commit. Run `black --line-length 100 <file>`.

**Pre-commit hooks** (strongly recommended):
```bash
pre-commit install   # one-time setup
pre-commit run       # run on staged files
```

Hooks enforce: trailing whitespace, clang-format, Black, and version file consistency.

## Architecture

FreeCAD has a layered core with independent workbenches:

```
Base   →   App   →   Gui
```

- **`src/Base/`**: Fundamental utilities — math (Matrix, Placement, Rotation), parameter/config system, threading, XML I/O, exceptions. No dependencies on App or Gui.
- **`src/App/`**: Non-GUI application layer — Document/DocumentObject model, property system, expression engine, recompute graph. Depends on Base.
- **`src/Gui/`**: Qt + Coin3D UI — MDI views, command system, 3D viewer (using Coin3D/Open Inventor), preferences. Depends on App.
- **`src/Mod/`**: ~28 workbenches that extend App and/or Gui. Each workbench is independent and can be C++, Python, or mixed.

**Key technology stack:**
- Geometry kernel: OpenCASCADE (OCCT) — used heavily in `src/Mod/Part/` and PartDesign
- 3D rendering: Coin3D (Open Inventor) — scene graph in `src/Gui/`
- Python bindings: PyBind11 and Shiboken (PySide6)
- Signals: `fastsignals` library (not Qt signals in core)
- GUI: Qt 6 (PySide6 for Python side)

**Document/Object model**: Everything is a `DocumentObject` inside a `Document`. Objects have typed `Property` fields (PropertyFloat, PropertyString, PropertyLink, etc.). The `App::Document` manages a DAG of objects and drives recomputes when properties change.

**Workbench structure** (e.g., `src/Mod/Part/`):
- `App/` — C++ DocumentObjects, geometry features
- `Gui/` — ViewProviders, commands, panels
- `*.py` / `Init.py` — Python-side registration and scripting API

**Module registration**: Each module has `Init.py` (always loaded) and `InitGui.py` (loaded only in GUI mode). C++ modules export an `init<ModuleName>()` function called at startup.

## Key Workbenches

| Workbench | Path | Purpose |
|-----------|------|---------|
| Part | `src/Mod/Part/` | OCCT-based geometry primitives and Boolean ops |
| PartDesign | `src/Mod/PartDesign/` | Parametric feature-based solid modeling |
| Sketcher | `src/Mod/Sketcher/` | 2D constraint solver for profiles |
| Assembly | `src/Mod/Assembly/` | Assembly constraints and joints |
| BIM | `src/Mod/BIM/` | Building/architecture tools (IFC) |
| Fem | `src/Mod/Fem/` | Finite element analysis |
| TechDraw | `src/Mod/TechDraw/` | 2D technical drawing output |
| CAM | `src/Mod/CAM/` | CNC toolpath generation |
| Spreadsheet | `src/Mod/Spreadsheet/` | Spreadsheet for parametric values |
| Draft | `src/Mod/Draft/` | 2D drafting and annotation |

## Contribution Requirements

- Each PR MUST address exactly one problem and compile cleanly on all platforms.
- Each commit in a PR must compile independently when merged with prior commits.
- Python API breaking changes must be minimized and clearly documented in the PR.
- If the PR changes UI, the PR body must include before/after screenshots.
- Raw AI-generated code is not accepted; AI may assist but the contributor must author and validate all changes.
- Add yourself to `src/Doc/CONTRIBUTORS` in a separate single-commit PR if desired.
