---
description: Resume, start, or complete development work based on project state
argument-hint: [US-number | --complete]
---

Read `tasks/PROGRESS.md`, the current epic file, and check git branch to understand project state.

**CRITICAL RULES:**
- ALWAYS ask user before ANY git command (branch, commit, merge, push, delete)
- ALWAYS end with "Next action:" suggesting what to do next
- Follow CLAUDE.md patterns and conventions

---

## If argument is "--complete":

Complete the current US:

1. Identify current US from git branch name (e.g., `feature/us-1.1-*`)
2. Read acceptance criteria from the epic file
3. **Pre-check: Verify all tasks are implemented**
   - Check each task in the US against actual files/code
   - If tasks remain incomplete: list them and STOP
   - Say: "Cannot complete - these tasks remain: [list]"
4. For EACH acceptance criterion, verify with actual test:
   - Run the relevant command/check
   - Document pass/fail result
5. Show verification summary table
6. If ALL pass:
   - Update epic file: mark US as ✅ Completed
   - Update `tasks/PROGRESS.md` with completion info (date, commit hash placeholder)
   - Show changes and ASK user: "Commit these changes?"
   - After commit, ASK user: "Merge to develop?"
   - After merge, ASK user: "Delete feature branch?"
7. If any fail:
   - List failing criteria with details
   - Suggest specific fixes
   - Do NOT mark as complete
   - Next action: "Fix the failing criteria, then run `/continue --complete` again"

---

## If argument is a US number (e.g., "1.2"):

Start US $ARGUMENTS:

1. Check if another US is already in progress (🔶 in epic files)
   - If yes: WARN user and ask to confirm switching
   - "US X.X is in progress. Abandon it and start $ARGUMENTS?"
2. Read the US from appropriate epic file in `tasks/`
3. Verify prerequisites:
   - Previous US in epic must be ✅ Completed
   - If not: STOP and say which US must be completed first
4. Show US overview (description, tasks, acceptance criteria)
5. ASK user: "Create feature branch `feature/us-$ARGUMENTS-<short-name>`?"
6. After branch created:
   - Update epic file: mark US as 🔶 In Progress
   - Update `tasks/PROGRESS.md`: set epic to 🔶 In Progress if not already
7. List all tasks to implement
8. Begin first task implementation
9. Next action: "Continue implementing tasks. Run `/continue` to check progress."

---

## If no argument:

### Case 1: A US is 🔶 In Progress

1. Identify which US from epic files
2. Check current git branch matches expected feature branch
   - If not: warn user about branch mismatch
3. Read the US requirements and task list
4. **Analyze task completion:**
   - Check each task against actual files/code
   - Count completed vs remaining
5. **If ALL tasks appear complete:**
   - Show: "All tasks complete (X/X)"
   - Show acceptance criteria preview
   - Next action: "Run `/continue --complete` to verify and finalize"
6. **If tasks remain:**
   - Show: "Tasks: X/Y complete"
   - List remaining tasks with checkboxes
   - Continue implementing next incomplete task
   - Next action: "Continue with remaining tasks, or `/status` to check progress"

### Case 2: No US in progress (all 🔲 or ✅)

1. Find next US to start (first 🔲 Not Started in current epic)
2. Show US summary (title, description, task count)
3. Next action: "Run `/continue X.X` to start this US"

### Case 3: Current epic complete (all US ✅)

1. Update `tasks/PROGRESS.md`: mark epic as ✅ Completed
2. Show epic completion summary
3. Identify next epic
4. Show next epic overview
5. Next action: "Run `/continue X.1` to start first US of next epic"

---

## Output Format

Always include at the end:

```
---
**Status:** [Epic X: Name] | [US X.X: Name] | [Tasks: X/Y]
**Branch:** [current branch]
**Next action:** [specific instruction]
```
