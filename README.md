# ApplicationTracker

A personal job application tracker with saved job postings, submitted cover letters, and an application history.

## Recommended first version

- A local web interface backed by Python and SQLite.
- Add an application with company, role, location, posting URL, requisition ID, application date, status, contact, notes, and next follow-up date.
- Attach an HTML snapshot of the posting and the exact cover letter submitted (PDF or DOCX, with an optional editable source).
- Show active applications by default; provide search, status filters, and an archive view.
- Mark rejected applications as `rejected` and hide them from the active view. Retain their documents and history and support reopening.
- Start with manual updates; add email ingestion after the core tracker works.

This repository is a project scaffold and design, not an implemented application.

## Directory structure

```text
ApplicationTracker/
  README.md
  docs/
    architecture.md
  src/
    application_tracker/    # Future UI, persistence, and service code
  tests/                   # Future behavior and integration tests
  examples/
    application.json       # Fictional record illustrating the data model
  data/                    # Local only; excluded from Git
    tracker.sqlite3
    applications/
      <application-uuid>/
        posting/
          original.html
          assets/
        cover-letter/
          submitted.pdf
          source.docx
```

Use a private GitHub repository for the source. Keep real application records, letters, email data, and credentials out of Git. Back up the SQLite database and document folder together to private storage.

## Implementation sequence

1. Application creation/editing, document upload, active/archive views, and manual rejection.
2. Posting capture/import, search, follow-up dates, and backup/export.
3. Read-only email connection, rejection suggestions, matching review, and duplicate handling.
4. Optional automatic archiving for explicit rejections matched to a single application, with undo and an audit trail.
