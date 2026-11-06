"""The Windows launcher must stay ASCII + CRLF.

The shipped start-vtuber.bat was UTF-8 Korean with LF-only newlines and ran
`chcp 65001`. Korean Windows cmd (CP949) treats bytes 0x81-0xFE as DBCS lead
bytes and its batch reader mishandles code page 65001, so commands were split.
Observed result: a garbled prefix, `'echo' is not recognized`, then a fragment
`'el' is not recognized`, then `pause`. GitHub ZIP files are the git blobs, so
the blob itself must contain CRLF. Mark the file `-text` or Git will store LF.
"""
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BAT = ROOT / 'start-vtuber.bat'


def assert_safe_launcher(data: bytes):
    if data.startswith(b'\xef\xbb\xbf') or data.startswith(b'\xff\xfe') or data.startswith(b'\xfe\xff'):
        raise AssertionError('BOM')
    if any(b > 127 for b in data):
        raise AssertionError('non-ASCII byte')
    if b'\n' in data.replace(b'\r\n', b''):
        raise AssertionError('bare LF')
    if b'\r' in data.replace(b'\r\n', b''):
        raise AssertionError('bare CR')
    if b'chcp ' in data.lower():
        raise AssertionError('chcp changes the code page and breaks batch parsing')
    text = data.decode('ascii')
    for line in (
        'cd /d "%~dp0"',
        'py -3 "%~dp0tools\\vtuber_relay.py"',
        'python "%~dp0tools\\vtuber_relay.py"',
        'where py >nul 2>&1',
        'where python >nul 2>&1',
        'pause',
    ):
        if line not in text:
            raise AssertionError('missing ' + line)


class LauncherTests(unittest.TestCase):
    def test_worktree_bytes(self):
        assert_safe_launcher(BAT.read_bytes())

    def test_gitattributes_disables_eol_conversion(self):
        attr = (ROOT / '.gitattributes').read_text(encoding='ascii')
        self.assertIn('start-vtuber.bat -text', attr)
        out = subprocess.check_output(
            ['git', 'check-attr', 'text', '--', 'start-vtuber.bat'],
            cwd=ROOT, text=True,
        )
        self.assertIn('unset', out)

    def test_old_utf8_lf_file_is_rejected(self):
        old = (
            '@echo off\n'
            'chcp 65001 >nul\n'
            'echo 픽셀\n'
            'pause\n'
        ).encode('utf-8')
        with self.assertRaises(AssertionError):
            assert_safe_launcher(old)

    def test_git_blob_keeps_crlf_when_staged_or_committed(self):
        staged = subprocess.run(
            ['git', 'show', ':start-vtuber.bat'],
            cwd=ROOT, capture_output=True,
        )
        if staged.returncode != 0:
            self.skipTest('launcher is not in the index yet')
        assert_safe_launcher(staged.stdout)


if __name__ == '__main__':
    unittest.main()
