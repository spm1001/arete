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

7. **Find `Node` where** — **All** of the following are true:
   - **`Title` is** the step-4 item
   - **`Document ID` is** the **Document ID** of the document from step 6

   Tick **Limit**, **Get: 1**.

   **Check the second filter's value box is actually filled.** Shortcuts will show a
   `Document ID` variable chip *next to or below* an empty box, which looks wired up and is
   not. An empty filter matches nothing, `Find Node` returns an empty list, and step 8 then
   fails with:

   ```
   Numerical argument out of domain
   You asked for item 0, but the first item is at index 1.
   ```

   That message reads like a bad index in one of the Get Item actions, and it is not — it is
   `Create Node` reaching into an empty result. If the variable will not go into the box,
   delete this filter row and match on `Title` alone; see the caveat below.

8. **Create Node** — this one reads as a sentence and the two slots are easy to get the wrong way round. The intent's own template is:

   ```
   Create ${createType} of ${relativeNode} in ${document}
   ```

   So it must end up reading **Create `Child` of `Node` in `Document`**:

   - **Create** → `Child`
   - **of** → the **Node** from step 7 — the *parent*, not the document
   - **in** → the **Document** from step 6
   - **Node Title** → the step-5 item. This is **hidden behind the `⌄` disclosure chevron** on the action; expand it, or every node arrives untitled.
   - **Open When Run** → **untick it**. arete calls this once per node, so leaving it on pulls MindNode to the front on every line of the list.

Nothing needs to be returned, so **Provide Output** can stay off.

*Getting the slots backwards — "of `Document` in `Node`" — is the natural reading of the sentence and produces no error message, so check this one against the template above rather than against how it sounds.*

## Check it

```bash
printf 'In my work I am 2\nThe long game\ntest leaf\n' > /tmp/append.txt
shortcuts run "Arete Append" --input-path /tmp/append.txt
arete --extract "In my work I am 2" | grep "test leaf"
```

## Caveats worth knowing before you rely on it

**Parent nodes are matched by title, so duplicate titles are ambiguous.** If two nodes in one map share a title, step 7 takes whichever MindNode returns first. `arete --append` refuses rather than guessing when the target title is not unique *in the target map*.

**It cannot check other maps, though.** If step 7 has no `Document ID` filter, the lookup spans every document, and a parent title that also exists elsewhere may win. arete's pre-flight cannot see that, so keep the filter if you can.

**Two of the three fixes fail silently.** A missing `Node Title` produces untitled nodes and a backwards `of`/`in` wiring misplaces them — neither raises an error. Only the empty-filter case above is loud. So verify the result in the map, not the absence of a complaint.

**If the `Document ID` filter is missing in step 7**, the node lookup spans every map, and a parent title that also exists in another document could attach the new node to the wrong map. Say so and we will find another route — matching on the document's `Nodes` property is the likely fallback.

**Corrections already folded in from building it (2026-08-28).** The first draft of this page named step 8's fields by their parameter names — *Document*, *Related Node* — and that is not what Shortcuts shows: it renders the action as a sentence, `Create … of … in …`, where "of" is the *relative node* and "in" is the *document*. Wiring them the way the sentence reads puts them backwards. The `Node Title` field also sits behind a disclosure chevron and is easy to miss entirely.

**The shortcut's window title is not its name.** It shows the selected action instead — a correctly-named `Arete Append` displayed as "Create Node", just as `Arete Export` displayed as "Title". `shortcuts list` is the authority.

**One Shortcut run per node** means a twenty-node list takes a noticeable few seconds. That is the price of not building a looping Shortcut, and it can be revisited if it grates.
