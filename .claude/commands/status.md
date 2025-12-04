---
description: Quick read-only overview of project progress
---

Read `tasks/PROGRESS.md` and current epic file. Provide a concise status summary.

**This is READ-ONLY. Do not modify any files or run git commands.**

## Output

Show exactly this format:

```
## Project Status

**Epic:** [N] [Name] ([Status])
**Progress:** [X/Y US complete]

**Current US:** [X.X: Name] ([Status])
**Tasks:** [X/Y complete]

**Branch:** [current git branch]

---

**Next action:** [what to do next]
```

## Next Action Logic

- If US in progress with tasks remaining: "Continue implementing tasks"
- If US in progress with all tasks done: "Run `/continue --complete` to finalize"
- If no US in progress: "Run `/continue X.X` to start next US"
- If epic complete: "Run `/continue X.1` to start next epic"
