# The export Shortcut

`arete --extract` reads MindNode's base snapshot, which needs nothing installed and is exact for any map created by import. It cannot see a map **typed in the app**, because that map's content lives in an unfolded CRDT operation log and the snapshot alone would report one blank node. `arete --list` marks which maps are which.

MindNode's own exporter has no such limit — it always sees the live document. It is reachable through the `ExportDocumentIntent` App Intent, and there is no supported way to call an app intent straight from a shell. So it needs one Shortcut, built once by hand. After that `arete --extract` uses it automatically for exactly the maps it needs to.

## What arete expects

| | |
|---|---|
| Name | `Arete Export` (override with `--shortcut NAME`) |
| Input | the map's title, as text |
| Output | that map's exported Markdown, as text |

`arete` runs it as `shortcuts run "Arete Export" --input-path <name.txt> --output-path <out.md>`, so the Shortcut must accept text input and return text.

## Building it

In **Shortcuts.app**, new shortcut named exactly `Arete Export`:

1. **Accept input.** In the shortcut's details (ⓘ), tick *Use as Quick Action* is not needed — what matters is that the first action consumes **Shortcut Input**. Set the input type to **Text**.

2. **Find Documents** — MindNode's document query. Add a filter: **Name** `is` **Shortcut Input**. Set *Limit* to 1 result, so the shortcut returns one map rather than a list.

3. **Export Document** — MindNode's `ExportDocumentIntent`. Set *Document* to the output of step 2, and *Format* to **Markdown Text**.

4. Make sure step 3's result is the shortcut's **last action**, so it becomes the output. If Shortcuts hands you a file rather than text, add **Get Text from Input** as a final step.

Then check it:

```bash
arete --list                          # the two columns should now say "via MindNode's exporter"
arete --extract "My Areas of Focus"   # MindNode's own Markdown
```

## Notes

**The UI labels may not match these exactly.** The action names above come from MindNode's App Intents metadata (`ExportDocumentIntent`, and the `DocumentEntityPropertyQuery` behind *Find Documents*), not from having built the shortcut — Shortcuts sometimes presents an intent under a friendlier name. The shape is right even where a label differs: find one document by name, export it as Markdown, return the text.

**Output is MindNode's, not arete's.** By default `--extract` passes MindNode's Markdown through untouched, so its heading and bullet style are whatever MindNode produces. With `--plain`, arete re-renders it through the same parser an import uses, so it round-trips — at the cost of dropping anything the parser does not model, such as notes or task checkboxes.

**Read the intents yourself** if any of this drifts:

```bash
python3 -c "import json,pathlib;d=json.loads(pathlib.Path('/Applications/MindNode.app/Contents/Resources/Metadata.appintents/extract.actionsdata').read_text());print('\n'.join(sorted(d['actions'])))"
```

`CreateNodeIntent` is in that list too, with `childOf` / `siblingAfter` placement — which is how a node could be added to an *existing* map, the other thing OPML import cannot do. Not built yet; bon `art-kenosa`.
