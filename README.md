# My Cognitive Harness

> A personal agentic infrastructure repository — the operational layer that gives AI agents the context, skills, memoryP, tools, and guardrails they need to work reliably in my day-to-day environment.

---

## What Is a Cognitive Harness?

A **cognitive harness** is the personal infrastructure layer that sits between raw AI models and real-world workflows. The model provides reasoning; the harness provides everything else:

| Layer | Responsibility |
|---|---|
| **Agent Skills** | Domain expertise and repeatable workflows loaded on demand |
| **Memory** | Durable knowledge the agent owns and manages — what's true about the user, the project, and how to work effectively. Maintained across sessions and shared across runtimes |
| **MCP Servers** | Connections to external tools, services, and data sources |
| **Context Engineering** | Curated prompts and rules that keep agents focused; progressive disclosure to manage the context window |
| **Guardrails** | Boundaries, human-in-the-loop checkpoints, and safety policies |

The distinction matters: the *agent* handles "what" and "why"; the *harness* handles "how" and "where." Even the most capable model will drift, hallucinate tool calls, or lose context without solid scaffolding around it.

A harness without memory is a harness that starts cold every session — re-learning the same preferences, re-asking the same questions, re-deriving the same conclusions. Memory is what turns a capable model into an agent that gets *better* at working with you over time. But memory only delivers that benefit if it's actively managed: written deliberately, pruned regularly, and treated as a first-class concern rather than a passive log.

---

## Architecture Overview

```
my-cognitive-harness/
├── .agents/
│   ├── skills/              # Agent Skills — auto-discovered by all compliant agents
│   └── memory/              # Shared agent memory — survives across sessions and runtimes
├── AGENTS.md                # Canonical agent instructions (AAIF spec)
├── CLAUDE.md                # Claude Code-specific overrides (defers to AGENTS.md)
├── .github/
│   └── copilot-instructions.md  # Copilot-specific overrides (defers to AGENTS.md)
└── README.md
```

---

## Agent Skills

Skills follow the [agentskills.io specification](https://agentskills.io/specification) — a lightweight, open standard originally developed by Anthropic and supported by GitHub Copilot, Claude, and most major agent runtimes.

### How Skills Work

1. **Discovery** — At startup, agents load only the `name` and `description` from each `SKILL.md` to know when a skill is relevant.
2. **Activation** — When a task matches a skill's description, the agent reads the full instructions into context.
3. **Execution** — The agent follows the instructions and optionally loads referenced scripts or assets as needed.

### Directory Structure per Skill

```
skill-name/
├── SKILL.md          # Required: YAML frontmatter + Markdown instructions
├── scripts/          # Optional: executable code (Python, Bash, JS)
├── references/       # Optional: detailed docs, forms, domain reference
└── assets/           # Optional: templates, schemas, diagrams
```

### Installing Skills via Tessl

[Tessl](https://tessl.io) is the package manager for agent skills. Use it to discover, install, and evaluate skills from the public registry:

```bash
# Search for available skills
npx tessl search

# Install a skill into this repo
npx tessl i <org>/<skill-name>

# Evaluate a skill's quality
npx tessl evaluate ./.agents/skills/<skill-name>
```

Skills installed via Tessl land in `.agents/skills/` and are immediately auto-discovered by any spec-compliant agent scanning the repo.

---

## Memory

Memory is what lets the agent get smarter about *me* and *my work* over time, instead of starting cold every session. It lives in `.agents/memory/` and is shared across every runtime that reads this repo — Claude Code, Copilot, and any future agent.

### Principles

1. **One source of truth.** All runtimes read and write to `.agents/memory/`. No runtime maintains its own private store. This avoids the trap of Claude knowing something Copilot doesn't (or vice versa).

2. **Distinct from skills.** Skills are *procedural* — how to do recurring tasks. Memory is *content* — what's true about me, the project, and how I like to work. The two never overlap.

3. **Distinct from RAG.** Memory is what the agent owns and manages. RAG and MCP fetch external knowledge the agent doesn't own. If the agent didn't write it, it's not memory.

4. **Write → Manage → Read.** Memory that's only written and read but never managed will rot. Stale entries accumulate, contradict each other, and dilute the agent's reasoning. Management is a first-class responsibility, not an afterthought.

### Architectural Scope

Memory in AI agents draws from a well-established taxonomy in cognitive science (Atkinson & Shiffrin 1968, Tulving 1972) and its adaptation to LLM agents (CoALA, Sumers et al. 2023). Four temporal scopes, each serving a different function:

| Scope | Analogy | What it holds | Where it lives in this harness |
|---|---|---|---|
| **Working** | RAM | The current prompt, conversation, tool results — what the model is actively reasoning with | The runtime's context window (transient) |
| **Episodic** | Diary | A timeline of past events — what was said, what tools ran, what came back | Conversation transcripts (`~/.claude/projects/.../*.jsonl`) |
| **Semantic** | Encyclopedia | Distilled, abstracted knowledge the agent has learned and retained | **`.agents/memory/`** ← the focus of this section |
| **Procedural** | Instruction manual | How to act — rules, workflows, behavioural patterns | `.agents/skills/` and `AGENTS.md` |

The harness implements all four, but only **semantic memory** is what most people mean colloquially when they say "memory" — the durable, agent-owned store of facts and preferences that persist across sessions. That's what `.agents/memory/` is for, and what the rest of this section describes.

> Curious about the theory? See [`engineering_excellence_q4/agent-memory-architecture.md`](engineering_excellence_q4/agent-memory-architecture.md) for the full taxonomy, lineage, and the Write → Manage → Read lifecycle model.

### Content Categories

Each memory file declares its type in frontmatter:

| Type | What it stores | Example |
|---|---|---|
| `user` | Who I am, role, expertise, preferences | "Senior engineer, deep Go background" |
| `feedback` | Corrections and validated approaches | "Don't mock the database in tests" |
| `project` | Time-bound facts about ongoing work | "Merge freeze begins 2026-03-05" |
| `reference` | Pointers to external systems | "Pipeline bugs tracked in Linear: INGEST" |

### Practical Layout (example)

```
.agents/memory/
├── MEMORY.md                # Index — loaded at every session start
├── preferences.md           # type: user
├── feedback-skills-scope.md # type: feedback
├── cx-iq-agent-registry.md  # type: reference
└── engineering-excellence-template.md  # type: project
```

`MEMORY.md` is the lightweight index — one line per memory file. Individual memories are loaded on demand when relevant to the current task.

### How Agents Use It

The behavioural contract (when to write, how to manage, when to read) lives in [AGENTS.md](./AGENTS.md). Every runtime defers to that file, so the rules are the same whether the session is in Claude Code or Copilot.

---

## MCP Servers

MCP (Model Context Protocol) servers extend agent capabilities with live connections to external systems. Server configuration is maintained in two files:

- [`.mcp.json`](.mcp.json) — Claude Code (top-level key `mcpServers`)
- [`.vscode/mcp.json`](.vscode/mcp.json) — GitHub Copilot (top-level key `servers`, supports `inputs` block)

Both files must be kept in sync manually. There is no shared MCP config format across runtimes — the two tools use similar but incompatible schemas, and both write directly to their own file, making generation from a canonical source impractical.

### Current Server Inventory

| Server | System | Use Cases |
|---|---|---|
| `github-cxepi` | GitHub (psmeunin-cxepi) | Cisco IQ engineering repos, CXEPI org |
| `github-cisco` | GitHub (psmeunin_cisco) | cisco-cx-agentic org, ACP repos |
| `cisco-cxe-atlassian` | Jira + Confluence | Cisco IQ projects, CX Engineering |
| `confluence-eng-gpk2` | Confluence Engineering | Internal Cisco knowledge base |
| `weaviate-docs` | Weaviate | Vector DB documentation |
| `docs-langchain` | LangChain | Official LangChain docs |
| `docs-openai` | OpenAI | Official OpenAI API docs |
| `pypi-query` | PyPI | Package info, deps, compatibility |
| `context7` | General library docs | Gemini, Mistral, and other frameworks |

### Authentication Notes

- GitHub PATs are stored in macOS Keychain and loaded via `.zshrc` + `launchctl setenv` for GUI app access.
- Classic PATs require **"Configure SSO"** authorization per GitHub org, or org repos will be invisible even with correct scopes.
- MCP HTTP server URLs **must** include `https://` — omitting the scheme causes VS Code to default to `file:///`.

---

## Primary Runtimes

This harness is designed to work with:

- **GitHub Copilot** (VS Code) — Primary IDE agent; reads skills from `.github/` and `.vscode/` automatically.
- **Claude** (claude.ai / Claude Code) — Reads skills from `.claude/` and any `SKILL.md` files in context.

Skills written to the [agentskills.io spec](https://agentskills.io/specification) are **agent-agnostic** — the same skill files work across Copilot, Claude, Gemini CLI, and other compatible runtimes without modification.

---

## Context Engineering Principles

This harness applies a **progressive disclosure** model to manage context window usage:

1. **Startup (~100 tokens/skill)** — Only `name` + `description` metadata is loaded for all skills.
2. **On activation (<5 000 tokens)** — Full `SKILL.md` instructions are loaded when the skill is triggered.
3. **On demand** — Referenced files in `scripts/`, `references/`, and `assets/` are loaded only when explicitly needed.

Additional principles:
- Keep individual `SKILL.md` files under 500 lines; move detail to `references/`.
- Prefer injecting specific documents via RAG over pre-loading large context.
- Summarize session history rather than accumulating raw logs in the context window.

---

## Getting Started

### 1. Clone the repo

```bash
git clone git@github.com:<your-username>/my-cognitive-harness.git
cd my-cognitive-harness
```

### 2. Install Tessl (if not already)

```bash
curl -fsSL https://get.tessl.io | sh
# or use npx without installing globally
npx tessl --help
```

### 3. Validate a skill

```bash
npx tessl evaluate ./.agents/skills/<skill-name>
```

### 4. Point your agent at the skills

For **GitHub Copilot** and **Claude Code**, skills in `.agents/skills/` are auto-discovered at the project level without any configuration — this is the cross-client convention both runtimes scan. Client-native paths (`.github/`, `.claude/skills/`) are also scanned, so skills in `.agents/skills/` will surface in all of them.

---

## Roadmap

- [ ] Author initial `cisco-iq-dev` skill with CXEPI AI framework patterns
- [ ] Author `jira-confluence` skill with standard workflow templates
- [ ] Author `code-review` skill with OWASP security checklist
- [ ] Set up Tessl workspace and publish first skill to registry
- [ ] Add GitHub Actions workflow to validate skills on PR
- [ ] Symlink or configure user-level skill discovery at `~/.agents/skills/` to expose harness skills globally across all projects

---

## References

- [Agent Skills Specification](https://agentskills.io/specification) — Official format spec
- [Tessl Registry](https://tessl.io/registry) — Discover and evaluate community skills
- [Tessl Docs](https://docs.tessl.io/) — CLI reference and evaluation guides
- [Example Skills](https://github.com/anthropics/skills) — Anthropic's reference skill library
- [Agent Harness Concepts](https://www.salesforce.com/agentforce/ai-agents/agent-harness/) — Infrastructure patterns for reliable agentic AI
- [skills-ref](https://github.com/agentskills/agentskills/tree/main/skills-ref) — Validation and prompt generation library
