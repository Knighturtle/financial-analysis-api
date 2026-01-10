# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0] - 2026-01-10

### Added

- **Web UI**: Interactive dashboard at `http://localhost:8000/`.
- **Strict Environment Checks**: Server checks for `OPENAI_API_KEY` on startup.
- **Async Support**: Optimized API for non-blocking operations.
- **Robust Verification**: `verify.ps1` and `verify_live.py` for CI/CD readiness.
- **Fallback Logic**: Graceful handling of OpenAI Quota limits (429).
- **Documentation**: Comprehensive `README.md` and `implementation_notes.md`.

### Changed

- Replaced legacy PowerShell scripts with standardized lifecycle management.
- Updated dependency management.
