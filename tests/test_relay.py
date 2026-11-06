"""Relay tests: separate processes, rooms, one audible player, late join, reconnect."""
import json
import os
import subprocess
import sys
import textwrap
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import vtuber_relay as relay  # noqa: E402


def vtuber_payload(**over):
    b = {k: 0 for k in relay.BLEND_KEYS}
    b.update(over.pop('b', {}))
    base = {
        'kind': 'vtuber', 'seq': 1, 'face': True, 'b': b,
        'micOn': False, 'micScore': 0, 'expr': 'auto', 'react': None,
    }
    base.update(over)
    return base


def player_payload(**over):
    base = {
        'kind': 'player', 'playing': True, 'ci': 0, 'ti': 0, 'oi': 0,
        'catId': 'opening', 'catName': '출근 도장',
        'file': 'audio/opening/opening_B_3min_loop.mp3',
        'title': '문이 열리는 시간', 'order': [0], 'shuffle': True,
        'vol': 0.5, 'offset': 3.25, 'dur': 180, 'sentAt': 1_700_000_000_000,
    }
    base.update(over)
    return base


class DefaultCharTests(unittest.TestCase):
    def test_default_is_fox92_and_explicit_ids_remain(self):
        self.assertEqual(relay.DEFAULT_CHAR, 'fox92')
        text = relay._urls(8765)
        self.assertIn('/?role=track&char=fox92', text)
        self.assertIn('/?role=display&obs=1&char=fox92', text)
        self.assertNotIn('char=fox91', text)
        self.assertNotIn('char=fox93', text)
        for key in ('fox91', 'fox92', 'fox93'):
            self.assertIn(key, relay.CHARS)
            manifest = json.loads((ROOT / 'assets' / key / 'manifest.json').read_text())
            self.assertEqual(manifest['mode'], 'face')
            self.assertTrue(manifest['layers'])
        html = (ROOT / 'index.html').read_text()
        self.assertIn('value="fox92" selected', html)
        self.assertNotIn('value="fox91" selected', html)
        self.assertIn('value="fox91"', html)
        self.assertIn('value="fox93"', html)
        app = (ROOT / 'js/app.js').read_text()
        self.assertIn('DEFAULT_CHAR', app)
        self.assertNotIn('CHARS.fox91', app)
        self.assertIn("fox91: 'assets/fox91/'", app)
        self.assertIn("fox93: 'assets/fox93/'", app)


class SanitizeTests(unittest.TestCase):
    def test_strips_frames_and_audio_blobs(self):
        raw = vtuber_payload(b={'jaw': 0.42, 'yaw': 33})
        raw['image'] = 'a' * 5000
        raw['pcm'] = [1, 2, 3]
        clean = relay.sanitize_state('vtuber', raw)
        self.assertNotIn('image', clean)
        self.assertNotIn('pcm', clean)
        self.assertEqual(clean['b']['jaw'], 0.42)
        self.assertEqual(clean['b']['yaw'], 33)

    def test_rejects_path_escape_and_huge_title(self):
        self.assertIsNone(relay.sanitize_state('player', player_payload(file='../secret.mp3')))
        self.assertIsNone(relay.sanitize_state('player', player_payload(title='x' * 500)))
        ok = relay.sanitize_state('player', player_payload())
        self.assertEqual(ok['vol'], 0.5)
        self.assertEqual(ok['file'], 'audio/opening/opening_B_3min_loop.mp3')

    def test_one_audible_player(self):
        def c(i, role, media='unknown'):
            return type('C', (), {'id': i, 'role': role, 'room': 'player', 'media': media})()
        a, b, ctrl = c('a', 'display'), c('b', 'display'), c('c', 'control')
        self.assertEqual(relay.choose_audible([a, b, ctrl]), 'a')
        a.media = 'blocked'
        self.assertEqual(relay.choose_audible([a, b, ctrl]), 'b')
        b.media = 'blocked'
        self.assertEqual(relay.choose_audible([a, b, ctrl]), 'c')
        self.assertIsNone(relay.choose_audible([type('C', (), {'id': 't', 'role': 'track', 'room': 'vtuber', 'media': 'unknown'})()]))


class SocketTests(unittest.TestCase):
    def setUp(self):
        self.httpd, self.hub = relay.serve_background(0)
        self.port = self.httpd.server_address[1]
        self.clients = []

    def tearDown(self):
        for c in self.clients:
            c.close()
        self.httpd.shutdown()
        self.httpd.server_close()

    def client(self, **kw):
        c = relay.SyncClient(self.port, **kw)
        self.clients.append(c)
        return c

    def test_cross_process_and_rooms(self):
        env = os.environ.copy()
        env['PYTHONPATH'] = str(ROOT / 'tools')
        code = textwrap.dedent(r'''
            import json, sys, time
            import vtuber_relay as r
            role, port, room = sys.argv[1], int(sys.argv[2]), sys.argv[3]
            c = r.SyncClient(port)
            c.send_json({"type": "hello", "role": role, "room": room})
            c.recv_type("welcome", 5)
            if role == "display":
                print("READY", flush=True)
                msg = c.recv_type("state", 8)
                print(json.dumps({"jaw": msg["payload"]["b"]["jaw"], "room": msg["room"], "mic": msg["payload"]["micScore"]}), flush=True)
                time.sleep(0.4)
            else:
                c.recv_type("peers", 5)
                b = {k: 0 for k in r.BLEND_KEYS}
                b["jaw"] = 0.77
                c.send_json({"type": "state", "room": "vtuber", "payload": {
                    "kind": "vtuber", "seq": 4, "face": True, "b": b,
                    "micOn": True, "micScore": 0.4, "expr": "happy", "react": None}})
                time.sleep(0.4)
            c.close()
        ''')
        display = subprocess.Popen(
            [sys.executable, '-c', code, 'display', str(self.port), 'vtuber'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
        )
        ready = display.stdout.readline().strip()
        self.assertEqual(ready, 'READY')
        track = subprocess.Popen(
            [sys.executable, '-c', code, 'track', str(self.port), 'vtuber'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
        )
        line = display.stdout.readline().strip()
        track.wait(timeout=5)
        display.wait(timeout=5)
        track_err = track.stderr.read()
        display_err = display.stderr.read()
        for stream in (display.stdout, display.stderr, track.stdout, track.stderr):
            stream.close()
        self.assertEqual(track.returncode, 0, track_err)
        self.assertEqual(display.returncode, 0, display_err)
        got = json.loads(line)
        self.assertEqual(got['jaw'], 0.77)
        self.assertEqual(got['mic'], 0.4)
        self.assertEqual(got['room'], 'vtuber')

    def test_late_join_replay_and_player_audible(self):
        control = self.client()
        control.send_json({'type': 'hello', 'role': 'control', 'room': 'player'})
        control.recv_type('welcome')
        first = control.recv_type('peers')
        self.assertTrue(first['youAudible'])
        self.assertEqual(first['roles']['display'], 0)
        control.send_json({'type': 'state', 'room': 'player', 'payload': player_payload(playing=False, offset=12)})
        # bad payload must not replace the snapshot
        control.send_json({'type': 'state', 'room': 'player', 'payload': {'kind': 'player', 'file': '../x', 'playing': True}})
        time.sleep(0.05)
        display = self.client()
        display.send_json({'type': 'hello', 'role': 'display', 'room': 'player'})
        display.recv_type('welcome')
        peers = display.recv_type('peers')
        state = display.recv_type('state')
        self.assertTrue(state.get('replay'))
        self.assertEqual(state['payload']['offset'], 12)
        self.assertFalse(state['payload']['playing'])
        self.assertTrue(peers['youAudible'])
        control_peers = control.recv_type('peers')
        self.assertFalse(control_peers['youAudible'])
        self.assertEqual(control_peers['audibleRole'], 'display')
        other = self.client()
        other.send_json({'type': 'hello', 'role': 'display', 'room': 'player'})
        other.recv_type('welcome')
        other_peers = other.recv_type('peers')
        self.assertFalse(other_peers['youAudible'])
        self.assertGreaterEqual(other_peers['roles']['display'], 2)
        joined = control.recv_type('peers')
        self.assertFalse(joined['youAudible'])
        self.assertEqual(joined['audibleRole'], 'display')
        # First display blocked → the other display is the only audible client.
        display.send_json({'type': 'media', 'audio': 'blocked'})
        moved = control.recv_type('peers')
        self.assertFalse(moved['youAudible'])
        self.assertEqual(moved['audibleRole'], 'display')
        self.assertNotEqual(moved['audibleId'], peers['clientId'])
        other.send_json({'type': 'media', 'audio': 'blocked'})
        back = control.recv_type('peers')
        self.assertTrue(back['youAudible'])
        self.assertEqual(back['audibleRole'], 'control')

    def test_room_isolation_and_foreign_origin(self):
        watch = self.client()
        watch.send_json({'type': 'hello', 'role': 'display', 'room': 'player'})
        watch.recv_type('welcome')
        track = self.client()
        track.send_json({'type': 'hello', 'role': 'track', 'room': 'vtuber'})
        track.recv_type('welcome')
        b = {k: 0 for k in relay.BLEND_KEYS}
        b['smile'] = 0.9
        track.send_json({'type': 'state', 'room': 'vtuber', 'payload': vtuber_payload(b={'smile': 0.9})})
        watch.sock.settimeout(0.3)
        with self.assertRaises(Exception):
            watch.recv_type('state', 0.3)
        with self.assertRaises(ConnectionError):
            relay.SyncClient(self.port, origin='https://firstund.github.io')

    def test_reconnect_gets_new_state(self):
        display = self.client()
        display.send_json({'type': 'hello', 'role': 'display', 'room': 'vtuber'})
        display.recv_type('welcome')
        track = self.client()
        track.send_json({'type': 'hello', 'role': 'track', 'room': 'vtuber'})
        track.recv_type('welcome')
        track.send_json({'type': 'state', 'room': 'vtuber', 'payload': vtuber_payload(b={'jaw': 0.2})})
        self.assertEqual(display.recv_type('state')['payload']['b']['jaw'], 0.2)
        track.close()
        self.clients.remove(track)
        track2 = self.client()
        track2.send_json({'type': 'hello', 'role': 'track', 'room': 'vtuber'})
        track2.recv_type('welcome')
        track2.send_json({'type': 'state', 'room': 'vtuber', 'payload': vtuber_payload(b={'jaw': 0.55}, seq=2)})
        self.assertEqual(display.recv_type('state')['payload']['b']['jaw'], 0.55)

    def test_artwork_untouched(self):
        for key in ('fox91', 'fox92', 'fox93'):
            manifest = json.loads((ROOT / 'assets' / key / 'manifest.json').read_text())
            for layer in manifest['layers']:
                self.assertTrue((ROOT / 'assets' / key / f'{layer}.png').is_file(), layer)
        player = (ROOT / 'player' / 'player.js').read_text()
        self.assertIn('listen', player)
        self.assertNotIn('getUserMedia', player)
        self.assertNotIn('BroadcastChannel', player)
        link = (ROOT / 'js' / 'link.js').read_text()
        self.assertNotIn('new BroadcastChannel', link)
        self.assertNotIn('localStorage.getItem', link)
        self.assertNotIn('localStorage.setItem', link)


if __name__ == '__main__':
    unittest.main()
