# jlcpcb-parts-cli

**Unofficial, read-only command-line client for the JLCPCB parts library.**
Not affiliated with JLCPCB. It queries the same public JSON endpoint the
jlcpcb.com parts pages use — no HTML scraping, no login, no cart or order
actions.

## Why this exists

When you design a board for JLCPCB Assembly, part choice dominates cost and
lead time. JLCPCB groups assembly parts into tiers:

1. **Basic** — no extra placement fee
2. **Promotional Extended** — no feeder loading fee in Economic PCBA
3. **Extended** — fees apply; use only when 1–2 have no match

The website does not let you search with tier priority from the terminal, and
BOM tools want JLCPCB part numbers (C-codes), not web pages. This script was
built for a terminal-first hardware workflow (and for AI agents helping pick
parts) where you type an MPN and get the C-code, tier, stock, and price
immediately, Basic-first.

## Install

Python 3.10+ standard library only — no pip, no venv, no dependencies.

```bash
git clone https://github.com/obionar/jlcpcb-parts-cli.git
cd jlcpcb-parts-cli && ./install.sh
```

This installs the CLI to `~/.local/bin`. To also install the bundled
agent skill (`skill/jlcpcb-parts-cli/SKILL.md`, AgentSkills-compatible),
pass your agent's skills dir explicitly:
`./install.sh --skill-dir ~/.claude/skills` — skills are never
auto-installed into every agent found; each agent integrates the skill
itself when you ask it to. `--uninstall` removes both. Manual CLI-only
alternative:

```bash
cp jlcpcb-parts-cli/jlcpcb-parts-cli ~/.local/bin/
chmod +x ~/.local/bin/jlcpcb-parts-cli
```

That's it — the script is a single self-contained file. (Any directory on
`PATH` works; make sure it stays executable.)

### Install as an agent skill

If you use an AI agent with shell access (Hermes, OpenClaw, Claude Code, …),
you don't need to install anything yourself. Paste the repository URL into the
agent chat and ask it to install the tool as a skill, e.g.:

> https://github.com/obionar/jlcpcb-parts-cli — install this as a skill:
> copy the script to ~/.local/bin (chmod +x), read AGENTS.md and follow it.

The repository's `AGENTS.md` contains everything the agent needs: command
contract, JSON output shape, and usage boundaries.

## Commands

| command | what it does |
|---|---|
| `jlcpcb-parts-cli search <keyword>` | free-text search across the whole library; results sorted Basic → Promo-Ext → Ext, then stock |
| `search --tier basic` | keep only Basic hits |
| `search --min-stock N` | drop low/no-stock hits |
| `jlcpcb-parts-cli basic` | browse the full Basic & Promotional Extended pool (cached 24h under `~/.cache/jlcpcb-parts-cli/`) |
| `basic --category X` | substring filter on category (e.g. `regulator`, `capacitor`, `mcu`) |
| `basic --list-categories` | list categories present in the pool |
| `basic --refresh` | force cache refetch |
| `jlcpcb-parts-cli info <C-code or MPN>` | full detail: tier, stock, price, datasheet, product URL |
| `jlcpcb-parts-cli check` | canary probe for API/schema drift (exit 0/1/2 = PASS/WARN/FAIL) — see below |
| `jlcpcb-parts-cli export [-o out.md]` | dump the Basic & Promo pool to a Markdown reference |
| `--json` (global, before subcommand) | machine-readable output for piping and agents |
| `--version` | print version |

### Examples

```bash
jlcpcb-parts-cli search STM32F103C8T6
jlcpcb-parts-cli --json search AMS1117-3.3 | jq '.[0].code'
jlcpcb-parts-cli info C6186
jlcpcb-parts-cli basic --category regulator
```

`search` reads additional pages when client-side tier or stock filters remove
early hits, up to five API pages per command. Narrow very broad keywords if
that safety cap is reached before `-n` matches are found.

## Output columns

`TIER | CODE (JLCPCB part number, e.g. C6186) | MPN | PKG | STOCK | PRICE@1 | description`

The `CODE` value is what you put into your BOM / KiCad "JLCPCB Part #" field.

## How tiers are determined

The API has no explicit tier field. The client derives it client-side
(verified 2026-08-22, see `tests/fixtures/NOTES.md`):

- `componentLibraryType == "base"` → Basic
- `expand` + `preferredComponentFlag == true` → Promotional Extended
- otherwise → Extended

Tier labels can change on JLCPCB's side; always re-check critical parts near
order time.

## Anomaly detection (`check`)

The API is unofficial and can change silently. The client defends itself at
two levels:

**Inline (every command):** transient network errors are retried 3× with
backoff; schema-level anomalies raise `PayloadError` immediately (no retry)
with a message pointing at the website; soft anomalies (unknown library type,
missing MPN, non-numeric stock) are reported as warnings on stderr while JSON
stdout remains machine-readable.

**Canary (`check` subcommand):** probes known-answer parts (C8734, C6186) and
verifies part found, tier unchanged, stock above threshold. Exit codes:
`0` = PASS, `1` = WARN (part found but tier/stock drifted), `2` = FAIL (API
unusable / canary parts missing). Suitable for cron watchdogs:

```
0 8 * * 1  jlcpcb-parts-cli check || echo "jlcpcb-parts-cli check failed (exit $?)"
```

## Using with AI agents

No manual setup needed. Paste this repository's URL into your agent chat
(Hermes, OpenClaw, Claude Code, …) and ask it to install the tool as a skill:

> https://github.com/obionar/jlcpcb-parts-cli — install this as a skill:
> copy the script to ~/.local/bin (chmod +x), read AGENTS.md and follow it.

`AGENTS.md` in this repository contains integration guidance for coding
agents — command contracts, JSON output shape, and boundaries. With it, an
agent can use this tool as a skill with minimal prompt overhead.

## Tests

```bash
python3 -m unittest discover tests -v
```

Offline only — tests run against minimal synthetic JSON fixtures, no live
requests or redistributed vendor payloads.

## Boundaries

Read-only and unofficial: no login, no cart/order automation, modest request
rates, local cache instead of repeated full-list fetches. JLCPCB can change
the endpoint at any time; `check` tells you when that happened. Use
respectfully and at your own risk.

Before publishing or operating this client for others, obtain JLCPCB's written
approval or migrate it to an approved official Parts API integration. This
repository does not grant permission to use or redistribute vendor data.

## Related tools

- **[lcsc-cli](https://github.com/obionar/lcsc-cli)** — companion tool: LCSC.com
  search plus JLC-vs-LCSC availability `compare`, for parts JLCPCB Assembly
  doesn't carry (manual sourcing / hand-soldering).

## License

GPL-3.0-only — see [LICENSE](LICENSE).
