---
description: Create a new epic with user stories following project standards
argument-hint: <epic-title>
---

Create a new epic based on the user's request. You MUST follow the established format and patterns.

**Argument:** $ARGUMENTS (the epic title or feature description)

---

## CRITICAL: Read-Only Information Gathering

**IMPORTANT:** This command is for PLANNING only. When gathering information:

1. **DO** read files, documents, and configuration to understand the codebase
2. **DO** use `ls`, `find`, `wc -l` to explore file structure
3. **DO NOT** execute tests, builds, or any long-running commands
4. **DO NOT** run `pytest`, `npm test`, `make`, or similar commands
5. **ASK FIRST** if you need to execute anything that takes more than a few seconds

If you need to run tests or long commands to understand the current state, **ask the user for permission first** and explain why it's needed.

---

## Step 1: Analyze Existing Epics

Before creating the new epic, read `tasks/PROGRESS.md` to:
1. Determine the next epic number (e.g., if Epic 11 exists, create Epic 12)
2. Understand the project context and completed work

---

## Step 2: Ask Clarifying Questions

Before writing the epic, ask the user about:
1. **Scope:** What specific features/functionality should this epic deliver?
2. **User Stories:** How many US do they envision? What are the main components?
3. **Prerequisites:** Does this depend on other epics?
4. **Complexity:** Should this be a large epic (4-5 US) or small (2-3 US)?

Wait for user response before proceeding.

---

## Step 3: Create Epic File

Create `tasks/epic-{N}-{slug}.md` following this EXACT structure:

```markdown
# Epic {N}: {Title}

## Overview

{2-3 sentences describing what this epic delivers and its value}

## Prerequisites

- {List any required epics or conditions}
- {Technical prerequisites}

## User Stories

---

## US {N}.1: {First User Story Title}

**Status:** 🔲 Not Started

### Description

{Clear description of what this US delivers}

### Context

{Why this is needed, background information}

### Tasks

- [ ] {Task 1 with clear deliverable}
- [ ] {Task 2}
- [ ] {Task 3}

### Implementation Details

{Optional: Code snippets, architecture decisions, API specs}

### Acceptance Criteria

- [ ] {Testable criterion 1}
- [ ] {Testable criterion 2}
- [ ] {Testable criterion 3}

### Tests

- **Modified:** `tests/test_<module>.py` - Update/fix tests for changed code
- **New:** `tests/test_<feature>.py` - Add tests for new functionality (if applicable)
- **Run:** `pytest tests/test_<module>.py -v` to verify

> Note: Only add new tests for new public functions/endpoints. Keep it minimal: 1 happy path + 1-2 edge cases.

### Files to Create/Modify

1. `path/to/file.py` - Description
2. `path/to/other.py` - Description

---

## US {N}.2: {Second User Story Title}

{... same structure ...}

---

## Definition of Done (Epic {N})

- [ ] All User Stories completed ({X}/{X} US)
- [ ] {Key deliverable 1}
- [ ] {Key deliverable 2}
- [ ] All acceptance criteria verified
- [ ] Tests pass
- [ ] Documentation updated
```

---

## Step 4: Update PROGRESS.md

Add the new epic to `tasks/PROGRESS.md`:

1. Add row to **Epic Status** table:
   ```
   | {N}  | {Epic Name}  | 🔲 Not Started | 0/{X} US |
   ```

2. Add to **Epic Files** list:
   ```
   - [Epic {N}: {Name}](./epic-{N}-{slug}.md)
   ```

---

## Epic Structure Rules

### User Story Guidelines

Each US MUST include:
- **Status:** Use exactly: `🔲 Not Started`, `🔶 In Progress`, or `✅ Completed`
- **Description:** What this US delivers (1-2 sentences)
- **Context:** Why it's needed, technical background
- **Tasks:** Checkboxes with concrete deliverables
- **Acceptance Criteria:** Testable, verifiable conditions
- **Tests:** Which tests to modify/add and command to run
- **Files to Create/Modify:** Explicit file list

### Complexity Guidelines

| Epic Size | User Stories | When to use |
|-----------|--------------|-------------|
| Small     | 2-3 US       | Bug fixes, minor features |
| Medium    | 3-4 US       | Standard features |
| Large     | 4-5 US       | Major features, infrastructure |

### Optional Sections (use when appropriate)

- **Implementation Details:** Code snippets, API specs
- **Architecture:** Diagrams, component relationships
- **Dependencies:** US dependency graph
- **Estimated Effort:** Complexity ratings per US
- **Test Scenarios:** For testing-focused epics
- **Migration:** For epics affecting existing data

---

## Naming Conventions

- Epic file: `epic-{number}-{slug}.md` (lowercase, hyphens)
- US numbering: `{epic}.{story}` (e.g., 12.1, 12.2)
- Branch: `feature/us-{epic}.{story}-{short-name}`

---

## Output Format

After creating the epic, show:

```
---
**Created:** Epic {N}: {Name}
**File:** tasks/epic-{N}-{slug}.md
**User Stories:** {X} US planned
**Next action:** Run `/flo_continue {N}.1` to start first US
```
