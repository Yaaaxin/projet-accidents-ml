import hashlib
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from uuid import uuid4

from src import download_data


class DownloadTests(unittest.TestCase):
    def test_verifies_before_writing_and_never_overwrites(self):
        root = download_data.ROOT / '.local' / ('download-test-' + uuid4().hex)
        (root / 'data').mkdir(parents=True)
        try:
            content = b'column\nvalue\n'
            record = {'path': 'data/test.csv', 'sha256': hashlib.sha256(content).hexdigest(),
                      'resource_url': 'https://example.invalid/test.csv'}
            (root / 'data/manifest.json').write_text(json.dumps({'files': [record]}))
            target = root / 'data/test.csv'
            with patch.object(download_data, 'ROOT', root):
                with patch('urllib.request.urlopen', return_value=io.BytesIO(b'changed')):
                    with self.assertRaises(ValueError):
                        download_data.download(root / 'data')
                self.assertFalse(target.exists())
                with patch('urllib.request.urlopen', return_value=io.BytesIO(content)):
                    download_data.download(root / 'data')
                self.assertEqual(target.read_bytes(), content)
                target.write_bytes(b'local edits')
                with patch('urllib.request.urlopen') as request:
                    with self.assertRaises(ValueError):
                        download_data.download(root / 'data')
                    request.assert_not_called()
                self.assertEqual(target.read_bytes(), b'local edits')
        finally:
            for path in (root / 'data').iterdir():
                path.unlink()
            (root / 'data').rmdir()
            root.rmdir()


if __name__ == '__main__':
    unittest.main()
