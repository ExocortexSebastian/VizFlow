# VizFlow Versioning Strategy

> Semantic versioning approach for pre-1.0 and post-1.0 releases

---

## Philosophy

**Pre-1.0**: Rapid iteration, breaking changes allowed, focus on getting design right
**Post-1.0**: Stable API, semantic versioning, backward compatibility

---

## Version Number Format

### Pre-1.0 (Current Phase)

**Format**: `0.MINOR.PATCH`

- **0.MINOR.0** - New features (new modules, new public APIs)
- **0.MINOR.PATCH** - Bug fixes, refactors, internal improvements (no new features)

**Breaking changes**: Allowed in any 0.MINOR release (document in changelog)

**Examples**:
- `0.3.0` → New features (parse_time, bin, aggregate)
- `0.4.0` → Refactor (global config pattern) - no new features, but changes API slightly
- `0.5.0` → New features (Enrichment + FIFO)
- `0.5.1` → Bug fix in FIFOMatch (no API changes)

### Post-1.0 (Future)

**Format**: `MAJOR.MINOR.PATCH`

- **MAJOR** - Breaking changes (incompatible API changes)
- **MINOR** - New features (backward compatible)
- **PATCH** - Bug fixes (backward compatible)

**Strict semantic versioning**: No breaking changes in MINOR or PATCH

---

## Roadmap: Pre-1.0 Development

### Phase 1: Core Features (0.1.0 - 0.7.0)

Build all essential features, allow API iteration.

| Version | Type | Focus | Breaking Changes? |
|---------|------|-------|-------------------|
| **0.1.0** | Feature | Project scaffolding | N/A (initial) |
| **0.2.0** | Feature | Config, Market (CN, CRYPTO) | Yes (new project) |
| **0.3.0** | Feature | Core ops (parse_time, bin, aggregate) | Yes (API design) |
| **0.4.0** | Refactor | Global config pattern | Minor (cleaner API) |
| **0.5.0** | Feature | Enrichment + FIFO | Yes (major new system) |
| **0.6.0** | Feature | Forward returns + Calendar | Likely no |
| **0.7.0** | Feature | Execution (run, run_batch, run_cluster) | Likely no |

**Status**: Currently at v0.4.0, next is v0.5.0

### Phase 2: Stability & Polish (0.8.0 - 0.9.x)

Freeze API, focus on stability, docs, performance.

| Version | Type | Focus | Breaking Changes? |
|---------|------|-------|-------------------|
| **0.8.0** | Feature | Visualization (optional) | No |
| **0.9.0** | Stabilization | **API freeze**, comprehensive docs | No (last chance) |
| **0.9.1** | Polish | Performance optimization | No |
| **0.9.2** | Polish | Bug fixes, edge cases | No |
| **0.9.3** | Polish | User feedback iteration | No |

**Goal**: v0.9.x series is "release candidates" for 1.0.0

### Phase 3: Production Release (1.0.0+)

| Version | Type | Focus |
|---------|------|-------|
| **1.0.0** | Major | **Production-ready**, stable API guarantee |
| **1.1.0** | Minor | New features (backward compatible) |
| **1.2.0** | Minor | More features |
| **2.0.0** | Major | Breaking changes (if absolutely needed) |

---

## What Triggers Version Bumps?

### Feature Release (0.MINOR.0)

**Triggers**:
- ✅ New public API (new function, class, module)
- ✅ New functionality exposed to users
- ✅ Significant refactor that changes how users import/use

**Examples**:
- v0.5.0: Adding `vf.Enricher`, `vf.FIFOMatch` (new public APIs)
- v0.6.0: Adding `vf.forward_return()` (new function)

**Does NOT trigger**:
- ❌ Internal code cleanup (no API change)
- ❌ Adding tests
- ❌ Documentation updates

### Patch Release (0.MINOR.PATCH)

**Triggers**:
- ✅ Bug fixes (no API change)
- ✅ Performance improvements (no API change)
- ✅ Internal refactors (no visible change)
- ✅ Documentation fixes

**Examples**:
- v0.5.1: Fix FIFO matching bug with partial fills
- v0.5.2: Improve parse_time performance by 2x
- v0.6.1: Fix forward_return handling of missing data

---

## Release Channels

### Stable (PyPI)

**Versions**: All 0.MINOR.0 and 0.MINOR.PATCH
**Cadence**: After all tests pass + user validation
**Audience**: All users

### Development (Git main branch)

**Version**: `0.MINOR.0.dev0` (in pyproject.toml between releases)
**Cadence**: Continuous
**Audience**: Contributors, advanced users

**Example** (between v0.5.0 and v0.6.0):
```toml
# pyproject.toml
version = "0.6.0.dev0"  # Next version in development
```

### Pre-releases (Optional, future)

**Versions**: `0.MINOR.0a1`, `0.MINOR.0b1`, `0.MINOR.0rc1`
**Use case**: Test complex features (like FIFO) before stable release
**Example**:
```
0.5.0a1  → Alpha 1 (feature complete, not tested)
0.5.0a2  → Alpha 2 (bug fixes)
0.5.0b1  → Beta 1 (tested, needs user feedback)
0.5.0rc1 → Release candidate (ready for release)
0.5.0    → Stable release
```

**Decision**: Skip for now, use dev branch instead. Reconsider for v1.0.0.

---

## Version 1.0.0 Criteria

**What makes v1.0.0 "production-ready"?**

### Functional Requirements

- ✅ All core features implemented:
  - [x] Config, Market, parse_time, bin, aggregate
  - [ ] Enrichment + FIFO
  - [ ] forward_return + calendar
  - [ ] Execution (run, run_batch, run_cluster)
  - [ ] Visualization (optional, can be 1.1.0)

### Quality Requirements

- ✅ **Test coverage**: >90% on core modules
- ✅ **Documentation**:
  - API reference complete
  - User guide with examples
  - Troubleshooting guide
- ✅ **Performance**:
  - Benchmarks documented
  - Handles TB-scale data (validated on ailab)
- ✅ **Real-world validation**: Used in production by at least 1 user (you)

### API Stability Requirements

- ✅ **No breaking changes** planned for 6 months
- ✅ **Deprecation policy** defined
- ✅ **Migration guide** from 0.9.x to 1.0.0 (if needed)

### Process Requirements

- ✅ **Changelog**: Complete history in CHANGELOG.md
- ✅ **Semantic versioning**: Committed to post-1.0
- ✅ **Release notes**: For every version
- ✅ **Security policy**: Defined (even if simple)

**Target**: v1.0.0 after v0.9.x stabilization (3-6 months from now)

---

## Breaking Changes Policy

### Pre-1.0 (Current)

**Allowed**: Yes, but document in changelog

**How to handle**:
1. Document in CHANGELOG.md under "BREAKING CHANGES"
2. Update migration guide in README
3. Bump MINOR version
4. Notify users in release notes

**Example** (v0.4.0 → v0.5.0):
```markdown
### BREAKING CHANGES in v0.5.0

- `vf.parse_time()` now requires `vf.set_config()` to be called first
- Old: `vf.parse_time(df, market=vf.CN, ...)`
- New: `vf.set_config(vf.Config(market="CN")); vf.parse_time(df, ...)`

Migration:
1. Add `vf.set_config(config)` at top of script
2. Remove `market` parameter from `parse_time()` calls
```

### Post-1.0 (Future)

**Allowed**: Only in MAJOR version bumps

**Process**:
1. Deprecate old API in MINOR release
2. Warn users for at least 2 MINOR versions
3. Remove in next MAJOR release

**Example** (hypothetical):
```python
# v1.5.0: Deprecate old API
def old_function():
    warnings.warn("old_function is deprecated, use new_function", DeprecationWarning)
    return new_function()

# v1.6.0, v1.7.0: Warning continues

# v2.0.0: Remove old_function entirely
```

---

## Revised Version Roadmap

### Immediate (Current Development)

| Version | Status | Features | Notes |
|---------|--------|----------|-------|
| 0.1.0 | ✅ Released | Scaffolding | Initial PyPI |
| 0.2.0 | ✅ Released | Config, Market | Foundation |
| 0.3.0 | ✅ Released | parse_time, bin, aggregate | Core ops |
| 0.4.0 | ✅ Released | Global config refactor | Internal improvement |
| **0.5.0** | 🚧 Next | **Enrichment + FIFO** | **Hardest feature** |
| 0.5.1 | 🔮 Future | Bug fixes from 0.5.0 | If needed |

### Near-term (Next 2-3 months)

| Version | Features | Complexity | Priority |
|---------|----------|------------|----------|
| **0.6.0** | forward_return, calendar | ⭐⭐ Medium | High |
| 0.6.1 | Bug fixes, edge cases | - | If needed |
| **0.7.0** | Execution (run, run_batch, run_cluster) | ⭐⭐⭐ Medium-High | High |
| 0.7.1 | Production hardening | - | Likely |

### Medium-term (3-6 months)

| Version | Features | Focus |
|---------|----------|-------|
| **0.8.0** | Visualization (Dash) | Optional, can skip |
| **0.9.0** | API freeze, docs, polish | Stabilization |
| 0.9.1-3 | Bug fixes, performance | Pre-release validation |

### Long-term (6+ months)

| Version | Milestone |
|---------|-----------|
| **1.0.0** | Production-ready release |
| 1.1.0 | First post-1.0 feature release |

---

## Version Numbering Examples

### Scenario 1: FIFO Bug After v0.5.0

```
v0.5.0  → Release with FIFO
  ↓
User reports bug: FIFO fails on zero-qty trades
  ↓
v0.5.1  → Fix zero-qty bug (patch release)
```

### Scenario 2: Add overnight_return to v0.6.0

```
v0.6.0  → Release with forward_return, calendar
  ↓
Decide to add overnight_return (new function)
  ↓
Option A: v0.6.1 (minor feature, fits theme) ✅
Option B: v0.7.0 (if execution is delayed)
```

### Scenario 3: Performance Refactor

```
v0.5.0  → FIFO initial release
  ↓
Optimize FIFO algorithm (2x faster, same API)
  ↓
v0.5.1  → Performance improvement (patch) ✅
```

### Scenario 4: Breaking API Change Pre-1.0

```
v0.6.0  → forward_return(df, horizons=[60])
  ↓
Decide horizons should be in config, not parameter
  ↓
v0.7.0  → BREAKING: forward_return(df) reads config.horizons
  ↓
Document in CHANGELOG, update examples
```

---

## Changelog Format

**File**: `CHANGELOG.md` (add to repo)

**Format**: Keep a Changelog style

```markdown
# Changelog

## [0.5.0] - 2024-12-XX

### Added
- Enrichment framework (State, TagRule, Enricher)
- FIFOMatch rule for trade matching with splitting
- TagCondition, TagRunning rules

### Changed
- (none)

### Deprecated
- (none)

### Removed
- (none)

### Fixed
- (none)

### BREAKING CHANGES
- Enricher.run() now requires sorted input (by sort_by column)
- FIFOMatch returns list[dict] for split trades (row-expanding)

## [0.4.0] - 2024-12-12

### Added
- Global config pattern (set_config, get_config)

### Changed
- parse_time() now uses global config instead of parameters
- Simplified API (don't need to pass market everywhere)

### BREAKING CHANGES
- parse_time() signature changed: removed market parameter
- Must call set_config() before using parse_time()

## [0.3.0] - 2024-12-11

### Added
- parse_time() operation
- bin() operation
- aggregate() operation

(etc.)
```

---

## Release Checklist

### For Feature Releases (0.MINOR.0)

- [ ] All tests pass (`pytest tests/`)
- [ ] Update `__version__` in `__init__.py`
- [ ] Update `version` in `pyproject.toml`
- [ ] Update CHANGELOG.md with changes
- [ ] Update CLAUDE.md progress tracker
- [ ] Build package (`python -m build`)
- [ ] Test install locally (`pip install dist/*.whl`)
- [ ] Upload to PyPI (`twine upload dist/*`)
- [ ] Create git tag (`git tag v0.5.0`)
- [ ] Push tag (`git push origin v0.5.0`)
- [ ] Create GitHub release with notes
- [ ] Update demo.ipynb if needed
- [ ] Notify users (if any breaking changes)

### For Patch Releases (0.MINOR.PATCH)

Same as above, but:
- [ ] Verify no new features added
- [ ] Verify no breaking changes
- [ ] Can skip CLAUDE.md update (just bug fixes)

---

## Summary: Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Versioning scheme** | 0.MINOR.PATCH (pre-1.0) | Standard for pre-release projects |
| **Breaking changes** | Allowed in 0.MINOR | Need flexibility during design phase |
| **FIFO version** | v0.5.0 (merged with Enrichment) | Architectural cohesion |
| **forward_return version** | v0.6.0 (after FIFO) | Follows pipeline stage order |
| **1.0.0 criteria** | Features + quality + stability | Clear production-ready definition |
| **Changelog** | Keep a Changelog format | Industry standard |
| **Pre-releases** | Skip for now, maybe for 1.0.0 | Simplicity during rapid dev |
| **Dev versions** | Use .dev0 on main | Clear distinction from releases |

---

**Next Steps**:
1. Create CHANGELOG.md
2. Update CLAUDE.md to v0.4.0
3. Implement v0.5.0 (Enrichment + FIFO)
4. Follow this versioning strategy going forward