# Development Guide

Welcome to the BioPro Flow Cytometry plugin development guide! This document outlines the setup, testing, and continuous integration workflows for contributors.

## 1. Prerequisites

This plugin is designed to run inside the **BioPro Framework**. Therefore, you need the `biopro-sdk` installed.

- **Python Version**: 3.11 or higher
- **Package Manager**: `uv` is recommended for fast installation, but standard `pip` works.

## 2. Local Environment Setup

### SDK Dependency
Currently, the plugin expects the BioPro SDK to be available as a sibling directory in development, or installed in your Python environment.

Clone the SDK (if available) next to this repository:
```bash
cd ..
git clone <biopro-sdk-repo-url> BioPro-SDK
cd BioPro-flow-cytometry
```

### Installation
Create a virtual environment and install the package with developer dependencies:

```bash
uv venv
source .venv/bin/activate

# Install the BioPro SDK locally
uv pip install -e ../BioPro-SDK

# Install the flow cytometry plugin dependencies
uv pip install -r requirements-dev.txt
```

## 3. Pre-commit Hooks

We use `pre-commit` to enforce code formatting and linting (via `ruff`) before every commit.

To install the hooks:
```bash
pre-commit install
```

## 4. Testing

The repository uses `pytest` with various markers to separate tests.

Run all tests:
```bash
pytest tests/ -v
```

Run only unit tests:
```bash
pytest tests/unit/ -v
```

Run functional and integration tests:
```bash
pytest tests/functional/ tests/integration/ -v
```

*Note: UI Integration tests may require an X11 server or offscreen rendering. On Linux/CI, set `QT_QPA_PLATFORM=offscreen`.*

## 5. Continuous Integration (CI)

Our CI pipeline (defined in `.github/workflows/ci.yml`) runs automatically on PRs and pushes to `main`/`develop`.

The CI pipeline performs:
1. **Linting**: Runs `ruff check` on all Python files.
2. **Testing**: Runs the test suite under Python 3.11 using an offscreen Qt plugin.

Because the CI pipeline relies on the `BioPro-SDK`, ensure that any structural API changes are coordinated with the SDK maintainers.

## 6. Code Style Guidelines

- **Formatting**: We use `ruff` to enforce PEP-8 compliance. A line length of `120` is allowed.
- **Error Handling**: Do not use bare `except Exception:` blocks unless at the absolute top-level of a UI event loop. Always catch specific exceptions (`ValueError`, `KeyError`, `OSError`, etc.) to prevent masking bugs.
- **Architecture**:
  - `analysis/`: Must NEVER import from `PyQt6` or `ui/`.
  - `ui/`: Should be as thin as possible, delegating business logic to `analysis/`.
