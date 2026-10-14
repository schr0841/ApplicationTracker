# Architecture and behavior

## Storage

Use SQLite for records and a local filesystem directory for attachments. A UUID identifies each application, independently of company and title. Multiple applications to the same employer remain separate.

Suggested tables:

- `applications`: id, company, role, location, posting_url, requisition_id, applied_at, status, contact, notes, next_follow_up_at, created_at, updated_at.
- `documents`: id, application_id, kind, relative_path, original_filename, media_type, sha256, captured_at, source_url. Document kinds include posting_html, cover_letter_submitted, and cover_letter_source.
- `status_events`: id, application_id, previous_status, new_status, occurred_at, source, email_message_id, reason. Use this for audit history and undo.
- `email_matches`: provider, message_id, thread_id, application_id, proposed_status, match_reason, review_state, processed_at. Enforce uniqueness on provider plus message_id to prevent duplicate processing.

Statuses: saved, applied, interviewing, offer, rejected, withdrawn, accepted. Active view includes saved, applied, interviewing, and offer; closed outcomes appear in the archive.

## Posting and letter preservation

Capture the posting when adding the application because the URL may later change or disappear. Support importing browser-saved HTML with its asset folder; retain the original URL and capture time. Preserve the rendered content of dynamic postings when possible and show a capture failure rather than silently saving an empty page. An optional PDF snapshot can supplement HTML.

Keep the submitted cover letter immutable. Later revisions are separate versions. Record a content hash to detect accidental changes.

Treat imported HTML as untrusted. Preview a sanitized copy in a sandbox without scripts, forms, or external requests; keep the original available as an attachment. Never render raw posting HTML inside the main application page.

Store attachments under generated IDs, validate paths and file types, and avoid overwriting existing files. If an upload or database write fails, clean up incomplete records. Backups must include both the database and attachments.

## Rejection email workflow

1. Connect the selected mail provider with read-only access. Store tokens outside Git using an appropriate local secret store.
2. Fetch candidate messages incrementally. Track provider message IDs and retry safely after failures.
3. Match requisition ID or an already-linked application conversation first. Use employer, role, and application date as supporting evidence. Company name alone is insufficient, especially with multiple applications at one employer.
4. Recognize an explicit rejection for that application. General newsletters, withdrawn postings, and unrelated messages must not close an application.
5. Put uncertain or conflicting matches in a review queue. Begin with review for every suggested rejection.
6. On confirmation, atomically set status to rejected and record the message reference, timestamp, and previous status. Hide it from the active view and preserve all attachments. Do not delete or modify the email.
7. Allow undo. Avoid automatic changes to accepted or otherwise conflicting outcomes. Optional automation can later handle only explicit, unambiguous matches.

No live email access or scheduled polling is configured by this scaffold.

## Useful verification when implemented

- Two applications at the same company cannot be confused by a rejection.
- Processing the same message twice creates one transition.
- Ambiguous rejection candidates require review.
- Archiving and undo retain documents and status history.
- Failed uploads cannot create broken attachment references.
- Saved posting previews cannot execute scripts or load remote tracking content.
