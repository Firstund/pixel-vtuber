#!/usr/bin/env python3
"""Loopback static server + WebSocket relay for the pixel VTuber and music player.

OBS browser source (CEF) and Chrome/Edge do not share localStorage or BroadcastChannel.
This process is the only bridge. It forwards small JSON state and never sees camera
frames or microphone audio. Bind is limited to loopback unless --allow-remote is set.

  py -3 tools/vtuber_relay.py
  python tools/vtuber_relay.py
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import socket
import threading
import time
import urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
MAX_FRAME = 8192
ROOMS = {'vtuber', 'player'}
PUBLISHER = {'vtuber': 'track', 'player': 'control'}
LOOPBACK_HOSTS = {'127.0.0.1', 'localhost', '::1'}
BLEND_KEYS = (
    'jaw', 'funnel', 'smile', 'blink', 'blinkL', 'blinkR', 'gx', 'gy',
    'browDown', 'browOuter', 'brow', 'wide', 'yaw', 'pitch', 'roll',
    'stretch', 'smileAsym', 'puff', 'squint',
)
EXPRS = {'auto', 'happy', 'tired', 'surprised', 'smug'}
REACTS = {'surprise', 'tired', 'flustered', 'wink', 'happy', 'angry'}
PROPS = {'coffee', 'laptop', 'bag', 'plant'}
DEFAULT_CHAR = 'fox92'
CHARS = {
    'fox93', 'fox92', 'fox91', 'fox9', 'fox85', 'fox84', 'fox83', 'fox82', 'fox81',
    'fox8', 'fox71', 'fox7', 'fox65', 'fox64', 'fox63', 'fox62', 'fox61', 'fox6',
    'fox53', 'fox52', 'fox51', 'fox5', 'fox4', 'fox3', 'fox2', 'test',
}


def encode_frame(data: bytes, opcode: int = 1, mask: bytes | None = None) -> bytes:
    if len(data) > MAX_FRAME:
        raise ValueError('frame too large')
    n = len(data)
    hdr = bytearray([0x80 | (opcode & 0x0F)])
    length_bit = n
    if mask:
        length_bit |= 0x80
    if n < 126:
        hdr.append(length_bit)
    elif n < 65536:
        hdr.append(126 | (0x80 if mask else 0))
        hdr += n.to_bytes(2, 'big')
    else:
        hdr.append(127 | (0x80 if mask else 0))
        hdr += n.to_bytes(8, 'big')
    if mask:
        if len(mask) != 4:
            raise ValueError('mask')
        data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        return bytes(hdr) + mask + data
    return bytes(hdr) + data


def try_decode_frame(buf: bytearray, require_mask: bool = False):
    """Return (opcode, payload, consumed) or None if the buffer is incomplete."""
    if len(buf) < 2:
        return None
    if (buf[0] & 0x80) == 0:
        raise ValueError('fragmented frames are not accepted')
    opcode = buf[0] & 0x0F
    ln = buf[1] & 0x7F
    masked = bool(buf[1] & 0x80)
    if require_mask and not masked:
        raise ValueError('client frames must be masked')
    pos = 2
    if ln == 126:
        if len(buf) < pos + 2:
            return None
        ln = int.from_bytes(buf[pos:pos + 2], 'big')
        pos += 2
    elif ln == 127:
        if len(buf) < pos + 8:
            return None
        ln = int.from_bytes(buf[pos:pos + 8], 'big')
        pos += 8
    if ln > MAX_FRAME:
        raise ValueError('frame too large')
    if masked:
        if len(buf) < pos + 4 + ln:
            return None
        mask = bytes(buf[pos:pos + 4])
        pos += 4
        raw = bytes(buf[pos:pos + ln])
        data = bytes(b ^ mask[i % 4] for i, b in enumerate(raw))
        pos += ln
    else:
        if len(buf) < pos + ln:
            return None
        data = bytes(buf[pos:pos + ln])
        pos += ln
    return opcode, data, pos


def _num(v, lo, hi, default=0.0):
    try:
        n = float(v)
    except (TypeError, ValueError):
        return None
    if n != n or n in (float('inf'), float('-inf')):
        return None
    return max(lo, min(hi, n))


def _bool(v):
    return bool(v) if isinstance(v, bool) else None


def sanitize_state(room: str, payload):
    if not isinstance(payload, dict):
        return None
    if room == 'vtuber':
        return _sanitize_vtuber(payload)
    if room == 'player':
        return _sanitize_player(payload)
    return None


def _sanitize_vtuber(p):
    blend_in = p.get('b')
    if not isinstance(blend_in, dict):
        return None
    b = {}
    for k in BLEND_KEYS:
        n = _num(blend_in.get(k, 0), -180, 180, 0)
        if n is None:
            return None
        b[k] = round(n, 3)
    expr = p.get('expr') or 'auto'
    if expr not in EXPRS:
        return None
    react = p.get('react')
    if react in ('', None):
        react = None
    elif react not in REACTS:
        return None
    mic_on = p.get('micOn')
    if not isinstance(mic_on, bool):
        mic_on = False
    mic_score = _num(p.get('micScore', 0), 0, 1, 0)
    if mic_score is None:
        return None
    face = p.get('face')
    if not isinstance(face, bool):
        face = False
    cfg = _sanitize_cfg(p.get('cfg'))
    seq = p.get('seq', 0)
    try:
        seq = int(seq)
    except (TypeError, ValueError):
        seq = 0
    out = {
        'kind': 'vtuber',
        'seq': max(0, min(seq, 2**31 - 1)),
        'face': face,
        'b': b,
        'micOn': mic_on,
        'micScore': round(mic_score, 3),
        'expr': expr,
        'react': react,
    }
    if cfg is not None:
        out['cfg'] = cfg
    return out


def _sanitize_cfg(cfg):
    if cfg is None:
        return None
    if not isinstance(cfg, dict):
        return None
    out = {}
    char = cfg.get('char')
    if isinstance(char, str) and char in CHARS:
        out['char'] = char
    for key in ('mirror', 'choppy', 'micExpr', 'autoBlink', 'breath'):
        bit = _bool(cfg.get(key))
        if bit is not None:
            out[key] = bit
    for key, lo, hi in (
        ('animFps', 6, 30), ('tMouth', 0, 1), ('tBlink', 0, 1),
        ('tSmile', 0, 1), ('smooth', 0, 0.95),
    ):
        if key in cfg:
            n = _num(cfg.get(key), lo, hi)
            if n is None:
                continue
            out[key] = int(n) if key == 'animFps' else round(n, 3)
    props = cfg.get('props')
    if isinstance(props, list):
        clean = []
        for item in props[:8]:
            if isinstance(item, str) and item in PROPS and item not in clean:
                clean.append(item)
        out['props'] = clean
    return out


def _sanitize_player(p):
    if _bool(p.get('playing')) is None and not isinstance(p.get('playing'), bool):
        return None
    playing = bool(p.get('playing'))
    try:
        ci = int(p.get('ci', 0))
        ti = int(p.get('ti', 0))
        oi = int(p.get('oi', 0))
    except (TypeError, ValueError):
        return None
    if not (0 <= ci <= 32 and 0 <= ti <= 500 and 0 <= oi <= 500):
        return None
    cat_id = p.get('catId') if isinstance(p.get('catId'), str) else ''
    cat_name = p.get('catName') if isinstance(p.get('catName'), str) else ''
    file = p.get('file') if isinstance(p.get('file'), str) else ''
    title = p.get('title') if isinstance(p.get('title'), str) else ''
    if max(len(cat_id), len(cat_name), len(title)) > 180 or len(file) > 240:
        return None
    if any(x in file for x in ('..', '\\', '\n', '\x00')):
        return None
    order_in = p.get('order')
    order = []
    if isinstance(order_in, list):
        if len(order_in) > 500:
            return None
        for item in order_in:
            try:
                n = int(item)
            except (TypeError, ValueError):
                return None
            if not 0 <= n <= 500:
                return None
            order.append(n)
    shuffle = p.get('shuffle')
    if not isinstance(shuffle, bool):
        shuffle = False
    vol = _num(p.get('vol', 0.6), 0, 1)
    offset = _num(p.get('offset', 0), 0, 60 * 60 * 6)
    dur = _num(p.get('dur', 0), 0, 60 * 60 * 6)
    sent = _num(p.get('sentAt', 0), 0, 1e15)
    if None in (vol, offset, dur, sent):
        return None
    return {
        'kind': 'player',
        'playing': playing,
        'ci': ci,
        'ti': ti,
        'oi': oi,
        'catId': cat_id,
        'catName': cat_name,
        'file': file,
        'title': title,
        'order': order,
        'shuffle': shuffle,
        'vol': round(vol, 3),
        'offset': round(offset, 3),
        'dur': round(dur, 3),
        'sentAt': int(sent),
    }


def choose_audible(clients):
    """Pick exactly one player-room client that may unmute, or None.

    Displays are preferred in connection order. A display that reported
    audio='blocked' is skipped. If every display is blocked, the oldest
    controller is the audible one so the streamer still hears music once.
    """
    displays = [c for c in clients if c.role == 'display' and c.room == 'player']
    controls = [c for c in clients if c.role == 'control' and c.room == 'player']
    for c in displays:
        if c.media != 'blocked':
            return c.id
    if controls:
        return controls[0].id
    return None


class Client:
    def __init__(self, cid, role, room, send):
        self.id = cid
        self.role = role
        self.room = room
        self.media = 'unknown'
        self.send = send
        self.connected_at = time.monotonic()


class Relay:
    def __init__(self):
        self._lock = threading.Lock()
        self.clients = {}
        self.last = {}
        self._seq = 0
        self._pinger = threading.Thread(target=self._ping_loop, daemon=True)
        self._pinger.start()

    def _ping_loop(self):
        while True:
            time.sleep(5)
            with self._lock:
                members = list(self.clients.values())
            for c in members:
                c.send({'type': 'ping', 't': int(time.time())})

    def _next_id(self):
        self._seq += 1
        return f'c{self._seq}'

    def hello(self, role, room, send):
        if role not in ('track', 'display', 'control') or room not in ROOMS:
            return None
        if role != 'display' and role != PUBLISHER[room]:
            return None
        with self._lock:
            cid = self._next_id()
            client = Client(cid, role, room, send)
            self.clients[cid] = client
            welcome = {'type': 'welcome', 'room': room, 'role': role, 'clientId': cid}
            peers = self._peers_locked(room)
            replay = self.last.get(room)
        send(welcome)
        self._broadcast(room, peers)
        if replay is not None:
            send({'type': 'state', 'room': room, 'payload': replay, 'replay': True})
        return client

    def disconnect(self, cid):
        with self._lock:
            client = self.clients.pop(cid, None)
            room = client.room if client else None
            peers = self._peers_locked(room) if room else None
        if room and peers:
            self._broadcast(room, peers)

    def publish(self, cid, payload):
        with self._lock:
            client = self.clients.get(cid)
            if not client or client.role != PUBLISHER[client.room]:
                return False
            clean = sanitize_state(client.room, payload)
            if clean is None:
                return False
            self.last[client.room] = clean
            room = client.room
            targets = [c for c in self.clients.values() if c.room == room and c.id != cid]
        msg = {'type': 'state', 'room': room, 'payload': clean}
        for c in targets:
            c.send(msg)
        return True

    def media(self, cid, audio):
        if audio not in ('ok', 'blocked'):
            return False
        with self._lock:
            client = self.clients.get(cid)
            if not client or client.role != 'display' or client.room != 'player':
                return False
            if client.media == audio:
                return True
            client.media = audio
            peers = self._peers_locked(client.room)
            room = client.room
        self._broadcast(room, peers)
        return True

    def _peers_locked(self, room):
        members = [c for c in self.clients.values() if c.room == room]
        members.sort(key=lambda c: c.connected_at)
        audible = choose_audible(members) if room == 'player' else None
        roles = {'track': 0, 'display': 0, 'control': 0}
        for c in members:
            roles[c.role] += 1
        audible_role = None
        if audible:
            audible_role = self.clients[audible].role
        return {
            'type': 'peers',
            'room': room,
            'roles': roles,
            'audibleId': audible,
            'audibleRole': audible_role,
            '_you': {c.id: c.id == audible for c in members},
        }

    def _broadcast(self, room, peers):
        you = peers.get('_you', {})
        with self._lock:
            members = [c for c in self.clients.values() if c.room == room]
        for c in members:
            msg = {
                'type': 'peers',
                'room': room,
                'roles': peers['roles'],
                'audibleId': peers['audibleId'],
                'audibleRole': peers['audibleRole'],
                'youAudible': bool(you.get(c.id, False)),
                'clientId': c.id,
            }
            c.send(msg)


def origin_ok(origin: str | None) -> bool:
    if not origin or origin in ('null', 'None'):
        return True
    try:
        host = (urllib.parse.urlparse(origin).hostname or '').lower()
    except ValueError:
        return False
    return host in LOOPBACK_HOSTS


class WsSession:
    def __init__(self, handler, relay: Relay):
        self.handler = handler
        self.relay = relay
        self.buf = bytearray()
        self.client = None
        self.alive = True
        self.send_lock = threading.Lock()

    def send_json(self, obj):
        if not self.alive:
            return
        data = json.dumps(obj, separators=(',', ':')).encode()
        try:
            with self.send_lock:
                self.handler.wfile.write(encode_frame(data, 1))
                self.handler.wfile.flush()
        except (OSError, ValueError):
            self.alive = False

    def send_pong(self, data: bytes):
        try:
            with self.send_lock:
                self.handler.wfile.write(encode_frame(data, 0xA))
                self.handler.wfile.flush()
        except OSError:
            self.alive = False

    def run(self):
        rfile = self.handler.rfile
        try:
            while self.alive:
                chunk = rfile.read1(4096) if hasattr(rfile, 'read1') else rfile.read(1)
                if not chunk:
                    break
                self.buf += chunk
                while True:
                    decoded = try_decode_frame(self.buf, require_mask=True)
                    if not decoded:
                        break
                    opcode, data, consumed = decoded
                    del self.buf[:consumed]
                    self._on_frame(opcode, data)
        except (ValueError, OSError, json.JSONDecodeError):
            pass
        finally:
            self.alive = False
            if self.client:
                self.relay.disconnect(self.client.id)
                self.client = None

    def _on_frame(self, opcode, data: bytes):
        if opcode == 0x8:
            self.alive = False
            return
        if opcode == 0x9:
            self.send_pong(data)
            return
        if opcode == 0xA:
            return
        if opcode != 0x1:
            self.alive = False
            return
        msg = json.loads(data.decode())
        if not isinstance(msg, dict):
            return
        kind = msg.get('type')
        if self.client is None:
            if kind != 'hello':
                self.alive = False
                return
            client = self.relay.hello(msg.get('role'), msg.get('room'), self.send_json)
            if client is None:
                self.send_json({'type': 'error', 'error': 'role'})
                self.alive = False
                return
            self.client = client
            return
        if kind == 'state':
            self.relay.publish(self.client.id, msg.get('payload'))
        elif kind == 'media':
            self.relay.media(self.client.id, msg.get('audio'))
        elif kind == 'drop':
            self.alive = False


def build_handler(relay: Relay):
    class Handler(SimpleHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(ROOT), **kwargs)

        def log_message(self, fmt, *args):
            return

        def do_GET(self):
            path = urllib.parse.unquote(urllib.parse.urlparse(self.path).path)
            if '/.git' in path or path.startswith('/.git'):
                self.send_error(404)
                return
            if path == '/health':
                body = b'{"ok":true,"service":"vtuber-relay"}'
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(body)
                return
            if path == '/ws':
                self._upgrade()
                return
            return super().do_GET()

        def _upgrade(self):
            if not origin_ok(self.headers.get('Origin')):
                self.send_error(403, 'local origin only')
                return
            key = self.headers.get('Sec-WebSocket-Key')
            if not key or self.headers.get('Upgrade', '').lower() != 'websocket':
                self.send_error(400, 'expected websocket')
                return
            accept = base64.b64encode(hashlib.sha1((key + GUID).encode()).digest()).decode()
            self.close_connection = True
            self.send_response(101, 'Switching Protocols')
            self.send_header('Upgrade', 'websocket')
            self.send_header('Connection', 'Upgrade')
            self.send_header('Sec-WebSocket-Accept', accept)
            self.end_headers()
            try:
                self.wfile.flush()
            except OSError:
                return
            WsSession(self, relay).run()

    return Handler


class Server(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def serve_background(port=0, host='127.0.0.1'):
    relay = Relay()
    httpd = Server((host, port), build_handler(relay))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, relay


def _urls(port: int) -> str:
    base = f'http://127.0.0.1:{port}'
    return '\n'.join([
        '픽셀 VTuber / 음악 로컬 중계 (127.0.0.1 전용)',
        f'  추적(크롬):  {base}/?role=track&char={DEFAULT_CHAR}',
        f'  OBS 표시:   {base}/?role=display&obs=1&char={DEFAULT_CHAR}',
        f'  음악 조작:  {base}/player/?role=control&shuffle=1&vol=0.5',
        f'  음악 OBS:   {base}/player/?role=display&obs=1',
        '카메라 영상과 마이크 소리는 나가지 않습니다. 표정·재생 상태만 전달합니다.',
        '끝내기: Ctrl+C',
    ])


def main(argv=None):
    parser = argparse.ArgumentParser(description='Loopback VTuber/player state relay')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--allow-remote', action='store_true')
    args = parser.parse_args(argv)
    host = args.host
    if host not in LOOPBACK_HOSTS and not args.allow_remote:
        raise SystemExit('기본은 127.0.0.1 전용입니다. 외부 공개는 --allow-remote 가 있어야 합니다.')
    os.chdir(ROOT)
    httpd = Server((host, args.port), build_handler(Relay()))
    port = httpd.server_address[1]
    print(_urls(port), flush=True)
    print('주소는 127.0.0.1 만 사용하세요. localhost 가 ::1 로 가면 연결되지 않습니다.', flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\n중계를 멈췄습니다.')
    finally:
        httpd.shutdown()
        httpd.server_close()


class SyncClient:
    """Blocking WebSocket client used by tests and one-off probes."""

    def __init__(self, port: int, host: str = '127.0.0.1', timeout: float = 5, origin: str | None = None):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        if origin is None:
            origin = f'http://{host}:{port}'
        origin_line = f'Origin: {origin}\r\n' if origin != '' else ''
        req = (
            f'GET /ws HTTP/1.1\r\nHost: {host}:{port}\r\n'
            'Upgrade: websocket\r\nConnection: Upgrade\r\n'
            f'Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n'
            f'{origin_line}\r\n'
        )
        self.sock.sendall(req.encode())
        buf = b''
        while b'\r\n\r\n' not in buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError('handshake closed')
            buf += chunk
        head, rest = buf.split(b'\r\n\r\n', 1)
        status = head.split(b'\r\n', 1)[0]
        if b' 101 ' not in status:
            self.sock.close()
            raise ConnectionError(status.decode('latin1', 'replace'))
        self.buf = bytearray(rest)

    def send_json(self, obj):
        frame = encode_frame(
            json.dumps(obj, separators=(',', ':')).encode(),
            1,
            mask=os.urandom(4),
        )
        self.sock.sendall(frame)

    def recv_json(self, timeout: float = 5):
        deadline = time.time() + timeout
        while True:
            decoded = try_decode_frame(self.buf)
            if decoded:
                opcode, data, consumed = decoded
                del self.buf[:consumed]
                if opcode == 0x9:
                    self.sock.sendall(encode_frame(data, 0xA, mask=os.urandom(4)))
                    continue
                if opcode == 0x1:
                    return json.loads(data.decode())
                if opcode == 0x8:
                    raise ConnectionError('closed')
                continue
            if time.time() > deadline:
                raise TimeoutError('websocket recv')
            self.sock.settimeout(max(0.1, deadline - time.time()))
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError('closed')
            self.buf += chunk

    def recv_type(self, type_name: str, timeout: float = 5):
        deadline = time.time() + timeout
        while True:
            left = deadline - time.time()
            if left <= 0:
                raise TimeoutError(type_name)
            msg = self.recv_json(left)
            if msg.get('type') == type_name:
                return msg

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


if __name__ == '__main__':
    main()
