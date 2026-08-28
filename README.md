# Arête

**Move lists in and out of MindNode.**

MindNode won't paste a multi-line list as separate nodes — you get one node containing twenty lines. There's no setting for it. Arête goes both ways instead:

```bash
pbpaste | arete --stdin --title "Q3 themes"          # list  → new map
arete --extract "Q3 themes"                          # map   → Markdown
arete --append --into "Q3 themes" --under "Risks"    # add to a map you already have
arete --list                                         # what MindNode holds
```

Named for the fishbone — the spine left when you fillet a fish, which is the shape a mind map makes.

## Install

```bash
uv tool install git+https://github.com/spm1001/arete        # the CLI (macOS)
claude plugin install arete@batterie                        # the skill, for Claude Code
```

The CLI drives the MindNode desktop app, so it wants a Mac. It does **not** want an interactive one — both directions work over ssh, so a session on another machine can reach a Mac across a tailnet.

## The two Shortcuts

Reading maps back out, and appending to them, go through MindNode's App Intents — which cannot be invoked from a shell. Two small Shortcuts bridge the gap, and both are in [`shortcuts/`](shortcuts/), signed and ready to import:

| File | Gives you |
|---|---|
| `Arete Export.shortcut` | `--extract` on every map, including ones typed in the app |
| `Arete Append.shortcut` | `--append` |

Download, double-click, keep the names. [`docs/export-shortcut.md`](docs/export-shortcut.md) and [`docs/append-shortcut.md`](docs/append-shortcut.md) describe them action by action if you'd rather build or audit them by hand — and record what went wrong the first time, which was more than you'd expect.

Without the export Shortcut, `--extract` falls back to decoding MindNode's library snapshot directly. That needs nothing installed and is exact for imported maps; it refuses, rather than guessing, on maps it can't read reliably.

## Hierarchy, and tags

Indentation makes the hierarchy — tabs, two spaces, four, or a mix; the unit is inferred from the list itself. Markdown heading levels count as depth too, so MindNode's own export feeds straight back in. Bullets, numbering and horizontal rules are stripped.

`--tags` turns a trailing `#tag` into a real MindNode tag. It's opt-in because the same parsing eats the number out of `issue #42` — a lost capability is recoverable, lost text isn't.

Extract and import are genuine inverses:

```bash
arete --extract X --plain | arete --stdin --title X --tags   # byte-identical, tags included
```

## Why it checks so much

MindNode fails quietly. An import fired while another is settling is dropped with no error; a map typed in the app can read as a single blank node; an OPML file wrapped in its own root produces two centre nodes. So arête verifies against the app rather than trusting an exit code — it waits for each map to appear before returning, refuses a snapshot it can't stand behind, and re-reads a map after appending to confirm it grew by exactly the number of nodes sent.

## Development

```bash
uv run --group dev pytest              # 147 tests, stdlib only
uv run --script scripts/export-shortcuts.py   # re-export the Shortcuts after editing them
```

MIT. Part of [Batterie de Savoir](https://github.com/spm1001/batterie-de-savoir).
