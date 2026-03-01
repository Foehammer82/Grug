# Discord — Documents

Upload campaign documents, homebrew PDFs exported as text, rule supplements, or any other plain-text reference material. Grug indexes them into his vector store and uses them to answer questions accurately and with citations.

---

## Commands

### `!upload_doc [description]`

Attach a document file to your message to index it.

| Alias | `!add_doc` |
|---|---|
| **Permission required** | Manage Guild |
| **Attachment required** | Yes |

**Supported formats:** `.txt`, `.md`, `.rst`

**Maximum file size:** 10 MB per file

```
!upload_doc Player's Handbook chapter 5 — equipment rules
```
*(with a `.txt` file attached)*

Grug will:
1. Read the attached file.
2. Split it into chunks.
3. Generate embeddings for each chunk.
4. Store the embeddings in the vector store.
5. Confirm with the number of chunks indexed.

!!! info "Supported file types"
    Only plain-text formats are supported. If you have a PDF, export it to `.txt` first using a tool like [pdftotext](https://www.xpdfreader.com/pdftotext-man.html) or your PDF reader's "Save as text" option.

---

### `!list_docs`

Show all documents currently indexed for this server.

| **Permission required** | None |

Grug replies with an embed listing each document's:
- File name
- Description (if provided at upload)
- Chunk count
- Date added

---

### `!remove_doc <id>`

Remove a document and delete all its vector embeddings.

| Alias | `!delete_doc <id>` |
|---|---|
| **Permission required** | Manage Guild |

Use `!list_docs` to find the document ID first.

```
!remove_doc 3
```

!!! warning "Deletion is permanent"
    Removing a document deletes all of its indexed chunks from the vector store. Grug will no longer be able to reference its content. You can re-upload the file at any time if needed.

---

## What makes a good document?

Grug retrieves document content based on **semantic similarity** to the question asked. He works best with:

- **Well-structured text** — headings, sections, and clear paragraph breaks help chunking.
- **Campaign-specific content** — house rules, world lore, session recaps, NPC files.
- **Reference material** — rule summaries, spell lists, equipment tables.

Avoid uploading very large unstructured blobs of text. If you have a large document, consider splitting it into topical files (e.g. one file per chapter or area).

---

## Managing documents from the web

You can also view and delete documents from the [Web UI Documents page](../web-ui/documents.md). Uploading via the web UI is not currently supported — use Discord for that.
