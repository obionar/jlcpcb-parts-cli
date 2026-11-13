# jlcpcb-parts-cli

Unofficial, read-only CLI for the JLCPCB Assembly parts library. Search by MPN or C-code and get tier, stock, price, datasheet and the part number needed for a BOM. No login, cart or order actions.

## Why use it

JLCPCB Assembly tiers affect cost:

1. **Basic** — no extra placement fee.
2. **Promotional Extended** — no feeder loading fee in Economic PCBA.
3. **Extended** — fees apply.

Results are sorted Basic → Promotional Extended → Extended, then stock. JLC assembly stock is not LCSC retail stock.

## Install

Python 3.10+ standard library only; no dependencies.

Ask your agent:

> Download https://github.com/obionar/jlcpcb-parts-cli and integrate it. Copy the executable to my chosen bin directory (default `~/.local/bin`) and the skill to `~/.agents/skills/jlcpcb-parts-cli`.

Manual equivalent:

```bash
git clone https://github.com/obionar/jlcpcb-parts-cli.git
cd jlcpcb-parts-cli
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR" "$HOME/.agents/skills/jlcpcb-parts-cli"
cp jlcpcb-parts-cli "$BIN_DIR/jlcpcb-parts-cli"
chmod 755 "$BIN_DIR/jlcpcb-parts-cli"
cp skill/jlcpcb-parts-cli/SKILL.md "$HOME/.agents/skills/jlcpcb-parts-cli/SKILL.md"
```

Set `BIN_DIR` to another `PATH` directory if desired. To update, pull and repeat the copies. There is no installer or agent auto-detection.

## Commands

| Command | Purpose |
|---|---|
| `jlcpcb-parts-cli search <keyword>` | Search all parts, Basic-first |
| `search --tier basic\|promo\|extended\|any` | Filter by tier |
| `search --min-stock N` | Filter by assembly stock |
| `jlcpcb-parts-cli basic [--category X]` | Browse the cached Basic + Promo pool |
| `basic --list-categories` | List available categories |
| `basic --refresh` | Refresh the 24-hour cache |
| `jlcpcb-parts-cli info <C-code or MPN>` | Exact part detail |
| `jlcpcb-parts-cli check [--timeout S]` | Check API/schema health |
| `jlcpcb-parts-cli export [-o out.md] [--refresh]` | Export the Basic + Promo pool |

`--json` is global and goes before the subcommand. Use `--version` to check the tool version.

### Examples

```bash
jlcpcb-parts-cli search STM32F103C8T6
jlcpcb-parts-cli --json search AMS1117-3.3 | jq '.[0].code'
jlcpcb-parts-cli info C6186
jlcpcb-parts-cli basic --category regulator
```

`search` and `info` read at most five pages. If `info` exceeds that cap, availability is unknown and the command errors instead of reporting a false no-match. Full-pool export/browse stops with an error after 100 pages. An empty API pool never replaces an existing cache.

## Output and tiers

Text output shows `TIER`, JLCPCB `CODE`, `MPN`, package, stock, price@1 and description. Put `CODE` in the BOM/KiCad `JLCPCB Part #` field.

The API has no explicit tier field, so the client derives it:

- `componentLibraryType == "base"` → Basic
- `expand` plus `preferredComponentFlag == true` → Promotional Extended
- everything else → Extended

Re-check important parts near order time; stock, prices and tiers can change.

## Reliability and tests

Transient network errors are retried three times. Payload anomalies produce warnings or clear errors. `check` returns `0` PASS, `1` WARN, `2` FAIL.

```bash
python3 -m unittest discover tests -v
```

Tests are offline and use minimal synthetic fixtures.

## Boundaries

Read-only and unofficial. Keep request volume modest; no login, cart, orders or account automation. Before operating this client for others, obtain JLCPCB's written approval or use an approved official API. This repository does not grant permission to redistribute vendor data.

Related: [lcsc-cli](https://github.com/obionar/lcsc-cli) for LCSC retail search and JLC/LCSC comparison.

License: GPL-3.0-only — see [LICENSE](LICENSE).
