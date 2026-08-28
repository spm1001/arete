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

Two directions. List → map is `outline` → `opml` → `mindnode`. Map → Markdown is
`library` → `wire` → `snapshot` → `markdown`, falling back to `shortcut` when the
snapshot is not authoritative.

| Module | Role |
|--------|------|
| `outline` | Reading a pasted list into rows — indent inference, bullet and rule stripping. Pure, no I/O. |
| `opml` | Rendering rows as OPML, with the attribute escaping MindNode's parser needs. Pure. |
| `library` | Read-only queries against MindNode's SQLite library: which documents exist, whether each can be trusted, where its snapshot is. |
| `mindnode` | Writing the temp file, opening it in the app, waiting for it to land, retrying once. |
| `wire` | A minimal protobuf wire-format reader. Knows nothing about MindNode. |
| `snapshot` | MindNode's snapshot layout → a `Node` tree, with invariants that refuse a tree we cannot trust. Pure. |
| `markdown` | A `Node` tree → nested Markdown bullets. Pure. |
| `shortcut` | Driving MindNode's own exporter through a Shortcut, for maps the snapshot cannot show. |
| `cli` | Argument parsing, input selection, reporting. |

## Key Conventions

**Stdlib only.** No runtime dependencies, and it should stay that way — this is a small tool that shells out to `open`. `pytest` is the only dev dependency.

**`opml.render` must not add a wrapper root.** MindNode creates the centre node itself from the *filename*, and hangs every top-level `<outline>` off it. Wrapping the list in a root element produces two centre nodes, one nested inside the other. This looks like a bug in MindNode and is not. Do not "fix" the missing root.

**Attribute escaping is deliberately stricter than `saxutils.escape`.** That function leaves quotes alone, which yields XML that looks correct and will not parse the moment a list contains a "quoted" word. `opml._attr` adds `"` and `'`. There is a test for each.

**Only the outermost list marker is stripped.** In `- 1. dedupe` the dash is decoration and the `1.` is the author's own numbering. Stripping both would quietly rewrite what someone wrote.

**Verification must never be able to break the import.** `library` returns `None` on any failure rather than raising, and `mindnode.import_opml` treats that as "unverified" and carries on. If MindNode relocates its library in a future version, the tool keeps working and only its reporting degrades.

**The snapshot field numbers are inferred, so `snapshot.read` guards them.** Nothing about
MindNode's format is documented; every field number in `snapshot.py` was recovered by walking
the wire format and checking the result against maps whose contents were known in advance. So
`read` asserts structural invariants — a known serialization version, exactly one root, every
node reachable from it — and raises `SnapshotError` rather than returning a tree it cannot
stand behind. Do not relax those checks to make a new file "work": a confidently wrong tree of
someone's thinking is far worse than an error.

**A snapshot is a base, not the current document.** This is the limitation that matters most.
A map created by import gets a complete snapshot and zero operations. A map *typed in the app*
accumulates CRDT operations against an all-but-empty 324-byte base snapshot — so reading only
the snapshot reports a map with one blank node called "Mind Map". `library.Document`
.`snapshot_is_authoritative` is false whenever `operation_count > 0`, and `--extract` refuses
outright in that case. Extraction would need the operation log replayed, which is not built.

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
- Sibling order is a fractional index — 200, 400, 600, 800, 1000 — so a node can be reordered without renumbering its siblings. Decoding it reproduced a known map's order exactly at every level.
- `--extract X --plain | arete --stdin --title X` is byte-identical on a snapshot-authoritative map. Verified 2026-08-28 on a 23-line map.

## The skill has two copies, on purpose (for now)

`skills/mindnode-mapping/SKILL.md` here is upstream. A **deployment copy** sits at
`~/.claude/skills/mindnode-mapping/SKILL.md`, because a skill only in a repo is never
loaded by any session — and this repo is not yet a marketplace plugin. Same relationship
a `rules/` shard has with its `instructions.md`: edit here, redeploy with `cp`.

When the marketplace entry lands, delete the deployed copy or sessions will see it twice.
Tracked as bon `art-sofoho`.

## Not done

**Replaying the operation log**, which would let `--extract` read maps typed in the app
without needing Shortcuts at all. The operations look like character-range text edits, so this
is a real CRDT replay whose failure mode is silent wrongness. The `shortcut` fallback covers
the same ground using MindNode's own exporter, so this may never be worth building — bon
`art-sidofe`.

**`CreateNodeIntent`**, which would let nodes be added to an *existing* map — the other thing
OPML import cannot do. The intent is there, with `childOf` / `siblingAfter` placement; only the
export half of the App Intents route is wired up. Tracked as bon `art-kenosa`.

**MindNode's MCP server** (`MindNodeAutomationMCP`: `add_nodes`, `move_nodes`,
`create_connection`, …). As of 2026-08-28 it cannot be enabled: the autostart preference is
reset by the app on launch and nothing listens. Its resource routes are visible in the binary
(`mindnode://documents/{documentID}/content/indented-list`) and would be the cleanest
extraction path of all. See bon `art-vonowu` for the re-check command.
