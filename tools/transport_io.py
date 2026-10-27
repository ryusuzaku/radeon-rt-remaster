"""Reference codec and session monitor for the proxy/renderer transport protocol.

The layout comes from docs/schemas/transport-v1.json; src/transport/transport.h
implements the same rules in C++ and the transport_layout ctest compares the two on
golden vectors. See docs/TRANSPORT_PROTOCOL.md.

`Session.feed(direction, data)` is a protocol monitor: both endpoints feed it every
message they send and receive, in order. It returns an error name (or 'ok') and
leaves the state untouched on any error, so the caller decides whether to close.
"""
import json
from pathlib import Path
import struct

SCHEMA_PATH = Path(__file__).resolve().parents[1] / 'docs' / 'schemas' / 'transport-v1.json'
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding='utf-8'))

P2R = 'p2r'
R2P = 'r2p'
_FORMAT = {'u16': 'H', 'u32': 'I', 'u64': 'Q'}
_SIZE = {'u16': 2, 'u32': 4, 'u64': 8}
HEADER_SIZE = SCHEMA['header']['size']
MAGIC = SCHEMA['magic']
MAX_MESSAGE_BYTES = SCHEMA['max_message_bytes']
MAX_IN_FLIGHT = SCHEMA['max_in_flight']
SUPPORTED_VERSIONS = tuple(SCHEMA['supported_versions'])
FLAG_SUPERSEDE_PENDING = 1 << SCHEMA['header_flags']['SUPERSEDE_PENDING']['bit']
MAX_DIMENSION = 16384
MAX_SLOTS = 8
ERRORS = tuple(SCHEMA['errors'])
HELLO_ACK_STATUS = SCHEMA['hello_ack_status']
FRAME_COMPLETE_STATUS = SCHEMA['frame_complete_status']
MESSAGES = {m['name']: m for m in SCHEMA['messages']}
BY_TYPE = {m['type']: m for m in SCHEMA['messages']}
DIRECTION = {'proxy->renderer': P2R, 'renderer->proxy': R2P}
GENERATIONS = ('scene_generation', 'camera_generation', 'lighting_generation', 'material_generation', 'settings_generation')


class TransportError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _pack_fields(fields, values):
    out = bytearray()
    for field in fields:
        assert field['offset'] == len(out), f'{field["name"]}: schema layout has a gap'
        out += struct.pack('<' + _FORMAT[field['type']], values.get(field['name'], 0))
    return bytes(out)


def _unpack_fields(fields, data):
    return {f['name']: struct.unpack_from('<' + _FORMAT[f['type']], data, f['offset'])[0] for f in fields}


def encode(name, values=None, sequence=1, frame_id=0, flags=0, version=1, magic=MAGIC):
    message = MESSAGES[name]
    payload = _pack_fields(message['fields'], values or {})
    assert len(payload) == message['payload_size'], f'{name}: payload size differs from the schema'
    header = struct.pack('<IHHIIQQ', magic, version, message['type'], len(payload), flags, sequence, frame_id)
    return header + payload


def parse(data):
    """Structural checks that need no session state. Returns (header, name, fields)."""
    if len(data) < HEADER_SIZE:
        raise TransportError('short_header')
    if len(data) > MAX_MESSAGE_BYTES:
        raise TransportError('oversized')
    magic, version, type_, payload_bytes, flags, sequence, frame_id = struct.unpack_from('<IHHIIQQ', data, 0)
    if magic != MAGIC:
        raise TransportError('bad_magic')
    if version not in SUPPORTED_VERSIONS:
        raise TransportError('bad_version')
    message = BY_TYPE.get(type_)
    if message is None:
        raise TransportError('unknown_type')
    if payload_bytes != message['payload_size'] or len(data) != HEADER_SIZE + payload_bytes:
        raise TransportError('payload_size_mismatch')
    allowed = FLAG_SUPERSEDE_PENDING if message['name'] == 'FrameSubmit' else 0
    if flags & ~allowed:
        raise TransportError('bad_flags')
    header = dict(magic=magic, version=version, type=type_, payload_bytes=payload_bytes, flags=flags, sequence=sequence, frame_id=frame_id)
    return header, message['name'], _unpack_fields(message['fields'], data[HEADER_SIZE:])


def negotiate(proxy_min, proxy_max):
    common = [v for v in SUPPORTED_VERSIONS if proxy_min <= v <= proxy_max]
    return max(common) if common else 0


class Session:
    """Protocol monitor shared by both endpoints."""

    def __init__(self):
        self.next_sequence = {P2R: 1, R2P: 1}
        self.hello = None
        self.ack_status = None
        self.selected = 0
        self.closed = False
        self.stopping = False
        self.last_frame = 0
        self.outstanding = []  # oldest first: dicts with frame_id, fence_value, resource_slot and generations
        self.completed = 0
        self.discarded = 0

    @property
    def ready(self):
        return self.ack_status == HELLO_ACK_STATUS['ok'] and not self.closed

    def feed(self, direction, data):
        try:
            header, name, f = parse(data)
        except TransportError as error:
            return error.code
        message = MESSAGES[name]
        if DIRECTION[message['direction']] != direction:
            return 'wrong_direction'
        if header['sequence'] != self.next_sequence[direction]:
            return 'out_of_sequence'
        if self.closed:
            return 'unexpected_state'
        if self.hello is not None and self.selected and header['version'] != self.selected:
            return 'bad_version'
        code = getattr(self, '_on_' + name)(header, f)
        if code == 'ok':
            self.next_sequence[direction] += 1
        return code

    def _on_Hello(self, header, f):
        if self.hello is not None:
            return 'unexpected_state'
        if header['frame_id'] != 0:
            return 'bad_frame_id'
        if f['reserved'] != 0:
            return 'reserved_nonzero'
        if not 1 <= f['min_version'] <= f['max_version']:
            return 'bad_field'
        self.hello = f
        return 'ok'

    def _on_HelloAck(self, header, f):
        if self.hello is None or self.ack_status is not None:
            return 'unexpected_state'
        if header['frame_id'] != 0:
            return 'bad_frame_id'
        if f['reserved'] != 0:
            return 'reserved_nonzero'
        if f['status'] not in HELLO_ACK_STATUS.values():
            return 'bad_field'
        selected = negotiate(self.hello['min_version'], self.hello['max_version'])
        if f['status'] == HELLO_ACK_STATUS['ok']:
            if f['selected_version'] != selected or not selected or header['version'] != selected:
                return 'bad_field'
            if f['adapter_luid'] != self.hello['adapter_luid'] or f['max_in_flight'] != MAX_IN_FLIGHT:
                return 'bad_field'
            self.selected = selected
        else:
            if f['selected_version'] != 0 or f['max_in_flight'] != 0:
                return 'bad_field'
            if f['status'] == HELLO_ACK_STATUS['version_mismatch'] and selected:
                return 'bad_field'
            if f['status'] == HELLO_ACK_STATUS['adapter_mismatch'] and (not selected or f['adapter_luid'] == self.hello['adapter_luid']):
                return 'bad_field'
            self.closed = True
        self.ack_status = f['status']
        return 'ok'

    def _on_FrameSubmit(self, header, f):
        if not self.ready or self.stopping:
            return 'unexpected_state'
        if header['frame_id'] == 0 or header['frame_id'] <= self.last_frame:
            return 'bad_frame_id'
        if not (1 <= f['width'] <= MAX_DIMENSION and 1 <= f['height'] <= MAX_DIMENSION and f['resource_slot'] < MAX_SLOTS):
            return 'bad_field'
        if f['reserved'] != 0:
            return 'reserved_nonzero'
        supersede = bool(header['flags'] & FLAG_SUPERSEDE_PENDING)
        if len(self.outstanding) >= MAX_IN_FLIGHT and not supersede:
            return 'too_many_in_flight'
        if len(self.outstanding) >= MAX_IN_FLIGHT:
            self.outstanding.pop()  # the pending frame; the active one keeps running
            self.discarded += 1
        self.last_frame = header['frame_id']
        entry = dict(frame_id=header['frame_id'], fence_value=f['fence_value'], resource_slot=f['resource_slot'])
        entry.update({g: f[g] for g in GENERATIONS})
        self.outstanding.append(entry)
        return 'ok'

    def _on_FrameComplete(self, header, f):
        if not self.ready:
            return 'unexpected_state'
        entry = next((e for e in self.outstanding if e['frame_id'] == header['frame_id']), None)
        if entry is None:
            return 'unknown_frame'
        if f['reserved32'] != 0 or f['reserved'] != 0:
            return 'reserved_nonzero'
        if f['status'] not in FRAME_COMPLETE_STATUS.values():
            return 'bad_field'
        if f['resource_slot'] != entry['resource_slot'] or any(f[g] != entry[g] for g in GENERATIONS):
            return 'generation_mismatch'
        if f['fence_value'] < entry['fence_value']:
            return 'bad_field'
        self.outstanding.remove(entry)
        if f['status'] == FRAME_COMPLETE_STATUS['discarded']:
            self.discarded += 1
        else:
            self.completed += 1
        return 'ok'

    def _on_Stop(self, header, f):
        if not self.ready or self.stopping:
            return 'unexpected_state'
        if header['frame_id'] != 0:
            return 'bad_frame_id'
        self.stopping = True
        return 'ok'

    def _on_StopAck(self, header, f):
        if not self.stopping or self.outstanding:
            return 'unexpected_state'
        if header['frame_id'] != 0:
            return 'bad_frame_id'
        if f['reserved'] != 0:
            return 'reserved_nonzero'
        if f['completed_frames'] != self.completed or f['discarded_frames'] != self.discarded:
            return 'bad_field'
        self.closed = True
        return 'ok'
