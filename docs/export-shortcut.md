# The export Shortcut

`arete --extract` prefers MindNode's own exporter, because it reads the **live** document and is therefore right by construction. Reaching it means one Shortcut, built once by hand: `ExportDocumentIntent` is an App Intent, and there is no supported way to call an app intent straight from a shell.

Without that Shortcut, `arete` falls back to decoding MindNode's base snapshot from the library. That needs nothing installed and is exact when the snapshot is current — but a snapshot is only a *base*, and nothing in the library reliably says how far behind it is. On 2026-08-28 a map showed 285 pending operations, then 0 an hour later, while its snapshot was still the empty 324-byte template and MindNode's exporter returned 2 KB of real content. `arete` refuses a snapshot that decodes to a single childless node for exactly that reason, but a *stale-yet-populated* snapshot is undetectable from outside.

So: build the Shortcut, and extraction stops depending on that guesswork.

## What arete expects

| | |
|---|---|
| Name | `Arete Export` (override with `--shortcut NAME`) |
| Input | the map's title, as text |
| Output | that map's exported Markdown, as text |

`arete` runs it as `shortcuts run "Arete Export" --input-path <name.txt> --output-path <out.md>`, so the Shortcut must accept text input and return text.

## Building it

In **Shortcuts.app**, new shortcut named exactly `Arete Export`:

These are the labels as they actually appear, confirmed against a working shortcut on 2026-08-28 (MindNode 2026.4.4, macOS 27):

1. **Receive `Text` from `Share Sheet`** — the input header. *If there's no input: Ask For Text* is fine; it never fires when `arete` supplies one.

2. **Find `Document` where** — MindNode's document query. Filter: **`Title` is `Shortcut Input`**. Tick **Limit** and set **Get: 1**, so one map comes back rather than a list. *Sort by* can stay **None**.

3. **Export Document** — set **Document** to the *Document* variable from step 2, and **Export Type** to **Markdown Text…**. Leave this as the last action.

**"Provide Output" does not need to be on.** It shows as off in the shortcut's Details pane and `shortcuts run --output-path` still receives the Markdown; that was measured, not assumed.

**Ignore the window title bar.** It can show something other than the shortcut's name — a working `Arete Export` displayed as "Title". `shortcuts list` is the authority on what the shortcut is really called, and that is the name `arete` matches.

Then check it:

```bash
arete --list                          # every row should now say "MindNode's exporter"
arete --extract "My Areas of Focus"   # MindNode's own Markdown
```

## Notes

**The UI labels may not match these exactly.** The action names above come from MindNode's App Intents metadata (`ExportDocumentIntent`, and the `DocumentEntityPropertyQuery` behind *Find Documents*), not from having built the shortcut — Shortcuts sometimes presents an intent under a friendlier name. The shape is right even where a label differs: find one document by name, export it as Markdown, return the text.

**What MindNode's Markdown looks like.** An H1 for the centre node, `##`/`###` for the upper branches, then `-` bullets with **tab** indentation below. Tags come through inline as `#Important`, and an untitled node exports as a bare `###` or an empty bullet.

Two consequences `arete` handles. Heading level counts as depth, so `## Branch` followed by `- leaf` nests properly — a parser reading only indentation would flatten the whole map to two levels. And an untitled heading is kept rather than dropped, because its level is what holds its children in place; dropping it would silently re-parent a subtree one level up.

**Output is MindNode's, not arete's.** By default `--extract` passes it through untouched. With `--plain`, arete re-renders it through the same parser an import uses and drops the H1 root — so `arete --extract X --plain | arete --stdin --title X` reproduces the map exactly. The cost is anything the parser does not model: task checkboxes, notes, and untitled *leaf* nodes, which are indistinguishable from horizontal rules.

**Read the intents yourself** if any of this drifts:

```bash
python3 -c "import json,pathlib;d=json.loads(pathlib.Path('/Applications/MindNode.app/Contents/Resources/Metadata.appintents/extract.actionsdata').read_text());print('\n'.join(sorted(d['actions'])))"
```

`CreateNodeIntent` is in that list too, with `childOf` / `siblingAfter` placement — which is how a node could be added to an *existing* map, the other thing OPML import cannot do. Not built yet; bon `art-kenosa`.
