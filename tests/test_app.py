import importlib.util
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import urlencode

spec = importlib.util.spec_from_file_location('tracker', Path(__file__).parents[1] / 'app.py')
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


class TrackerTest(unittest.TestCase):
    def setUp(self):
        test_root = Path(__file__).parents[1] / 'data'
        test_root.mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=test_root)
        app.DATA = Path(self.tmp.name)
        self.server = app.ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def add(self, filename='posting.html'):
        boundary = 'tracker-test-boundary'
        parts = []
        for key, value in {'token': app.TOKEN, 'company': 'Example <Company>', 'role': 'Engineer', 'status': 'applied'}.items():
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="posting"; filename="{filename}"\r\nContent-Type: text/html\r\n\r\n<script>alert(1)</script>Job description\r\n--{boundary}--\r\n'.encode())
        return urlopen(Request(self.base + '/applications', data=b''.join(parts), headers={'Content-Type': f'multipart/form-data; boundary={boundary}'}))

    def test_upload_archive_restore_and_persistence(self):
        with self.add() as response:
            self.assertIn('Example &lt;Company&gt;', response.read().decode())
        with app.connect() as db:
            record = db.execute('SELECT * FROM applications').fetchone()
            doc = db.execute('SELECT * FROM documents').fetchone()
        with urlopen(self.base + '/documents/' + doc['id']) as response:
            self.assertIn('attachment', response.headers['Content-Disposition'])
            self.assertIn(b'<script>', response.read())
        for status in ('rejected', 'applied'):
            data = urlencode({'token': app.TOKEN, 'id': record['id'], 'status': status}).encode()
            with urlopen(Request(self.base + '/status', data=data)) as response:
                self.assertIn('Engineer', response.read().decode())
            with urlopen(self.base + ('/' if status == 'rejected' else '/?view=archive')) as response:
                self.assertNotIn('Engineer', response.read().decode())
        with app.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM documents').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM status_events').fetchone()[0], 2)
        self.assertTrue((app.DATA / doc['path']).is_file())

    def test_invalid_upload_and_csrf_do_not_create_records(self):
        with self.assertRaises(HTTPError) as caught:
            self.add('bad.exe')
        self.assertEqual(caught.exception.code, 400)
        data = urlencode({'status': 'applied', 'company': 'x', 'role': 'y'}).encode()
        with self.assertRaises(HTTPError) as caught:
            urlopen(Request(self.base + '/applications', data=data))
        self.assertEqual(caught.exception.code, 403)
        with app.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM applications').fetchone()[0], 0)


if __name__ == '__main__':
    unittest.main()
