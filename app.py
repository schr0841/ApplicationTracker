"""Local-only ApplicationTracker. Run with: python app.py"""
from email.parser import BytesParser
from email.policy import default
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
import secrets
import sqlite3
import uuid
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
TOKEN = secrets.token_urlsafe(32)
ACTIVE = ('saved', 'applied', 'interviewing', 'offer')
STATUSES = ACTIVE + ('rejected', 'withdrawn', 'accepted')
MAX_UPLOAD = 25 * 1024 * 1024


class Connection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()


def connect():
    DATA.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATA / 'tracker.sqlite3', factory=Connection)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript('''
    CREATE TABLE IF NOT EXISTS applications (
      id TEXT PRIMARY KEY, company TEXT NOT NULL, role TEXT NOT NULL,
      posting_url TEXT, requisition_id TEXT, applied_at TEXT, status TEXT NOT NULL,
      notes TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS documents (
      id TEXT PRIMARY KEY, application_id TEXT REFERENCES applications(id),
      kind TEXT, name TEXT, path TEXT);
    CREATE TABLE IF NOT EXISTS status_events (
      id INTEGER PRIMARY KEY, application_id TEXT REFERENCES applications(id),
      previous_status TEXT, new_status TEXT, occurred_at TEXT DEFAULT CURRENT_TIMESTAMP);
    ''')
    return db


def text(value):
    return escape(str(value or ''), quote=True)


def page(content):
    return '''<!doctype html><html lang="en"><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>ApplicationTracker</title><style>
    *{box-sizing:border-box}body{margin:0;background:#f4f6fa;color:#172437;font:16px system-ui}
    main{max-width:1000px;margin:40px auto;padding:0 20px}h1{margin-bottom:4px}
    nav{display:flex;gap:20px;margin:28px 0}a{color:#1851a1}section,article{background:white;
    border:1px solid #dce2eb;border-radius:12px;padding:24px;margin:16px 0}
    .grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}label{display:block;font-weight:600}
    input,select,textarea{width:100%;margin:6px 0 14px;padding:10px;border:1px solid #adb9ca;border-radius:6px;font:inherit}
    button{background:#1851a1;color:white;border:0;padding:11px 18px;border-radius:6px;font:inherit;cursor:pointer}
    small,.muted{color:#526176}.badge{background:#e6edf8;padding:4px 10px;border-radius:20px}
    .row{display:flex;justify-content:space-between;gap:15px;align-items:center}.inline{display:flex;gap:10px;align-items:center}
    .inline select{width:auto;margin:0}pre{white-space:pre-wrap;font:inherit}h2{margin-top:0}
    @media(max-width:600px){.grid{grid-template-columns:1fr}.row{display:block}.inline{flex-wrap:wrap}}
    </style><main><h1>ApplicationTracker</h1><p class="muted">Your applications and documents, kept on this computer.</p>
    <nav><a href="/">Active applications</a><a href="/?view=archive">Archive</a><a href="/new">Add application</a></nav>''' + content + '</main></html>'


class Handler(BaseHTTPRequestHandler):
    def send_html(self, body, status=200):
        data = page(body).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Content-Security-Policy', "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, location):
        self.send_response(303)
        self.send_header('Location', location)
        self.end_headers()

    def do_GET(self):
        route = urlsplit(self.path)
        if route.path == '/new':
            options = ''.join(f'<option value="{s}" {"selected" if s == "applied" else ""}>{s.title()}</option>' for s in STATUSES)
            self.send_html(f'''<section><h2>Add application</h2>
            <form method="post" action="/applications" enctype="multipart/form-data">
            <input type="hidden" name="token" value="{TOKEN}">
            <div class="grid"><label>Company *<input name="company" required maxlength="200"></label>
            <label>Job title *<input name="role" required maxlength="200"></label>
            <label>Posting URL<input name="posting_url" type="url"></label>
            <label>Requisition ID<input name="requisition_id" maxlength="200"></label>
            <label>Application date<input name="applied_at" type="date"></label>
            <label>Status<select name="status">{options}</select></label></div>
            <label>Saved job posting<input type="file" name="posting" accept=".html,.htm,.zip"></label>
            <small>HTML, or a ZIP containing HTML and its asset folder.</small>
            <label>Submitted cover letter<input type="file" name="letter" accept=".pdf,.docx,.txt"></label>
            <small>PDF, DOCX, or TXT. Combined upload limit: 25 MB. Documents are optional.</small>
            <label>Notes<textarea name="notes" rows="4" maxlength="10000"></textarea></label>
            <button>Save application</button></form></section>''')
            return
        if route.path.startswith('/documents/'):
            with connect() as db:
                doc = db.execute('SELECT * FROM documents WHERE id=?', (route.path.rsplit('/', 1)[-1],)).fetchone()
            if not doc:
                self.send_html('<h2>Document not found</h2>', 404)
                return
            path = DATA / doc['path']
            if not path.is_file():
                self.send_html('<h2>Document file is missing</h2>', 404)
                return
            data = path.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'application/octet-stream')
            self.send_header('Content-Disposition', 'attachment; filename="document' + path.suffix + '"')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if route.path != '/':
            self.send_html('<h2>Page not found</h2>', 404)
            return
        archive = parse_qs(route.query).get('view') == ['archive']
        with connect() as db:
            records = db.execute('SELECT * FROM applications ORDER BY created_at DESC, rowid DESC').fetchall()
            docs = db.execute('SELECT * FROM documents').fetchall()
        records = [r for r in records if (r['status'] not in ACTIVE) == archive]
        body = f'<h2>{"Archive" if archive else "Active applications"} <small>({len(records)})</small></h2>'
        if not records:
            body += '<section>No applications here yet. <a href="/new">Add an application</a>.</section>'
        for r in records:
            options = ''.join(f'<option value="{s}" {"selected" if s == r["status"] else ""}>{s.title()}</option>' for s in STATUSES)
            links = ' · '.join(f'<a href="/documents/{d["id"]}">{text(d["kind"])}: {text(d["name"])}</a>' for d in docs if d['application_id'] == r['id'])
            url = r['posting_url'] or ''
            source = f'<a href="{text(url)}" target="_blank" rel="noopener noreferrer">Original posting</a>' if urlsplit(url).scheme in ('http', 'https') else ''
            body += f'''<article><div class="row"><h2>{text(r['role'])}</h2><span class="badge">{text(r['status'].title())}</span></div>
            <p><strong>{text(r['company'])}</strong> · Applied: {text(r['applied_at']) or 'Not recorded'}</p>
            <p>{source} {(' · Requisition: ' + text(r['requisition_id'])) if r['requisition_id'] else ''}</p>
            <p>{links}</p><pre>{text(r['notes'])}</pre>
            <form class="inline" method="post" action="/status"><input type="hidden" name="token" value="{TOKEN}">
            <input type="hidden" name="id" value="{r['id']}">
            <label for="status-{r['id']}">Update status</label><select id="status-{r['id']}" name="status">{options}</select><button>Update</button></form></article>'''
        self.send_html(body)

    def do_POST(self):
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if size <= 0 or size > MAX_UPLOAD:
                raise ValueError('The request must be smaller than 25 MB.')
            content_type = self.headers.get('Content-Type', '')
            raw = self.rfile.read(size)
            fields, uploads = {}, []
            if content_type.startswith('multipart/form-data'):
                msg = BytesParser(policy=default).parsebytes(('Content-Type: ' + content_type + '\r\nMIME-Version: 1.0\r\n\r\n').encode() + raw)
                for part in msg.iter_parts():
                    name = part.get_param('name', header='content-disposition')
                    filename = part.get_filename()
                    payload = part.get_payload(decode=True) or b''
                    if filename:
                        uploads.append((name, Path(filename.replace('\\', '/')).name, payload))
                    elif name:
                        fields[name] = payload.decode('utf-8')
            else:
                fields = {k: v[0] for k, v in parse_qs(raw.decode()).items()}
            if not secrets.compare_digest(fields.get('token', ''), TOKEN):
                self.send_html('<h2>Form expired</h2><p>Reload the form and try again.</p>', 403)
                return
            status = fields.get('status', '')
            if status not in STATUSES:
                raise ValueError('Choose a valid status.')
            if self.path == '/status':
                with connect() as db:
                    old = db.execute('SELECT status FROM applications WHERE id=?', (fields.get('id'),)).fetchone()
                    if not old:
                        raise ValueError('Application not found.')
                    db.execute('UPDATE applications SET status=? WHERE id=?', (status, fields['id']))
                    if old['status'] != status:
                        db.execute('INSERT INTO status_events(application_id,previous_status,new_status) VALUES(?,?,?)', (fields['id'], old['status'], status))
            elif self.path == '/applications':
                company, role = fields.get('company', '').strip(), fields.get('role', '').strip()
                if not company or not role or len(company) > 200 or len(role) > 200:
                    raise ValueError('Company and job title are required (up to 200 characters each).')
                url = fields.get('posting_url', '').strip()
                if url and urlsplit(url).scheme not in ('http', 'https'):
                    raise ValueError('Posting URL must start with http:// or https://.')
                date = fields.get('applied_at', '')
                if date:
                    from datetime import date as Date
                    Date.fromisoformat(date)
                for kind, name, payload in uploads:
                    allowed = { 'posting': {'.html', '.htm', '.zip'}, 'letter': {'.pdf', '.docx', '.txt'} }
                    if kind not in allowed or Path(name).suffix.lower() not in allowed[kind]:
                        raise ValueError('Unsupported document type. Use HTML/ZIP for postings or PDF/DOCX/TXT for letters.')
                    if not payload:
                        raise ValueError('Uploaded documents cannot be empty.')
                app_id = str(uuid.uuid4())
                written = []
                try:
                    with connect() as db:
                        db.execute('INSERT INTO applications(id,company,role,posting_url,requisition_id,applied_at,status,notes) VALUES(?,?,?,?,?,?,?,?)', (app_id, company, role, url, fields.get('requisition_id',''), date, status, fields.get('notes','')))
                        for kind, name, payload in uploads:
                            doc_id = str(uuid.uuid4())
                            relative = Path('applications') / app_id / (doc_id + Path(name).suffix.lower())
                            dest = DATA / relative
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            written.append(dest)
                            dest.write_bytes(payload)
                            db.execute('INSERT INTO documents VALUES(?,?,?,?,?)', (doc_id, app_id, kind, name, str(relative)))
                except Exception:
                    for dest in written:
                        dest.unlink(missing_ok=True)
                    raise
            else:
                self.send_html('<h2>Page not found</h2>', 404)
                return
            self.redirect('/?view=archive' if status not in ACTIVE else '/')
        except (ValueError, UnicodeError) as exc:
            self.send_html(f'<h2>Could not save application</h2><p>{text(exc)}</p><p><a href="/new">Return to form</a></p>', 400)
        except Exception:
            self.send_html('<h2>Could not save</h2><p>Check that the local data folder is writable and try again.</p>', 500)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    with connect():
        pass
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print(f'ApplicationTracker: http://127.0.0.1:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
