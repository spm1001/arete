---
name: mindnode-mapping
description: Orchestrates turning a list into MindNode nodes with the `arete` CLI — required before hand-building a map node by node, writing OPML by hand, or editing MindNode library files. A 3-step convert-import-verify workflow that catches the two silent behaviours which sink hand-rolled attempts. Triggers on 'paste this list into MindNode', 'make a mind map from these', 'turn this outline into a map', 'mindnode file format', 'arete'. (user)
---

# MindNode mapping

Getting a list into MindNode is a solved problem with one command. The work is knowing which route is real, because the obvious two are dead ends: pasting a multi-line list produces one node containing line breaks, and the library format is not something to write by hand.

```bash
pbpaste | arete --stdin --title "Q3 themes"
```

That is usually the whole job. The rest of this exists because MindNode's importer is silent when it declines — and a silent decline is the kind you report as success.

## When to use

- Someone has a list — pasted, in a file, on the clipboard — and wants it as a mind map
- An outline needs to become a map with branches
- Someone asks how MindNode's file format works, or wants to write one directly
- MindNode "won't let me paste" a list

## Boundaries

- **macOS only.** It drives the desktop app through `open -a MindNode`.
- **Import always creates a *new* document.** There is no supported route for adding nodes to a map that already exists. If that is what is wanted, say so plainly rather than producing a second map and hoping it passes.
- Editing an existing map, styling, themes and layout are all out of scope — those are the app's job.

## CLI reference

| Command | Does |
|---|---|
| `arete` | Clipboard → new map, opened in MindNode |
| `arete notes.md` | A file instead; the filename becomes the default title |
| `arete --stdin` | Read from a pipe |
| `arete --title "Name"` | Set the centre node and the document name |
| `arete --opml > out.opml` | Just the OPML — does not touch the app |
| `arete --tab-stop N` | Columns a tab counts for when reading indentation (default 4) |
| `arete --timeout S` | How long to wait for the map to appear (default 12s) |

Indentation carries hierarchy. The indent unit is inferred from the list itself, so tabs, two spaces and four spaces all work, including mixed in one paste — which is exactly what a list assembled from two sources looks like. Bullets and numbering are stripped; horizontal rules are dropped.

Exit status is 0 only when the map was seen to land. A non-zero exit means it genuinely did not import, and the message carries the path to the OPML so it can be opened by hand.

## What MindNode does that will surprise you

Each of these cost a real debugging round on 2026-08-28 against MindNode 2026.4.4. They are properties of the app, so re-check them if it has moved on.

**The centre node comes from the *filename*, not from the OPML `<head><title>`.** MindNode creates a root node itself and hangs every top-level `<outline>` off it. So an OPML that wraps its list in a root element of its own produces *two* centre nodes, one inside the other. This is the single most likely mistake when hand-writing OPML, and it looks like a MindNode bug rather than yours. `arete` writes a temp file named after the title for this reason.

**An import fired while another is still settling is dropped in silence.** No error, no dialog, nothing in `log show`. The document simply never appears. `arete` waits for the document to show up in the library and retries once if it did not, which is also why calling it twice in a row is safe — the first call does not return until its map has landed.

**MindNode appears to ignore an import identical to an existing map.** Re-importing the same content produced nothing on three consecutive tries. This confounds bisecting: a test that re-imports the same file to vary something else will read as a failure of the thing being varied. Vary the content whenever you vary anything else.

**A dropped import and a rejected one look the same from outside** — both are silence. Check the library rather than the app window; `arete` does this for you.

## The file format, and why not to write it

If asked to edit MindNode documents directly, the answer is don't, and here is the reason rather than a flat refusal.

Documents live in `~/Library/Containers/com.ideasoncanvas.mindnode/Data/Library/Application Support/MindNode/production-v1_0/MindNode Library.mindnodelibrary/`, in a SQLite database. The rows are not a mind map. They are a **CRDT operation log**: protobuf-encoded edits, each stamped with a hybrid logical clock and a peer ID, replayed to reconstruct the document, with CloudKit syncing the result across devices. Writing into it means forging clock values and peer identities that the sync engine will then disagree with, on a corpus of someone's real thinking.

Reading it is fine and useful — that is how `arete` verifies an import landed. `src/arete/library.py` opens a *copy* of the database, including its write-ahead log, without which a just-finished import is invisible.

The custom clipboard types (`com.ideasoncanvas.mindnode.canvasObjects`, `…codableCanvas`) are the same encoding on a different transport, so synthesising a paste is the same dead end wearing a hat.

## MindNode's own MCP server

MindNode 2026.4.4 ships a complete MCP server — `MindNodeAutomationMCP`, with tools including `add_nodes`, `move_nodes`, `remove_nodes`, `create_connection` and `update_content`. It would beat OPML on the one thing OPML cannot do, which is adding nodes to a map already open.

**As of 2026-08-28 it cannot be switched on.** Setting `MNDefaultsMCPServerShouldAutoStartOnLaunch` to true is reset to 0 by the app on next launch, nothing listens on any port, and no token is minted in the Keychain. Whether that is a MindNode Plus gate or an unreleased feature is undetermined. The app ships with the `com.apple.security.network.server` entitlement and the full settings UI exists in the binary, so it is built and waiting for a switch.

Re-check in one command before repeating any of this:

```bash
defaults read com.ideasoncanvas.mindnode MNDefaultsMCPServerShouldAutoStartOnLaunch
lsof -nP -iTCP -sTCP:LISTEN -a -p "$(pgrep -x MindNode)"
```

If a listener appears, the MCP route is live and is the better one — prefer it over OPML for anything touching an existing map.

## Common mistakes

| Mistake | What happens | Instead |
|---|---|---|
| Wrapping the OPML list in a root `<outline>` | Two centre nodes, nested | No wrapper; the filename is the root |
| `xml.sax.saxutils.escape` for attributes | Quotes unescaped, XML will not parse | Escape `"` and `'` too |
| Reporting success because `open` returned 0 | `open` reports the launch, not the import | Check the library for a new document |
| Re-importing identical content while testing | Reads as a failure of whatever else you changed | Vary the content every time |
| Deleting test maps via SQLite | Fights CloudKit | Bin them in the app |
| Assuming the head `<title>` names the map | It names nothing visible | The filename names the map |

## Integration

- Verifying an import reads MindNode's library directly; if MindNode relocates it, verification degrades to "unknown" and the import still runs. It must never be able to break the tool it checks.
- Repo, tests and work tracker: `~/repos/spm1001/arete`, bon prefix `art`.

This covers the common cases, not every case. Where something here does not fit what you are seeing, reason from the whys — the importer is silent on failure, the filename is the root, and the library is an operation log — rather than from the letter of the table.
