# VizFlow - Claude Instructions

---

## 🚨 CRITICAL RULES

**1. NEVER UPLOAD SOURCE CODE (.tar.gz) TO PyPI**
- Upload wheel ONLY: `twine upload dist/*.whl`
- NEVER: `twine upload dist/*.tar.gz`
- ALWAYS ask user first: "Ready to publish v0.X.0 to PyPI?"

**2. READ DOCS FIRST - NO GUESSING**

When user asks about: design, datasources, plan, architecture, pipeline, stages, schema, config

**Protocol (must follow in order):**
1. Say: "Let me read the docs first."
2. Call `Read docs/DESIGN.md`
3. Call `Read docs/PLAN.md`
4. THEN answer based on what I just read

Do NOT skip steps. Do NOT answer from memory.

---

## Project Principles

**VizFlow is a Polars extension, NOT a replacement**

### What VizFlow Should Do
- Hard problems (FIFO matching with trade splitting)
- Complicated logic (elapsed_seconds with market sessions)
- Heavy coding tasks (batch processing, skip_existing)

### What VizFlow Should NOT Do
- Wrap simple Polars operations (user can do `pl.scan_parquet()`)
- Add unnecessary abstraction layers
- Hide Polars from the user

---

## Implementation Rules

Before implementing any module:

1. Read `docs/DESIGN.md` for API design
2. Read `docs/PLAN.md` for implementation steps
3. Follow specs exactly - NO extra features
4. Ask: "Can user do this easily with Polars?" → Don't add it

---

## Current Status

**Version**: v0.4.0 (Global config pattern)
**Next**: v0.5.0 (Enrichment + FIFO)

**See [docs/PLAN.md](docs/PLAN.md) for detailed progress and steps**

---

## Quick Commands

```bash
# Test
pytest tests/

# Build (OK to run)
python -m build

# Publish (ASK USER FIRST!)
twine upload dist/*.whl  # Wheel only, NOT .tar.gz!
```
