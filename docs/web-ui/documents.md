# Web UI — Documents

The Documents page shows all files indexed into Grug's vector store for your server and lets you delete them.

---

## Accessing documents

1. Log in to the [web dashboard](overview.md).
2. Select your server from the dashboard.
3. Click **Documents** in the sidebar.

---

## Document table

Each row represents one indexed document and shows:

| Column | Description |
|---|---|
| **File name** | Original name of the uploaded file. |
| **Description** | The description provided at upload time (if any). |
| **Chunks** | Number of vector chunks the document was split into. |
| **Date Added** | When the document was uploaded. |
| **Actions** | Delete button to remove the document and its embeddings. |

---

## Deleting a document

Click the **delete** (trash icon) button on a row to permanently remove the document and all its vector embeddings from the store.

!!! warning "Permanent action"
    Once deleted, Grug can no longer reference the document's content. You can re-upload the file from Discord at any time using [`!upload_doc`](../discord/documents.md).

---

## Uploading documents

Document upload is only available via Discord — see the [`!upload_doc` command](../discord/documents.md).
