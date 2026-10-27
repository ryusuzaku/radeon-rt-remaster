"""Golden scenarios for the transport protocol, shared by the pure-Python contract and the C++ comparison.

Each scenario is a list of (direction, message bytes, expected error name) fed to a fresh session in order.
The expectations are written by hand from the rules in docs/schemas/transport-v1.json, not computed, so
a bug that both implementations share still fails here.
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from transport_io import encode, P2R, R2P, MAGIC, FLAG_SUPERSEDE_PENDING  # noqa: E402

LUID = 0x1122334455667788
GEN = dict(scene_generation=11, camera_generation=22, lighting_generation=33, material_generation=44, settings_generation=55)


def hello(sequence=1, **over):
    values = dict(min_version=1, max_version=1, adapter_luid=LUID, process_id=4242, capabilities=0, capture_level=20)
    values.update(over)
    return encode('Hello', values, sequence=sequence)


def ack(sequence=1, version=1, **over):
    values = dict(selected_version=1, status=0, adapter_luid=LUID, max_in_flight=2, capabilities=0)
    values.update(over)
    return encode('HelloAck', values, sequence=sequence, version=version)


def submit(sequence, frame_id, flags=0, **over):
    values = dict(fence_value=100 + frame_id, resource_slot=frame_id % 8, width=1280, height=720, **GEN)
    values.update(over)
    return encode('FrameSubmit', values, sequence=sequence, frame_id=frame_id, flags=flags)


def complete(sequence, frame_id, status=0, **over):
    values = dict(fence_value=100 + frame_id, status=status, resource_slot=frame_id % 8, **GEN)
    values.update(over)
    return encode('FrameComplete', values, sequence=sequence, frame_id=frame_id)


def stop(sequence=1, frame_id=0):
    return encode('Stop', {}, sequence=sequence, frame_id=frame_id)


def stop_ack(sequence, completed, discarded, **over):
    values = dict(completed_frames=completed, discarded_frames=discarded)
    values.update(over)
    return encode('StopAck', values, sequence=sequence)


def open_session():
    return [(P2R, hello(), 'ok'), (R2P, ack(), 'ok')]


def scenarios():
    s = {}
    s['happy_path'] = open_session() + [
        (P2R, submit(2, 1), 'ok'), (P2R, submit(3, 2), 'ok'), (R2P, complete(2, 1), 'ok'), (R2P, complete(3, 2), 'ok'),
        (P2R, stop(4), 'ok'), (R2P, stop_ack(4, 2, 0), 'ok')]
    good = hello()
    corrupt = bytearray(good)
    s['short_header'] = [(P2R, good[:10], 'short_header'), (P2R, b'', 'short_header')]
    s['bad_magic'] = [(P2R, hello()[:0] + struct.pack('<I', MAGIC ^ 1) + good[4:], 'bad_magic')]
    s['bad_version'] = [(P2R, good[:4] + struct.pack('<H', 2) + good[6:], 'bad_version'), (P2R, good[:4] + struct.pack('<H', 0) + good[6:], 'bad_version')]
    s['unknown_type'] = [(P2R, good[:6] + struct.pack('<H', 99) + good[8:], 'unknown_type'), (P2R, good[:6] + struct.pack('<H', 0) + good[8:], 'unknown_type')]
    s['oversized'] = [(P2R, good + bytes(4096), 'oversized')]
    s['payload_size'] = [(P2R, good[:8] + struct.pack('<I', 16) + good[12:], 'payload_size_mismatch'), (P2R, good + b'\0', 'payload_size_mismatch'), (P2R, good[:-1], 'payload_size_mismatch')]
    s['bad_flags'] = [(P2R, encode('Hello', dict(min_version=1, max_version=1), flags=1), 'bad_flags'), (P2R, encode('Hello', dict(min_version=1, max_version=1), flags=0x80000000), 'bad_flags')]
    s['wrong_direction'] = [(R2P, hello(), 'wrong_direction')] + open_session()[:1] + [(P2R, ack(), 'wrong_direction')]
    s['sequence'] = [(P2R, hello(sequence=2), 'out_of_sequence'), (P2R, hello(sequence=0), 'out_of_sequence'), (P2R, hello(), 'ok'), (R2P, ack(sequence=2), 'out_of_sequence'), (R2P, ack(), 'ok'),
                     (P2R, submit(3, 1), 'out_of_sequence'), (P2R, submit(2, 1), 'ok')]
    s['hello_fields'] = [(P2R, hello(reserved=1) if False else encode('Hello', dict(min_version=1, max_version=1, reserved=1)), 'reserved_nonzero'),
                         (P2R, hello(min_version=0), 'bad_field'), (P2R, hello(min_version=3, max_version=2), 'bad_field'),
                         (P2R, encode('Hello', dict(min_version=1, max_version=1), frame_id=7), 'bad_frame_id'), (P2R, hello(), 'ok'), (P2R, hello(sequence=2), 'unexpected_state')]
    s['order'] = [(P2R, submit(1, 1), 'unexpected_state'), (R2P, ack(), 'unexpected_state'), (P2R, hello(), 'ok'), (P2R, submit(2, 1), 'unexpected_state'),
                  (R2P, ack(), 'ok'), (R2P, ack(sequence=2), 'unexpected_state'), (P2R, submit(2, 1), 'ok')]
    s['version_mismatch'] = [(P2R, hello(min_version=2, max_version=3), 'ok'), (R2P, ack(), 'bad_field'),
                             (R2P, ack(selected_version=0, status=1, max_in_flight=0), 'ok'), (P2R, submit(2, 1), 'unexpected_state')]
    s['adapter_mismatch'] = [(P2R, hello(), 'ok'), (R2P, ack(adapter_luid=LUID + 1), 'bad_field'),
                             (R2P, ack(selected_version=0, status=2, adapter_luid=LUID + 1, max_in_flight=0), 'ok'), (P2R, stop(2), 'unexpected_state')]
    s['ack_fields'] = [(P2R, hello(), 'ok'), (R2P, ack(selected_version=2), 'bad_field'), (R2P, ack(max_in_flight=3), 'bad_field'), (R2P, ack(status=9), 'bad_field'),
                       (R2P, ack(version=2), 'bad_version'), (R2P, encode('HelloAck', dict(selected_version=1, status=0, adapter_luid=LUID, max_in_flight=2, reserved=5)), 'reserved_nonzero'),
                       (R2P, encode('HelloAck', dict(selected_version=1, adapter_luid=LUID, max_in_flight=2), frame_id=1), 'bad_frame_id'),
                       (R2P, ack(selected_version=0, status=1, max_in_flight=0), 'bad_field'), (R2P, ack(), 'ok')]
    s['busy'] = [(P2R, hello(), 'ok'), (R2P, ack(selected_version=0, status=3, max_in_flight=0), 'ok'), (P2R, submit(2, 1), 'unexpected_state')]
    s['frame_fields'] = open_session() + [
        (P2R, submit(2, 0), 'bad_frame_id'), (P2R, submit(2, 1, width=0), 'bad_field'), (P2R, submit(2, 1, height=16385), 'bad_field'),
        (P2R, submit(2, 1, resource_slot=8), 'bad_field'), (P2R, submit(2, 1, reserved=1), 'reserved_nonzero'), (P2R, submit(2, 1, flags=2) if False else encode('FrameSubmit', dict(width=1, height=1), sequence=2, frame_id=1, flags=2), 'bad_flags'),
        (P2R, submit(2, 5), 'ok'), (P2R, submit(3, 5), 'bad_frame_id'), (P2R, submit(3, 4), 'bad_frame_id'), (P2R, submit(3, 6, width=16384, height=16384, resource_slot=7), 'ok')]
    s['in_flight'] = open_session() + [
        (P2R, submit(2, 1), 'ok'), (P2R, submit(3, 2), 'ok'), (P2R, submit(4, 3), 'too_many_in_flight'),
        (P2R, submit(4, 3, flags=FLAG_SUPERSEDE_PENDING), 'ok'), (R2P, complete(2, 2), 'unknown_frame'), (R2P, complete(2, 1), 'ok'), (R2P, complete(3, 3), 'ok'),
        (P2R, submit(5, 4, flags=FLAG_SUPERSEDE_PENDING), 'ok'), (P2R, stop(6), 'ok'), (R2P, complete(4, 4), 'ok'), (R2P, stop_ack(5, 3, 1), 'ok')]
    s['complete_fields'] = open_session() + [
        (P2R, submit(2, 1), 'ok'), (R2P, complete(2, 1, fence_value=100), 'bad_field'), (R2P, complete(2, 1, settings_generation=0), 'generation_mismatch'),
        (R2P, complete(2, 1, resource_slot=7), 'generation_mismatch'), (R2P, complete(2, 1, status=4), 'bad_field'), (R2P, complete(2, 1, reserved32=1), 'reserved_nonzero'),
        (R2P, complete(2, 1, reserved=1), 'reserved_nonzero'), (R2P, complete(2, 9), 'unknown_frame'), (R2P, complete(2, 1, fence_value=500, status=1), 'ok'),
        (P2R, stop(3), 'ok'), (R2P, stop_ack(3, 0, 1), 'ok'), (P2R, submit(4, 2), 'unexpected_state')]
    s['stop_rules'] = open_session() + [
        (P2R, submit(2, 1), 'ok'), (P2R, stop(3, frame_id=1), 'bad_frame_id'), (R2P, stop_ack(2, 0, 0), 'unexpected_state'), (P2R, stop(3), 'ok'),
        (P2R, stop(4), 'unexpected_state'), (P2R, submit(4, 2), 'unexpected_state'), (R2P, stop_ack(2, 0, 0), 'unexpected_state'),
        (R2P, complete(2, 1), 'ok'), (R2P, stop_ack(3, 0, 0), 'bad_field'), (R2P, stop_ack(3, 1, 0, reserved=1), 'reserved_nonzero'), (R2P, stop_ack(3, 1, 0), 'ok'),
        (R2P, complete(4, 1), 'unexpected_state')]
    s['error_keeps_state'] = open_session() + [(P2R, submit(2, 1, width=0), 'bad_field'), (P2R, submit(2, 1), 'ok'), (P2R, submit(3, 1), 'bad_frame_id'), (P2R, submit(3, 2), 'ok')]
    return s
