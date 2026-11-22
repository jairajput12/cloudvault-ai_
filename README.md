# CloudVault AI

An AI-powered cloud document and media platform — upload any file type, get
it automatically processed by AI depending on what it is, chat with your
documents, generate study material from them, organize with folders and
favorites, and share files publicly with expiring links.

Built as a final-year capstone project. Positioned as "Google Drive for
everyone, with a genuine study superpower for students."

## Live features

- **Auth** — sign up, email verification, sign in (Amazon Cognito), with
  per-user file isolation enforced server-side (not just hidden in the UI)
- **Upload any file type** — dropped straight into S3 via a pre-signed URL
- **AI processing on upload**, branching by file type:
  - Images → Amazon Bedrock (Nova Lite vision) generates a description + tags,
    with a real thumbnail preview
  - PDFs → Nova Lite reads the document and extracts its text, then
    summarizes it
  - Plain text → read directly, then summarized
  - Anything else → stored as-is, no AI attempted
- **Chat with a document** — ask questions about one specific file, answered
  using its extracted text
- **AI Assistant** — ask questions across your *entire* library at once;
  answers cite which file(s) the answer came from
- **Study Assistant** — generate 5 MCQs and 5 flashcards per document,
  cached so they're not regenerated every time
- **Learn Hub** — browse and practice every document that has study material
- **Folders** — create, move files into, delete (files return to
  "Uncategorized" rather than being destroyed)
- **Favorites** — star any file, browse them in a dedicated tab
- **Shareable links** — generate a public link to one file with a
  selectable expiry (1hr / 24hr / 7 days), viewable without an account
- **Dashboard** — real-time stats, search, drag-and-drop upload
- **Light/dark theme toggle**, simulated storage quota bar, quick
  "switch account" via remembered emails

## Architecture

```
Browser (frontend/index.html)
    |
    |-- Amazon Cognito (sign up / sign in / email verification)
    |
    |-- API Gateway (HTTP API, JWT Authorizer on every route except
    |   /shared-file, which must stay public)
    |       |-- GET    /documents
    |       |-- GET    /upload-url
    |       |-- GET    /download-url
    |       |-- DELETE /delete-document
    |       |-- PATCH  /update-document        (folder move + favorite toggle)
    |       |-- POST   /chat                   (chat with one document)
    |       |-- POST   /ask-assistant          (chat across the whole library)
    |       |-- POST   /generate-study-material
    |       |-- POST   /create-folder
    |       |-- GET    /folders
    |       |-- DELETE /delete-folder
    |       |-- POST   /create-share
    |       |-- GET    /shared-file            (NO authorizer - public)
    |
    |-- Direct-to-S3 upload via pre-signed URL (bypasses Lambda for the
        actual file bytes; ContentType is pinned to match on both ends,
        or S3 rejects the signature)

Amazon S3 (uploads bucket, private, per-user key prefix)
    |
    |-- S3 Event Notification (object create)
            |
            v
    lambda_upload_handler.py
            |-- image  -> Bedrock Nova Lite (vision) -> description + tags
            |-- pdf    -> Nova Lite reads the PDF -> extracted text -> Nova Lite -> summary
            |-- text   -> read directly -> Nova Lite -> summary
            |-- other  -> stored only
            |
            v
    DynamoDB
      - cloudvault-documents (PK document_id)
      - cloudvault-folders   (PK user_id, SK folder_name)
      - cloudvault-shares    (PK share_id)

Public share page: frontend/share.html (separate static file, no login,
calls /shared-file to fetch a fresh short-lived download link)

Hosting: the frontend sits in a private S3 bucket behind CloudFront (HTTPS).
```

## Folder structure

- `frontend/index.html` — the entire app UI. Plain HTML/JS, no build step,
  no framework. It reads the API address and Cognito client from
  `config.js`, which the deploy pipeline writes (see `config.example.js`).
- `frontend/share.html` — the public page a share link opens.
- `backend/` — one file per Lambda function (see table below). Table names,
  the bucket, the site URL and the model ID come from environment variables
  set by Terraform.
- `infrastructure/` — Terraform for the whole stack, and `bootstrap/` for the
  one-time state bucket and GitHub sign-in role. See
  [infrastructure/README.md](infrastructure/README.md).
- `.github/workflows/` — `deploy.yml` (plan on pull requests, apply and
  publish on `main`) and `destroy.yml` (tear everything down).
- `docs/iam/` — the IAM policies the original console-built stack used, kept
  for reference. Terraform defines the live ones in `infrastructure/iam.tf`.

## Deploying

Deployment is a push to `main`. The pipeline applies the Terraform, writes
`frontend/config.js` from the outputs, syncs the frontend to S3 and invalidates
CloudFront. Setup (a one-time bootstrap and three repository variables) is in
[infrastructure/README.md](infrastructure/README.md).

## Lambda functions

| File | Trigger | Purpose |
|---|---|---|
| `lambda_upload_handler.py` | S3 event | Reads the new file, runs AI based on type, stores metadata |
| `lambda_list_documents.py` | API GW | Returns the signed-in user's documents |
| `lambda_generate_upload_url.py` | API GW | Pre-signed S3 PUT URL |
| `lambda_get_download_url.py` | API GW | Pre-signed S3 GET URL, ownership-checked |
| `lambda_delete_document.py` | API GW | Deletes from S3 + DynamoDB, ownership-checked |
| `lambda_update_document.py` | API GW | Folder move and/or favorite toggle |
| `lambda_chat_with_document.py` | API GW | Q&A grounded in one document's extracted text |
| `lambda_ask_assistant.py` | API GW | Q&A grounded in the user's whole library (summaries) |
| `lambda_generate_study_material.py` | API GW | Generates 5 MCQs + 5 flashcards, caches result |
| `lambda_create_folder.py` / `lambda_list_folders.py` / `lambda_delete_folder.py` | API GW | Folder management |
| `lambda_create_share.py` | API GW | Creates a share_id + expiry, returns a public link |
| `lambda_get_shared_file.py` | API GW (**no authorizer**) | Public lookup by share_id, expiry-checked |

## AWS services used

| Service | Purpose |
|---|---|
| S3 | File storage, and the origin for the frontend |
| CloudFront | HTTPS in front of the frontend |
| Terraform + GitHub Actions | Infrastructure as code and the deploy pipeline |
| Lambda (Python 3.12) | All backend logic |
| API Gateway (HTTP API) | Exposes Lambda functions as REST endpoints |
| DynamoDB | Documents, folders, and shares metadata |
| Amazon Bedrock (Nova Lite) | AI summarization, vision, PDF reading, chat, study material |
| Amazon Cognito | User authentication |
| IAM | Least-privilege roles scoped per resource |

## Known limitations

- **PDF reading** sends the whole file to the model, which accepts PDFs up
  to about 4.5 MB. Larger files are stored but get no summary. Only the first
  few pages' text (about 3,000 tokens) is kept for chat and study material.
- **Video files** are stored but not yet AI-processed — would need frame
  extraction and/or audio transcription (Amazon Transcribe).
- **HEIC/HEIF photos** (default iPhone format) get a friendly message
  asking to convert to JPEG/PNG, since Nova can't read that format directly.
- **Duplicate filenames overwrite each other** in S3, since the filename is
  used directly as the S3 key.
- **Storage quota is simulated** (15 GB, Drive-style) — S3 has no real
  per-user cap; this is a cosmetic UI element, not an enforced limit.
- **"Switch account" is the simple version** — remembered emails for fast
  re-login, not true simultaneous multi-session switching.

## Debugging notes worth knowing

A number of genuinely subtle bugs came up building this, useful to
understand rather than just work around:

- IAM roles are **global**, but the resources they reference (DynamoDB
  tables, S3 buckets) are **regional** — a mismatched region in a
  `Resource` ARN causes `AccessDenied` even when the policy looks correct.
- Anthropic models on Bedrock bill through AWS Marketplace and require a
  verified payment method; Amazon's own models (Nova) are first-party and
  bill directly — relevant if testing without a card on file.
- S3 event notifications **URL-encode the object key** (spaces become
  `+`) — must `urllib.parse.unquote_plus()` it before use, or you'll be
  looking for a file that doesn't exist under that literal name.
- Pre-signed PUT URLs are signed against a specific `Content-Type`. The
  browser's actual upload request must send the *exact same* value, or S3
  rejects it with `SignatureDoesNotMatch`.
- Setting CORS headers in **both** the Lambda response and the API Gateway
  CORS config causes duplicate headers, which browsers reject outright.
- Pages opened via `file://` send `Origin: null`, which API Gateway's `*`
  CORS wildcard does not reliably match — only real web hosting (even
  S3 static hosting) resolves this cleanly.
- Newly created Lambda functions default to their **own auto-generated
  execution role**, not any shared role you've built — easy to forget to
  switch, and the resulting `AccessDeniedException` is initially
  confusing since the shared role's permissions look correct.
