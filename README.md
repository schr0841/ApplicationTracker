# ApplicationTracker

A personal job application tracker with saved job postings, submitted cover letters, and an application history.

## Recommended first version

- A local web interface backed by Python and SQLite.
- Add an application with company, role, location, posting URL, requisition ID, application date, status, contact, notes, and next follow-up date.
- Attach an HTML snapshot of the posting and the exact cover letter submitted (PDF or DOCX, with an optional editable source).
- Show active applications by default; provide search, status filters, and an archive view.
- Mark rejected applications as `rejected` and hide them from the active view. Retain their documents and history and support reopening.
- Start with manual updates; add email ingestion after the core tracker works.

## Run the app

Requires Python 3.10 or newer; no packages need to be installed.

```powershell
cd C:\Users\schre\GitHub\ApplicationTracker
python app.py
```

Open http://127.0.0.1:8765 in your browser. Keep the terminal running; Ctrl+C stops the app. Use `python app.py --port 8766` if the default port is occupied.

Click **Add application**, fill in the company and job title, and optionally attach a posting (HTML or ZIP with assets) and submitted cover letter (PDF, DOCX, or TXT). Combined request limit: 25 MB. Saved documents download as attachments; raw HTML is not previewed in the app.

Use **Update status** to move rejected, withdrawn, or accepted applications to the archive. Change the status back to Applied to restore an application. Records and documents persist in `data/`, which is excluded from Git. Back up the entire data folder together.

This first version supports adding applications, uploads, document downloads, status changes, and active/archive lists. Email automation, editing existing application details, search, and automatic posting capture are not implemented. The server binds only to localhost and is intended for personal use on this computer, not public hosting.

Run verification with `python -m unittest discover -s tests -v`.

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

This public GitHub repository contains source code, documentation, and fictional examples only. Keep real application records, letters, email data, and credentials out of Git. Back up the SQLite database and document folder together to private storage.

## Implementation sequence

1. Application creation/editing, document upload, active/archive views, and manual rejection.
2. Posting capture/import, search, follow-up dates, and backup/export.
3. Read-only email connection, rejection suggestions, matching review, and duplicate handling.
4. Optional automatic archiving for explicit rejections matched to a single application, with undo and an audit trail.
