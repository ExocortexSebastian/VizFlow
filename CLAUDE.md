# VizFlow - Claude Instructions

---

## 🚨 CRITICAL RULES

**1. NEVER UPLOAD SOURCE CODE (.tar.gz) TO PyPI**
- Upload wheel ONLY: `twine upload dist/*.whl`
- NEVER: `twine upload dist/*.tar.gz`
- ALWAYS ask user first: "Ready to publish v0.X.0 to PyPI?"
- twine upload --config-file /Users/yichenlu/VizFlow/.pypirc dist/*.whl
**2. ASK BEFORE WORKAROUNDS**
- When encountering confusing errors, ASK the user first
- Do NOT hardcode fixes to overfit the bug
- Example: If concat fails with schema error, ask "Are your files supposed to have the same schema?" before adding `how="diagonal"`

**3. READ DOCS FIRST - NO GUESSING**

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

---

## Dual Feedback Loop

This workspace contains both VizFlow (library) and research projects (use cases).

### Core Principles

1. **Research projects consume VizFlow** - No ad-hoc data processing code in projects/
2. **Feedback-driven development** - Missing features → FEEDBACK.md → implement in VizFlow
3. **Generalize, don't specialize** - Every new feature must benefit other users

### Workflow

1. Working in research project → discover missing VizFlow feature
2. Record to `/FEEDBACK.md` with standard template
3. Switch to VizFlow → implement feature (TDD: test first)
4. Return to research → use new feature
5. Update FEEDBACK.md status → request code-review before deletion

### Slash Commands

- `/research <project>` - **DRIVER** - Push research forward, iterate on analysis
- `/feedback` - Record a new feature request to FEEDBACK.md
- `/implement-feedback` - Pick an open item and implement in VizFlow
- `/review-feedback` - Verify implementation before removing from FEEDBACK.md
