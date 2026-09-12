# AGENTS.md — jlcpcb-parts-cli integration guide for AI agents

This file teaches a coding/automation agent (Hermes, Claude Code, OpenClaw,
etc.) how to use this tool correctly. It is deliberately short and factual so
it can be pasted into a skill or system prompt with minimal tokens.

## What this tool is

Read-only CLI over JLCPCB's unofficial parts-search API. Single-file Python 3.10+
(stdlib only), no install: clone, copy to `~/.local/bin`, done. It never logs
in, never mutates anything — GET-like POST search requests only.

## Command contract

```
jlcpcb-parts-cli [--json] search <keyword> [--tier basic|promo|extended|any] [--min-stock N] [-n N]
jlcpcb-parts-cli [--json] basic [--category X] [--list-categories] [-n N] [--refresh]
jlcpcb-parts-cli [--json] info <C-code or MPN>
jlcpcb-parts-cli [--json] check [--timeout S]
jlcpcb-parts-cli export [-o out.md] [--refresh]
```

- `--json` is **global and must precede the subcommand**.
- Exit codes: `0` success · `1` WARN or no result for info · `2` API/payload
  error or canary FAIL. Stderr carries `error: <human message>` on failure.
- When offline or the API drifted, do not retry aggressively — report the
  error message; it always tells you whether it is network or schema drift.

## JSON output shape

`search` / `basic` / `info --json` emit an array of part objects:

```json
{
  "code": "C6186",
  "mpn": "AMS1117-3.3",
  "description": "...",
  "manufacturer": "AMS",
  "package": "SOT-223",
  "category": "Regulators",
  "stock": 43210,
  "tier": "basic | promo_extended | extended",
  "price_1": 0.0567,
  "url": "https://jlcpcb.com/partdetail/...",
  "datasheet": "https://...pdf"
}
```

`check --json` emits `{"status": "PASS|WARN|FAIL", "checks": [...]}`.

## Semantics an agent must respect

- **Tier priority is the point**: when picking parts for JLCPCB Assembly,
  prefer `basic` > `promo_extended` > `extended`, then stock. The default sort
  already does this — don't re-sort by price.
- `stock` on JLC = assembly-line stock (what their machines can place), not
  retail stock. For hand-buying use lcsc-cli.
- Ambiguous keywords work, but exact MPNs give exact hits; prefer full MPNs.
- `info` accepts either a C-code (`C6186`) or an MPN (`AMS1117-3.3`).

## Safety boundaries (hard rules)

- Never attempt login, cart, order, or account flows — the tool has none and
  must never gain any.
- Keep request volume modest: no bulk crawling beyond what `basic`/`export`
  already cache locally (24h cache under `~/.cache/jlcpcb-parts-cli/`).
- Payloads are volatile: treat any field as possibly missing; the client
  already degrades to `null` instead of crashing.
- If `check` fails, the endpoint moved or the schema changed: report it, then
  verify against https://jlcpcb.com/parts manually before code changes.

## Using as a skill

This repository ships a ready-made, agent-neutral skill at
`skill/jlcpcb-parts-cli/SKILL.md` (AgentSkills-compatible SKILL.md with YAML
frontmatter — the same format Claude Code, OpenCode, OpenClaw, and Hermes
load). `./install.sh` installs ONLY the CLI. Skills are never sprayed into
every agent on the machine: when a user asks THIS agent to integrate the
tool, the agent runs
`./install.sh --skill-dir <its-own-skills-dir>` — one explicit target,
chosen by the agent that owns it, at the moment its user asks.

## Maintenance

- Tests: `python3 -m unittest discover tests` (offline fixtures).
- After an API change: create the smallest synthetic regression fixture; never
  commit raw vendor responses. Update `tests/fixtures/NOTES.md` and keep
  `check` canaries green.
