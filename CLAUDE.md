# Arete

Turn a flat list into a MindNode mind map, via OPML import.

Named for the fishbone — the skeleton left when a fish is filleted, and the shape a mind map makes.

## Quick Commands

```bash
uv run --group dev pytest          # run tests
uv tool install . --force          # (re)install the CLI
arete --opml < list.txt            # convert without touching the app
```

## Module Map

Two directions. List → map is `outline` → `opml` (or `freemind`, with `--tags`) → `mindnode`. Map → Markdown prefers `shortcut` (MindNode's own exporter, reading the live
document) and falls back to `library` → `wire` → `snapshot` → `markdown` when no
export Shortcut is installed.

| Module | Role |
|--------|------|
| `outline` | Reading a pasted list into rows — indent inference, heading level as depth, bullet and rule stripping, single-root lifting. Pure, no I/O. |
| `opml` | Rendering rows as OPML — the default import format, text verbatim. Pure. |
| `freemind` | Rendering rows as FreeMind XML — the only import format that turns a trailing #tag into a real tag. Pure. |
| `library` | Read-only queries against MindNode's SQLite library: which documents exist, whether each can be trusted, where its snapshot is. |
| `mindnode` | Writing the temp file, opening it in the app, waiting for it to land, retrying once. |
| `wire` | A minimal protobuf wire-format reader. Knows nothing about MindNode. |
| `snapshot` | MindNode's snapshot layout → a `Node` tree, with invariants that refuse a tree we cannot trust. Pure. |
| `markdown` | A `Node` tree → nested Markdown bullets. Pure. |
| `shortcut` | Driving MindNode's own App Intents through Shortcuts — `export` for maps the snapshot cannot show, `append` for adding to an existing map. |
| `cli` | Argument parsing, input selection, reporting. |

## Key Conventions

**Stdlib only.** No runtime dependencies, and it should stay that way — this is a small tool that shells out to `open`. `pytest` is the only dev dependency.

**`opml.render` must not add a wrapper root.** MindNode creates the centre node itself from the *filename*, and hangs every top-level `<outline>` off it. Wrapping the list in a root element produces two centre nodes, one nested inside the other. This looks like a bug in MindNode and is not. Do not "fix" the missing root.

**Attribute escaping is deliberately stricter than `saxutils.escape`.** That function leaves quotes alone, which yields XML that looks correct and will not parse the moment a list contains a "quoted" word. `opml._attr` adds `"` and `'`. There is a test for each.

**Only the outermost list marker is stripped.** In `- 1. dedupe` the dash is decoration and the `1.` is the author's own numbering. Stripping both would quietly rewrite what someone wrote.

**Verification must never be able to break the import.** `library` returns `None` on any failure rather than raising, and `mindnode.import_opml` treats that as "unverified" and carries on. If MindNode relocates its library in a future version, the tool keeps working and only its reporting degrades.

**Tags are MindNode's parsing, not ours, and only FreeMind import does it.** Measured
2026-08-28 against MindNode 2026.4.8. The importers differ:

| Import format | Trailing `#word` |
|---|---|
| OPML | stays literal text |
| FreeMind (`.mm`) | becomes a real tag, and leaves the node title |
| plain text (`.txt`) | becomes a real tag (but each top-level line becomes its own root) |
| TaskPaper (`.taskpaper`) | refused: *"The file is not of a supported type"* despite `com.taskpaper.text` being declared in Info.plist |

MindNode consumes a trailing *run* of tag tokens and nothing else — `"two trailing #one #two"`
gives two tags, `"digits only #42"` tags `42`, while `"tag then word #one and"`, `"#leading
tag"` and `"C# programming"` are all left alone.

That is why `--tags` is **opt-in**: the same parsing silently eats the number out of a line
reading `"issue #42"`, which OPML preserves. Do not make FreeMind the default to save a flag.

**The snapshot field numbers are inferred, so `snapshot.read` guards them.** Nothing about
MindNode's format is documented; every field number in `snapshot.py` was recovered by walking
the wire format and checking the result against maps whose contents were known in advance. So
`read` asserts structural invariants — a known serialization version, exactly one root, every
node reachable from it — and raises `SnapshotError` rather than returning a tree it cannot
stand behind. Do not relax those checks to make a new file "work": a confidently wrong tree of
someone's thinking is far worse than an error.

**A snapshot is a base, not the current document — and no local signal reliably says how far
behind it is.** This is the limitation that matters most, and the first attempt at guarding it
was wrong. A map typed in the app accumulates CRDT operations against an all-but-empty
324-byte base snapshot. Gating on `operation_count == 0` looked sufficient, then decayed
within the hour: "My Areas of Focus" read 285 operations, then 0, while its snapshot was still
the empty template and MindNode's exporter returned 2 KB of content. arete duly reported the
map as a single node called "Mind Map" — the exact failure the guard existed to prevent.

Two changes came out of that. `snapshot.read` refuses any tree with a childless root, which
catches every empty base whatever its title or locale. And `--extract` now prefers MindNode's
own exporter, using the snapshot only when no export Shortcut is installed, because a
*stale-yet-populated* snapshot is undetectable from outside and the exporter reads the live
document. `--from-snapshot` forces the fast path for anyone who wants it.

**Appending is the one direction binning a document cannot undo, so it pre-flights.**
`do_append` confirms the map exists, the parent node exists, and the parent title is *unique*
before writing anything — the Shortcut matches parents by title, so a duplicate would attach
the list somewhere plausible and wrong. It also refuses a batch whose repeated titles have to
act as parents, and it re-reads the map afterwards to check it grew by exactly the number of
nodes added. Assert on the map, never on the Shortcut's account of itself.

**arete works over ssh, which is why the plugin is worth shipping to tube.** Measured
2026-08-28 from a non-interactive ssh session to the Mac's Tailscale IP: `shortcuts run` and
`open -a MindNode` both work, despite `launchctl managername` reporting `Background` rather
than `Aqua`. Two caveats — `~/.local/bin` is not on a non-interactive ssh PATH, so the CLI
needs an absolute path or an explicit export; and MindNode was already running, so the
no-GUI-session case is untested.

**The Shortcut fallback is a contract with something we do not own.** `shortcut.export`
promises only: text in (a map's title), text out (its Markdown). Everything else about that
Shortcut is the user's to build — `docs/export-shortcut.md` — so failures there must be
reported with the Shortcut's name and what it did wrong, never swallowed. Its output is passed
through untouched unless `--plain` is asked for, because reformatting someone's exported
thinking silently is worse than inconsistent bullets.

**Retry only on a confirmed miss.** `import_opml` retries exactly once, and only when the library was readable and showed no new document. Retrying blind would produce duplicate maps.

## What MindNode does, and how we found out

Measured 2026-08-28 against MindNode 2026.4.4 on macOS 27. These are app behaviours, so re-check them if it has moved.

- The centre node comes from the filename, not the OPML `<head><title>`.
- An import fired while another is still settling is dropped with no error, no dialog and nothing in `log show`. Waiting for the document to appear before returning is what makes back-to-back calls safe.
- An import identical to an existing map appears to be ignored. This confounds bisecting — vary the content whenever you vary anything else. It cost three false conclusions about filenames and temp directories before it was spotted.
- Documents are a protobuf CRDT operation log (hybrid logical clocks, peer IDs) in SQLite, CloudKit-synced. Read it; never write it.
- Sibling order is a fractional index — 200, 400, 600, 800, 1000 — so a node can be reordered without renumbering its siblings.
- MindNode's Markdown export uses an H1 for the centre, `##`/`###` for upper branches, then tab-indented `-` bullets, with tags inline as `#Important` and untitled nodes as bare `###`. A parser reading only indentation flattens a 93-node map to two levels, so `outline.parse` counts heading level as depth.
- `--extract X --plain | arete --stdin --title X --tags` is byte-identical *including tags*. Verified 2026-08-28 on a 23-line tagged map, both via the snapshot and via MindNode's exporter.
- FreeMind takes the document's name from the filename but its root node from the XML, so the two are independent — unlike OPML, where the root comes from the filename.
- MindNode's export renders a real tag and literal `#text` identically, so the export cannot tell you which is which. The snapshot decode can: a real tag is absent from the node title.

## Distribution

Shipped on the batterie marketplace since suite **1.79.0** (2026-08-28):
`claude plugin install arete@batterie`. `skills/mindnode-mapping/SKILL.md` here is the only
copy — the assembler vendors it, so edit here and let the daily run publish it. The
hand-deployed copy that used to sit in `~/.claude/skills/` is gone.

**Skill-only, deliberately.** No `instructions.md` and no SessionStart hook, because
`rules/*.md` loads unconditionally in every session on every machine and this tool is
symptom-triggered. The CLI stays a macOS-only `uv tool install`; the skill is the portable
half and documents the ssh route for sessions elsewhere.

**The plugin ships `skills/` but not `docs/`** — the assembler's skill-plugin copy-list is
`commands skills agents hooks scripts .mcp.json CLAUDE.md instructions.md`. So references to
the Shortcut setup guides are absolute GitHub URLs, not relative paths.

## Not done

**Replaying the operation log**, which would let `--extract` read maps typed in the app
without needing Shortcuts at all. The operations look like character-range text edits, so this
is a real CRDT replay whose failure mode is silent wrongness. The `shortcut` fallback covers
the same ground using MindNode's own exporter, so this may never be worth building — bon
`art-sidofe`.

**Batching the append.** `--append` runs the Shortcut once per node, which is simple and
correct but takes a second or two each. A looping Shortcut taking the whole list would be
faster; it was not worth the extra actions to hand-build up front.

**MindNode's MCP server** — dropped on purpose (Sameer, 2026-08-28). It cannot be enabled:
the autostart preference is reset by the app on launch and nothing listens. Its resource routes
are visible in the binary (`mindnode://documents/{documentID}/content/indented-list`) and would
be tidier than driving Shortcuts, but the App Intents route now covers both directions, so it
would buy nothing. The two-command re-check lives in the skill if it ever matters again.
