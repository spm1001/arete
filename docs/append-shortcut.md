# The append Shortcut

`arete` can only ever create a *new* map, because OPML import has no notion of adding to an existing document. MindNode's `CreateNodeIntent` does: it takes a placement (`childOf`, `siblingAfter`, `siblingBefore`, `mainNode`) and the node to place relative to.

Like the export half, it is an App Intent, so it needs one Shortcut built by hand. After that `arete --append` drives it.

## What arete expects

| | |
|---|---|
| Name | `Arete Append` (override with `--append-shortcut NAME`) |
| Input | three lines of text: the map's title, the parent node's title, the new node's title |
| Output | nothing needed |

So `arete` writes a file like this and runs `shortcuts run "Arete Append" --input-path <file>`:

```
In my work I am 2
The long game
a pension that actually pays out
```

One node per run. That is slower than a single batched call, but it keeps the Shortcut to one straight line of actions with no looping, and `arete` already knows the tree — it walks top-down so a parent always exists before its children are added.

## Building it

New shortcut in **Shortcuts.app**, named exactly `Arete Append`.

1. **Receive `Text` from `Share Sheet`** — the input header, same as the export Shortcut. *If there's no input: Ask For Text* is harmless.

2. **Split Text** — set *Text* to **Shortcut Input**, and *Separator* to **New Lines**. This gives a three-item list.

3. **Get Item from List** — *Get* **Item At Index**, *Index* **1**, from the split text. This is the **map title**. (Rename the action's output variable to `MapTitle` if Shortcuts lets you — it makes the later steps readable.)

4. **Get Item from List** — *Item At Index* **2**. This is the **parent node title**.

5. **Get Item from List** — *Item At Index* **3**. This is the **new node title**.

6. **Find `Document` where** — filter **`Title` is** the step-3 item. Tick **Limit**, **Get: 1**.

7. **Find `Node` where** — filter **`Title` is** the step-4 item, **and** **`Document ID` is** the *Document ID* of the document from step 6. Tick **Limit**, **Get: 1**.
   *If a Document ID filter is not offered, filter on Title alone and see the caveat below.*

8. **Create Node** — *Create Type* **Child**, *Document* the step-6 document, *Related Node* the step-7 node, *Node Title* the step-5 item.

Nothing needs to be returned, so **Provide Output** can stay off.

## Check it

```bash
printf 'In my work I am 2\nThe long game\ntest leaf\n' > /tmp/append.txt
shortcuts run "Arete Append" --input-path /tmp/append.txt
arete --extract "In my work I am 2" | grep "test leaf"
```

## Caveats worth knowing before you rely on it

**Parent nodes are matched by title, so duplicate titles are ambiguous.** If two nodes in one map share a title, step 7 takes whichever MindNode returns first. `arete --append` warns when the target title is not unique rather than guessing silently.

**If the `Document ID` filter is missing in step 7**, the node lookup spans every map, and a parent title that also exists in another document could attach the new node to the wrong map. Say so and we will find another route — matching on the document's `Nodes` property is the likely fallback.

**The UI labels above come from MindNode's App Intents metadata, not from having built this.** When the export Shortcut was written up the same way, the shape was right but two labels differed — the filter field was `Title` rather than `Name`, and the parameter was `Export Type` rather than `Format`. Expect the same kind of small mismatch, and tell me what you actually see.

**One Shortcut run per node** means a twenty-node list takes a noticeable few seconds. That is the price of not building a looping Shortcut, and it can be revisited if it grates.
