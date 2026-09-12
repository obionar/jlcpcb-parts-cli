---
name: jlcpcb-parts-cli
description: Search JLCPCB parts for assembly; Basic-first tier selection, C-codes for the BOM.
license: GPL-3.0-only
tool-version: 1.1.0
---

# jlcpcb-parts-cli — JLCPCB assembly parts from the terminal

Read-only CLI over JLCPCB's unofficial parts-search API. Single-file Python
3.10+ (stdlib only). It never logs in, never mutates anything.

## When to use

- Picking components for a board that will go through JLCPCB Assembly.
- The user needs the JLC part number (C-code) for a BOM / KiCad
  "JLCPCB Part #" field.

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
  retail stock. For hand-buying use the companion `lcsc-cli`.
- Ambiguous keywords work, but exact MPNs give exact hits; prefer full MPNs.
- `info` accepts either a C-code (`C6186`) or an MPN (`AMS1117-3.3`).
- `search` reads up to five API pages; narrow very broad keywords if that cap
  is hit.

## Safety boundaries (hard rules)

- Never attempt login, cart, order, or account flows — the tool has none and
  must never gain any.
- Keep request volume modest: no bulk crawling beyond what `basic`/`export`
  already cache locally (24h cache under `~/.cache/jlcpcb-parts-cli/`).
- Payloads are volatile: treat any field as possibly missing; the client
  already degrades to `null` instead of crashing.
- If `check` fails, the endpoint moved or the schema changed: report it, then
  verify against https://jlcpcb.com/parts manually before code changes.

## Version check

This skill documents `jlcpcb-parts-cli` **1.1.0** (`tool-version` above).
Before relying on the command contract, run `jlcpcb-parts-cli --version`:

- **Match** → proceed.
- **Mismatch** → skill and tool have drifted apart; the command contract
  above may be wrong. Refresh both from the source before continuing:
  ```bash
  git -C <your-clone-dir> pull && ./install.sh
  # no clone yet? git clone https://github.com/obionar/jlcpcb-parts-cli.git && cd jlcpcb-parts-cli && ./install.sh
  ```
  Then re-run `--version` and reload this skill if it changed. Do not guess
  how an unknown version behaves — old flags may be gone or renamed.

## Install

```bash
git clone https://github.com/obionar/jlcpcb-parts-cli.git
cd jlcpcb-parts-cli && ./install.sh --skill-dir ~/.your-agent/skills
```

`./install.sh` alone installs only the CLI; the skill goes into ONE
explicitly passed skills dir — the agent integrating this tool passes its
own (e.g. `~/.claude/skills`, `~/.hermes/skills`).

No API keys, no configuration, no environment variables needed.
