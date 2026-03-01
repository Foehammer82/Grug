# Guide — Character Sheets

Grug can ingest character sheets so the AI has accurate information about your party when answering questions, generating encounters, or narrating scenes.

---

## Supported formats

Character sheets must be exported as plain text before uploading. Supported file extensions:

| Format | Extension | Notes |
|---|---|---|
| Plain text | `.txt` | Universal — any character builder can export this |
| Markdown | `.md` | Great for hand-crafted or Obsidian character sheets |
| reStructuredText | `.rst` | Less common but fully supported |

**Maximum file size:** 10 MB per file

---

## Exporting your character sheet

How you export depends on the tool you're using:

=== "D&D Beyond"

    D&D Beyond does not have a direct plain-text export. Options:

    - Use the **Print** function and save the resulting HTML as text via your browser's **File → Save As → Text**.
    - Use a browser extension like [D&D Beyond to PDF](https://www.dndbeyond.com/tools) and then convert the PDF to text with `pdftotext`.
    - Copy-paste manually into a `.txt` file for the most important details (stats, abilities, equipment).

=== "Foundry VTT"

    Export your actor as JSON from the Foundry UI, then convert the JSON to a readable text summary. Many community modules (e.g. **PDF Export**) can generate a printable/text version directly.

=== "Pathbuilder 2e"

    Use **Export → Text** in Pathbuilder to download a `.txt` file ready for upload.

=== "Hand-crafted (Markdown)"

    If you write your character sheet in Markdown (e.g. in Obsidian), you can upload the `.md` file directly.

---

## Uploading the character sheet

Use the [`!upload_doc`](../discord/documents.md) command with a descriptive name:

```
!upload_doc Thalindra Swiftbrook — Level 7 Wood Elf Ranger
```
*(with the character sheet `.txt` file attached)*

**Tips:**

- Upload each character as a separate file. This makes it easier to update or remove individual sheets later.
- Include the character name and class in the description so you and Grug can identify the file quickly with `!list_docs`.
- Re-upload (and remove the old version with `!remove_doc`) whenever the character levels up or their gear changes significantly.

---

## How Grug uses character sheets

Once a character sheet is indexed, Grug retrieves relevant sections via semantic search during conversations. For example:

> **Player:** @Grug can Thalindra cast Conjure Animals today?

Grug will search the indexed documents, find Thalindra's sheet, check her spell slots, and give an accurate answer — rather than guessing from general knowledge.

For best results:
- Make sure the sheet includes **spell slots and prepared spells**, **ability scores**, **class features**, and **equipment**.
- Mention the character's name in your questions so Grug knows which sheet to look for.

---

## Keeping sheets up to date

Character sheets become stale as characters level up. A good workflow:

1. After each level-up or major gear change, export an updated sheet.
2. Run `!list_docs` to find the old sheet's ID.
3. Remove the old sheet: `!remove_doc <id>`.
4. Upload the new sheet: `!upload_doc <character name and level>`.
