# Synapse Development Workflow

## Overview

แต่ละ Phase จะมี workflow ดังนี้:

```
START → WORK → REVIEW → COMMIT → NEXT
```

## Outputs Per Phase

| Output | Description | Who |
|--------|-------------|-----|
| `docs/reports/phase_N_report.md` | สรุปงานที่ทำ | โจ (Claude) |
| `docs/reviews/phase_N_review.md` | Code review | Codex |
| `git commit` | Version control | Git |

## Phases

### Phase 0: Project Setup ✅ (Done)
- สร้างโปรเจค
- โครงสร้างพื้นฐาน
- Documentation

### Phase 1: Bug Fixes (Current)
- แก้ bugs ที่ Codex พบ
- Import errors
- TTL bugs
- Duplicate code

### Phase 2: Fork Graphiti
- Clone Graphiti
- Integrate into Synapse
- Test basic functionality

### Phase 3: Five Layers
- Implement all 5 memory layers
- User model, Procedural, Semantic, Episodic, Working

### Phase 4: Thai NLP
- Thai NLP client
- Integration with entity extraction
- Integration with search

### Phase 5: MCP Server
- Unified MCP server
- All tools
- Integration with JellyCore

## Report Template

```markdown
# Phase N Report

**Date:** YYYY-MM-DD
**Author:** โจ (Claude)
**Reviewer:** Codex

## Tasks Completed
- [ ] Task 1
- [ ] Task 2

## Changes Made
| File | Change |
|------|--------|
| path/to/file | Description |

## Test Results
- Test 1: ✅/❌
- Test 2: ✅/❌

## Issues Found
- Issue 1

## Next Phase
- Task for next phase
```

## Review Template

```markdown
# Phase N Codex Review

**Date:** YYYY-MM-DD
**Reviewer:** Codex (gpt-5.3-codex)

## Files Reviewed
- file1.py
- file2.py

## Findings
| Severity | Issue | Line | Suggestion |
|----------|-------|------|------------|
| 🔴 High | ... | ... | ... |

## Approval
- [ ] Approved
- [ ] Needs fixes

## Comments
...
```

## Git Commit Format

```
phase(N): Brief description

- Task 1 completed
- Task 2 completed

Files changed:
- path/to/file1
- path/to/file2

Report: docs/reports/phase_N_report.md
Review: docs/reviews/phase_N_review.md

Co-Authored-By: Claude <noreply@anthropic.com>
Co-Authored-By: Codex <codex@openai.com>
```
