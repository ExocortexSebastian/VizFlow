# VizFlow - Claude Instructions

> Instructions for Claude to track progress and continue implementation

---

## Project Overview

**VizFlow** is a TB-scale data analysis and visualization library.
- Usage: `import vizflow as vf`
- Engine: Polars (lazy evaluation)
- Primary use case: Financial market data (alpha evaluation, post-trade analysis)

## Key Documents

| Document | Purpose |
|----------|---------|
| `docs/DESIGN.md` | API design, architecture, data flow |
| `docs/PLAN.md` | Implementation plan with phases and steps |
| `CLAUDE.md` | This file - progress tracking |

---

## Current Status

**Current Phase**: 2 - Core Operations (COMPLETE)
**Current Version**: 0.3.0 (published to PyPI)
**Last Completed Step**: 2.7 - Published v0.3.0 to PyPI

---

## Progress Tracker

### Phase 0: Project Scaffolding [COMPLETE]
- [x] 0.1 Create directory structure
- [x] 0.2 Write pyproject.toml
- [x] 0.3 Write vizflow/__init__.py
- [x] 0.4 Write README.md
- [x] 0.5 Write tests/test_import.py
- [x] 0.6 Run tests locally
- [x] 0.7 Build package
- [x] 0.8 Upload to PyPI
- [ ] 0.9 Verify installation (user can test: pip install vizflow==0.1.0)

### Phase 1: Config + Market [COMPLETE]
- [x] 1.1 Create vizflow/config.py
- [x] 1.2 Create vizflow/market.py
- ~~1.3 io.py~~ (skipped - user uses Polars directly)
- [x] 1.4 Update __init__.py exports
- [x] 1.5 Create tests/test_config.py
- [x] 1.6 Create tests/test_market.py
- [x] 1.7 Run all tests (17 passed)
- [x] 1.8 Publish v0.2.0

### Phase 2: Core Operations [COMPLETE]
- [x] 2.1 Add parse_time() to ops.py
- [x] 2.2 Add bin() to ops.py
- [x] 2.3 Add aggregate() to ops.py
- [x] 2.4 Update __init__.py exports
- [x] 2.5 Create tests/test_ops.py
- [x] 2.6 Run all tests (35 passed)
- [x] 2.7 Publish v0.3.0

### Phase 3: Forward Returns + Calendar [ ]
- [ ] 3.1 Add forward_return() to ops.py
- [ ] 3.2 Create vizflow/calendar.py
- [ ] 3.3 Update __init__.py exports
- [ ] 3.4 Create tests/test_forward_return.py
- [ ] 3.5 Create tests/test_calendar.py
- [ ] 3.6 Run all tests
- [ ] 3.7 Publish v0.4.0

### Phase 4: Execution [ ]
- [ ] 4.1 Create vizflow/context.py
- [ ] 4.2 Add run() to run.py
- [ ] 4.3 Add run_batch() to run.py
- [ ] 4.4 Add run_local() to run.py
- [ ] 4.5 Add run_cluster() to run.py
- [ ] 4.6 Update __init__.py exports
- [ ] 4.7 Create tests/test_run.py
- [ ] 4.8 Run all tests
- [ ] 4.9 Publish v0.5.0

### Phase 5: Enrichment Framework [ ]
- [ ] 5.1 Create base classes (State, TagRule)
- [ ] 5.2 Add TagCondition rule
- [ ] 5.3 Add TagRunning rule
- [ ] 5.4 Add Enricher class
- [ ] 5.5 Update __init__.py exports
- [ ] 5.6 Create tests/test_enrichment.py
- [ ] 5.7 Run all tests
- [ ] 5.8 Publish v0.6.0

### Phase 6: FIFO Matching [ ]
- [ ] 6.1 Add FIFOMatch rule
- [ ] 6.2 Update Enricher for row-expanding
- [ ] 6.3 Create tests/test_fifo.py
- [ ] 6.4 Run all tests
- [ ] 6.5 Publish v0.7.0

### Phase 7: Visualization [ ]
- [ ] 7.1 Create vizflow/viz.py
- [ ] 7.2 Add optional dependencies
- [ ] 7.3 Create tests
- [ ] 7.4 Publish v0.8.0

---

## Project Assumptions

**User Profile**:
- User knows Polars well - don't wrap simple Polars operations
- VizFlow is an **extension tool** for Polars, not a replacement
- VizFlow is a **workflow accelerator** - focus on saving time for complex/repetitive tasks

**What VizFlow Should Do**:
- Things that are **hard to do** (e.g., FIFO matching with trade splitting)
- Things that are **complicated** (e.g., elapsed_seconds with market sessions)
- Things that require **heavy coding** (e.g., batch processing with skip_existing)

**What VizFlow Should NOT Do**:
- Wrap simple Polars operations (load/save/scan - user can do `pl.scan_parquet()`)
- Add unnecessary abstraction layers
- Hide Polars from the user

---

## Implementation Rules

**IMPORTANT**: Before implementing any module:
1. Read the relevant section in `docs/DESIGN.md` for API design
2. Read the relevant step in `docs/PLAN.md` for implementation details
3. Follow the specs exactly - don't add extra functionality
4. Ask: "Is this hard/complicated/heavy? Or can the user do it easily with Polars?"

---

## How to Continue

When resuming work on this project:

1. **Read this file** to see current phase and last completed step
2. **Read `docs/PLAN.md`** for detailed step instructions
3. **Continue from the next unchecked step**
4. **After completing a step**, update the checkbox in this file
5. **After completing a phase**, update "Current Phase" and "Current Version" above

---

## Workflow per Step

```
1. Implement the step
2. Write/update tests
3. Run tests: pytest tests/
4. If tests pass: mark step complete in this file
5. If tests fail: fix and re-run
```

## Workflow per Phase

```
1. Complete all steps in the phase
2. Run full test suite: pytest tests/
3. Update version in pyproject.toml and __init__.py
4. Build: python -m build
5. Upload: twine upload dist/*
6. Verify: pip install vizflow==X.Y.Z
7. Mark phase complete, update Current Phase/Version
8. Get user feedback before starting next phase
```

---

## Commands Reference

```bash
# Run tests
pytest tests/

# Run specific test
pytest tests/test_market.py -v

# Build package
python -m build

# Upload to PyPI (test)
twine upload --repository testpypi dist/*

# Upload to PyPI (production)
twine upload dist/*

# Install locally for testing
pip install -e .

# Install from PyPI
pip install vizflow==0.1.0
```

---

## Notes

- **Always run tests before marking a step complete**
- **Get user feedback at the end of each phase before proceeding**
- **Each phase should be independently usable after publishing**
- **Keep backward compatibility - don't break existing API**
