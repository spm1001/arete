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

| Module | Role |
|--------|------|
| `outline` | Reading a pasted list into rows — indent inference, bullet and rule stripping. Pure, no I/O. |
| `opml` | Rendering rows as OPML, with the attribute escaping MindNode's parser needs. Pure. |
| `library` | Best-effort read of MindNode's document library, so an import can be verified. |
| `mindnode` | Writing the temp file, opening it in the app, waiting for it to land, retrying once. |
| `cli` | Argument parsing, input selection (clipboard / file / stdin), reporting. |

## Key Conventions

**Stdlib only.** No runtime dependencies, and it should stay that way — this is a small tool that shells out to `open`. `pytest` is the only dev dependency.

**`opml.render` must not add a wrapper root.** MindNode creates the centre node itself from the *filename*, and hangs every top-level `<outline>` off it. Wrapping the list in a root element produces two centre nodes, one nested inside the other. This looks like a bug in MindNode and is not. Do not "fix" the missing root.

**Attribute escaping is deliberately stricter than `saxutils.escape`.** That function leaves quotes alone, which yields XML that looks correct and will not parse the moment a list contains a "quoted" word. `opml._attr` adds `"` and `'`. There is a test for each.

**Only the outermost list marker is stripped.** In `- 1. dedupe` the dash is decoration and the `1.` is the author's own numbering. Stripping both would quietly rewrite what someone wrote.

**Verification must never be able to break the import.** `library` returns `None` on any failure rather than raising, and `mindnode.import_opml` treats that as "unverified" and carries on. If MindNode relocates its library in a future version, the tool keeps working and only its reporting degrades.

**Retry only on a confirmed miss.** `import_opml` retries exactly once, and only when the library was readable and showed no new document. Retrying blind would produce duplicate maps.

## What MindNode does, and how we found out

Measured 2026-08-28 against MindNode 2026.4.4 on macOS 27. These are app behaviours, so re-check them if it has moved.

- The centre node comes from the filename, not the OPML `<head><title>`.
- An import fired while another is still settling is dropped with no error, no dialog and nothing in `log show`. Waiting for the document to appear before returning is what makes back-to-back calls safe.
- An import identical to an existing map appears to be ignored. This confounds bisecting — vary the content whenever you vary anything else. It cost three false conclusions about filenames and temp directories before it was spotted.
- Documents are a protobuf CRDT operation log (hybrid logical clocks, peer IDs) in SQLite, CloudKit-synced. Read it; never write it.

## The skill has two copies, on purpose (for now)

`skills/mindnode-mapping/SKILL.md` here is upstream. A **deployment copy** sits at
`~/.claude/skills/mindnode-mapping/SKILL.md`, because a skill only in a repo is never
loaded by any session — and this repo is not yet a marketplace plugin. Same relationship
a `rules/` shard has with its `instructions.md`: edit here, redeploy with `cp`.

When the marketplace entry lands, delete the deployed copy or sessions will see it twice.
Tracked as bon `art-sofoho`.

## Not done

MindNode 2026.4.4 ships a full MCP server (`MindNodeAutomationMCP`: `add_nodes`, `move_nodes`, `create_connection`, …) which would allow adding nodes to an *existing* map — the one thing OPML import cannot do. As of 2026-08-28 it cannot be enabled: the autostart preference is reset by the app on launch and nothing listens. See bon `art-` items and the `mindnode-mapping` skill for the re-check command.
