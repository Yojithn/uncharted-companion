# The notes the companion answers from

`ingest.py` reads every `.txt` file in this folder, splits it into chunks at
each **blank line**, and stores the chunks in ChromaDB. So write one fact, step,
puzzle solution or treasure location per paragraph, with a blank line between
paragraphs.

Only `characters.txt` and `uncharted4_a_thiefs_end.txt` (short summaries written
for this project) are included in the repository. The chapter-by-chapter
walkthroughs and the collectibles list were adapted from published game guides
(IGN, PowerPyx), so they're left out.

## File names the chat page recognises

| File name | Shown as |
|---|---|
| `uncharted4_ch00_prologue.txt` | Prologue |
| `uncharted4_ch08_grave_of_henry_avery.txt` | Ch. 08 · The Grave of Henry Avery |
| `characters.txt` | Characters |
| `uncharted4_a_thiefs_end.txt` | Story |
| `uncharted4_collectibles.txt` | Collectibles |

Any other `.txt` file works too; it's just labelled with its file name.

After adding or changing notes, run `python ingest.py` again to rebuild the database.
