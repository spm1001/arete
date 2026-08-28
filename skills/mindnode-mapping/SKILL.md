---
name: mindnode-mapping
description: Orchestrates moving lists in and out of MindNode with the `arete` CLI — required before hand-building a map node by node, writing OPML by hand, or reading MindNode library files. A 3-step convert-import-verify workflow one way and a guarded snapshot decode the other, catching the silent behaviours that sink hand-rolled attempts. Triggers on 'paste this list into MindNode', 'make a mind map from these', 'get this map as markdown', 'export my mind map', 'mindnode file format', 'arete'. (user)
---

# MindNode mapping

MindNode goes both ways with one command each. The work is knowing which route is real, because the obvious two are dead ends: pasting a multi-line list produces one node containing line breaks, and the library format is not something to write by hand.

```bash
pbpaste | arete --stdin --title "Q3 themes"   # list  -> map
arete --extract "Q3 themes"                    # map   -> Markdown
```

That is usually the whole job. The rest of this exists because MindNode's importer is silent when it declines — and a silent decline is the kind you report as success.

## When to use

- Someone has a list — pasted, in a file, on the clipboard — and wants it as a mind map
- An outline needs to become a map with branches
- Someone asks how MindNode's file format works, or wants to write one directly
- MindNode "won't let me paste" a list
- A map needs to come back out as Markdown, an outline, or text

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
| `arete --tags` | Import via FreeMind, so a trailing `#tag` becomes a real MindNode tag |
| `arete --append --into MAP --under NODE` | Add the list under a node of a map that already exists |
| `arete --list` | Every map MindNode holds, and whether each can be read out |
| `arete --extract NAME` | That map as Markdown — an H1 for the centre, nested bullets below |
| `arete --extract NAME --plain` | Bullets only, so it feeds straight back in |

Extract and import are inverses: `arete --extract X --plain | arete --stdin --title X --tags` reproduces the map byte-for-byte, tags included. That works because the root is never emitted as a bullet — MindNode mints the centre node from the document name on import, so a root bullet would come back a level deeper every cycle.

Indentation carries hierarchy. The indent unit is inferred from the list itself, so tabs, two spaces and four spaces all work, including mixed in one paste — which is exactly what a list assembled from two sources looks like. Bullets and numbering are stripped; horizontal rules are dropped.

Exit status is 0 only when the map was seen to land. A non-zero exit means it genuinely did not import, and the message carries the path to the OPML so it can be opened by hand.

## What MindNode does that will surprise you

Each of these cost a real debugging round on 2026-08-28 against MindNode 2026.4.4. They are properties of the app, so re-check them if it has moved on.

**The centre node comes from the *filename*, not from the OPML `<head><title>`.** MindNode creates a root node itself and hangs every top-level `<outline>` off it. So an OPML that wraps its list in a root element of its own produces *two* centre nodes, one inside the other. This is the single most likely mistake when hand-writing OPML, and it looks like a MindNode bug rather than yours. `arete` writes a temp file named after the title for this reason.

**An import fired while another is still settling is dropped in silence.** No error, no dialog, nothing in `log show`. The document simply never appears. `arete` waits for the document to show up in the library and retries once if it did not, which is also why calling it twice in a row is safe — the first call does not return until its map has landed.

**MindNode appears to ignore an import identical to an existing map.** Re-importing the same content produced nothing on three consecutive tries. This confounds bisecting: a test that re-imports the same file to vary something else will read as a failure of the thing being varied. Vary the content whenever you vary anything else.

**A dropped import and a rejected one look the same from outside** — both are silence. Check the library rather than the app window; `arete` does this for you.

## Adding to a map that already exists

Import always mints a *new* document, so `--append` goes through MindNode's `CreateNodeIntent`
instead, driven by a second hand-built Shortcut ([docs/append-shortcut.md](https://github.com/spm1001/arete/blob/main/docs/append-shortcut.md)). It adds one node
per Shortcut run, walking the list top-down so a parent always exists before its children.

Working since 2026-08-28, three levels deep. Because the Shortcut matches parents **by title**, `--append` pre-flights before writing
anything: the map must exist, the `--under` node must exist, and its title must be *unique* in
that map. It also refuses a batch whose repeated titles would have to act as parents, and
re-reads the map afterwards to check it grew by exactly the number of nodes added. Appending is
the one direction that binning a document cannot undo, which is why it checks first and
verifies after rather than trusting the Shortcut's exit code.

**Building that Shortcut has one trap worth carrying.** An index field you have not typed into
shows a greyed placeholder `1` indistinguishable from a real value, and an unset index resolves
to **0** — producing *"You asked for item 0, but the first item is at index 1"* against an action
whose box plainly reads 1. Three rounds of debugging went elsewhere before the literal reading
won. `~/Library/Shortcuts/Shortcuts.sqlite` holds what a Shortcut actually contains (actions in
`ZSHORTCUTACTIONS.ZDATA`, a bplist); the canvas is not authoritative. Reach for it whenever a
Shortcut looks right and behaves wrong.

## Running it from another machine

`arete` drives a Mac app, but it does **not** need an interactive Mac session. Measured
2026-08-28 from a non-interactive ssh session to the Mac's Tailscale IP: both `shortcuts run`
and `open -a MindNode` work, even though `launchctl managername` reports `Background` rather
than `Aqua`. So a session on another machine can do this:

```bash
ssh sameer-macbook-air 'export PATH="$HOME/.local/bin:$PATH"; arete --extract "Q3 themes"'
```

Two things bite. **`~/.local/bin` is not on a non-interactive ssh PATH**, so the CLI needs an
absolute path or that explicit export. And the Mac's sshd accepts **Tailscale addresses only** —
`ssh localhost` is refused by design, so use the Tailscale name or IP. MindNode was already
running when this was measured; whether `open -a` can launch it with no GUI session at all is
untested.

## Tags: only FreeMind import creates them, and it is opt-in

Tags are MindNode's own text parsing, not arete's, and the importers disagree about it.
Measured 2026-08-28 against MindNode 2026.4.8:

| Import format | A trailing `#word` |
|---|---|
| OPML — arete's default | stays as literal text |
| FreeMind `.mm` — `arete --tags` | becomes a real tag, and leaves the node title |
| plain text `.txt` | becomes a real tag, but each top-level line becomes its own root map |
| TaskPaper `.taskpaper` | **refused at runtime** — *"The file is not of a supported type"* — even though `com.taskpaper.text` is declared in MindNode's Info.plist. Declared is not honoured. |

MindNode eats a trailing *run* of tag tokens and nothing else:

```
"ends with #tag"          -> "ends with"     + tag: tag
"two trailing #one #two"  -> "two trailing"  + tags: one, two
"unicode tag #Café"       -> "unicode tag"   + tag: Café
"tag then word #one and"  -> unchanged, no tags
"#leading tag"            -> unchanged, no tags
"C# programming"          -> unchanged, no tags
```

**Why `--tags` is opt-in rather than the default:** the same parsing silently eats the number
out of a list item reading `"issue #42"` or `"Sprint #3"`. OPML preserves that text verbatim.
Reach for `--tags` when a list is meant to carry tags, not by reflex.

**Telling a real tag from literal text.** MindNode's Markdown export renders both as
`#Important`, so the export cannot discriminate. The snapshot decode can: a real tag is
*absent* from the node's title, because it is stored separately. That is the check to run when
it matters.

## Extraction reads a snapshot, and a snapshot is only a base

**The limitation that matters most, and the guard that was not enough.** A map typed in the app
keeps its content in a CRDT operation log against an all-but-empty 324-byte base snapshot, so
reading the snapshot alone reports one blank node called "Mind Map".

Gating on "no pending operations" seemed sufficient and then decayed within the hour: one map
read 285 operations, then 0, while its snapshot was still the empty template and MindNode's
exporter returned 2 KB of content. arete reported that map as empty — the exact failure the
guard existed to prevent. **Operation count reaching zero is not evidence the snapshot is
current.** A stale-yet-populated snapshot cannot be detected from the library at all.

So `--extract` now prefers MindNode's own exporter, which reads the live document, and
`snapshot.read` refuses any tree whose root has no children.

For those maps `--extract` falls back to **MindNode's own exporter**, driven through a
Shortcut, which always sees the live document. That Shortcut has to be built once by hand —
[docs/export-shortcut.md](https://github.com/spm1001/arete/blob/main/docs/export-shortcut.md) in the arete repo has the steps — and `arete --list` says whether it
is installed. Without it, export by hand: **File > Export > Markdown Text**.

Replaying the operation log would remove the Shortcut dependency, but the operations are
character-range text edits and a subtly wrong CRDT replay fails silently, so the exporter is
the better bet.

## MindNode's App Intents — the supported route to both gaps

`/Applications/MindNode.app/Contents/Resources/Metadata.appintents` lists 20 intents, and two
of them cover exactly what `arete` cannot do:

- **`ExportDocumentIntent`** takes an `exportType` of `markdown` (also `plainText`,
  `taskPaper`, `opml`-ish `mindnode`, `pdf`, `png`, `svg`). MindNode's own exporter, so it
  sees the live document, operation log and all.
- **`CreateNodeIntent`** takes a `createType` of `mainNode` / `parentOf` / `childOf` /
  `siblingAfter` / `siblingBefore` — so nodes **can** be added to an existing map, which OPML
  import cannot do.

There is no supported way to invoke an app intent straight from a shell. The route is one
Shortcut built by hand in Shortcuts.app, after which `shortcuts run "<name>"` is scriptable.

**The export half is wired up already**: build a Shortcut called `Arete Export` that takes a
map's name as text and returns its Markdown, and `arete --extract` uses it automatically for
exactly the maps the snapshot cannot show. Steps: [docs/export-shortcut.md](https://github.com/spm1001/arete/blob/main/docs/export-shortcut.md). Override the name
with `--shortcut NAME`.

**`CreateNodeIntent` is not wired up** — that is the route to appending to an existing map,
and it remains the one thing arete cannot do.

Read the intents and their parameters with:

```bash
python3 -c "import json,pathlib;d=json.loads(pathlib.Path('/Applications/MindNode.app/Contents/Resources/Metadata.appintents/extract.actionsdata').read_text());print('\n'.join(sorted(d['actions'])))"
```

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
| Reading a 324-byte snapshot as an empty map | It is a base; the content is in the operation log | Check `--list`, or use MindNode's export |
| Emitting the root as a bullet on extract | Each round trip adds a level | Root is the H1 only; children start at the margin |

## Integration

- Verifying an import reads MindNode's library directly; if MindNode relocates it, verification degrades to "unknown" and the import still runs. It must never be able to break the tool it checks.
- Repo, tests and work tracker: [spm1001/arete](https://github.com/spm1001/arete), bon prefix `art`.
- **Installing the CLI.** The plugin ships this skill everywhere; the `arete` command is macOS-only and installs separately: `uv tool install ~/repos/spm1001/arete` (clone it first). A session on another machine reaches a Mac over ssh — see above.

This covers the common cases, not every case. Where something here does not fit what you are seeing, reason from the whys — the importer is silent on failure, the filename is the root, and the library is an operation log — rather than from the letter of the table.
