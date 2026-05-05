# My Cognitive Harness — Agent Instructions

> This file follows the [AGENTS.md](https://aaif.io) specification (Linux Foundation / AAIF).
> It is the canonical instruction file for all AI coding agents working in this repo.

## Memory

Shared memory lives in `.agents/memory/`. It is the agent's long-term store — distilled knowledge about the user, the project, and how to work effectively with both. Memory operates on a **Write → Manage → Read** lifecycle. The agent owns all three phases.

### Memory Types

Each entry has a `type` declared in frontmatter:

| Type | Contains | Example |
|---|---|---|
| `user` | Who the user is, role, expertise, preferences | "Senior engineer, deep Go background, new to React" |
| `feedback` | Corrections and validated approaches from the user | "Don't mock the database in tests — use real DB" |
| `project` | Time-bound facts about ongoing work, decisions, deadlines | "Merge freeze begins 2026-03-05 for mobile release cut" |
| `reference` | Pointers to where information lives in external systems | "Pipeline bugs tracked in Linear project INGEST" |

Do not invent new types.

### Read

- At session start: read `.agents/memory/MEMORY.md` (the index). Eagerly load the body of any memory whose `type` is `user` or `feedback` — these define how to work with the user and apply to every task.
- During a session: open `project` and `reference` memories on demand, only when their index entry looks relevant to the current task. Do not load them all upfront.
- Before recommending anything based on a memory: verify the underlying fact still holds (file still exists, function still named that, etc.). A memory is a claim about a past moment, not a guarantee about now.
- If a memory contradicts what you observe in the current code/state: trust what you observe, then update or delete the stale memory.

**Retrieval contract by type:**

| Type | Retrieval |
|---|---|
| `user` | Always-load — eager at session start |
| `feedback` | Always-load — eager at session start |
| `project` | On-demand — load when the index entry matches the current task |
| `reference` | On-demand — load when the index entry matches the current task |

### Write

Save a memory when **any** of these is true:
- The user explicitly asks ("remember this", "save this").
- The user corrects your approach (→ `feedback`).
- The user validates a non-obvious approach you took (→ `feedback`).
- You learn a durable fact about the user, project, or external system that future sessions will need.

Do **not** save:
- Code patterns, file paths, conventions — these are derivable by reading the repo.
- Ephemeral task state — use tasks or plans for that.
- Anything already in `AGENTS.md` or other instruction files.

Format: one file per memory, kebab-case filename matching the topic. Frontmatter:

```markdown
---
name: <short title>
description: <one-line hook used by the index — be specific>
type: user | feedback | project | reference
created: YYYY-MM-DD
expires_on: YYYY-MM-DD     # optional — hard expiry, janitor proposes deletion after this date
review_after: YYYY-MM-DD   # optional — soft expiry, janitor proposes review after this date
---

<body>

For `feedback` and `project` types, structure the body as:
- Lead sentence: the rule or fact
- **Why:** the reason the user gave (or the underlying motivation)
- **How to apply:** when this kicks in
```

`expires_on` and `review_after` are both optional. Set them at write-time when the memory has a known shelf life:
- `feedback` and `user` memories rarely need either — they're durable until explicitly overridden.
- `project` memories often have an `expires_on` (a known deadline) or `review_after` (situation may evolve).
- `reference` memories often have a `review_after` (verify the external system still exists).

After writing, add a one-line entry to `MEMORY.md` under the matching type heading: `- [Title](file.md) — one-line hook`.

### Manage

Memory left unmanaged rots — entries grow stale, contradict each other, and dilute the agent's reasoning. The agent maintains memory continuously, not just on a schedule.

**When a memory is contradicted by current observation or by a newer memory:**
- If the old memory is wrong → delete it (and remove its `MEMORY.md` line).
- If the old memory is partially wrong → edit it in place.
- Never leave two contradicting memories side by side.

**On user request to "forget X":** find the matching memory, delete the file, and remove its `MEMORY.md` line.

**Dedicated maintenance skills:**
- `memory-reflect` — user-initiated review of the current session for new candidates and contradictions.
- `memory-prune` — janitor that scans the whole memory store for expired entries, duplicates, and integrity issues. Writes findings to `.agents/memory/_janitor-report.md` for review.

## Skills

All custom skills are defined in `.agents/skills/`. When a user request matches a skill's description, load and follow the full instructions from that skill's `SKILL.md`. Do not improvise — defer to the skill.

When asked about available skills, list everything found in `.agents/skills/`.
