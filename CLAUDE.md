# My Cognitive Harness — Claude Code Instructions

## Memory

Shared memory for this project lives in `.agents/memory/`. Read `MEMORY.md` there as the index at the start of each session. Write new memories to that directory (not to `~/.claude/projects/...`), following the same typed frontmatter format (`type: user | feedback | project | reference`).

## Skills

All custom skills are defined in `.agents/skills/`. When a user request matches a skill's description, load and follow the full instructions from that skill's `SKILL.md`. Do not improvise — defer to the skill.

When asked about available skills, list everything found in `.agents/skills/`.
