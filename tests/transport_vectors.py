"""Golden scenarios for the transport protocol, shared by the pure-Python contract and the C++ comparison.

Each scenario is a list of (direction, message bytes, expected error name) fed to a fresh session in order.
The expectations are written by hand from the rules in docs/schemas/transport-v1.json, not computed, so
a bug that both implementations share still fails here. `Script` only numbers messages: a step whose expected
outcome is 'ok' advances that direction's sequence, a rejected step does not, exactly as the session does.
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from transport_io import encode, P2R, R2P, MAGIC, FLAG_SUPERSEDE_PENDING, MAX_SCENE_BYTES  # noqa: E402

LUID = 0x1122334455667788
SCENE_GEN = 11
GEN = dict(scene_generation=SCENE_GEN, camera_generation=22, lighting_generation=33, material_generation=44, settings_generation=55)
DIGEST = {f'output_sha256_{i}': 5 + i for i in range(4)}
SCENE_DIGEST = {f'sha256_{i}': 1 + i for i in range(4)}


class Script:
    def __init__(self):
        self.steps = []
        self.seq = {P2R: 1, R2P: 1}

    def step(self, direction, build, expected, seq=None):
        self.steps.append((direction, build(self.seq[direction] if seq is None else seq), expected))
        if expected == 'ok':
            self.seq[direction] += 1
        return self

    def p(self, build, expected='ok', seq=None):
        return self.step(P2R, build, expected, seq)

    def r(self, build, expected='ok', seq=None):
        return self.step(R2P, build, expected, seq)

    def raw(self, direction, data, expected):
        self.steps.append((direction, data, expected))
        return self


def msg(name, values=None, frame_id=0, flags=0, version=1):
    return lambda seq: encode(name, values or {}, sequence=seq, frame_id=frame_id, flags=flags, version=version)


def hello(**over):
    values = dict(min_version=1, max_version=1, adapter_luid=LUID, process_id=4242, capabilities=0, capture_level=20)
    values.update(over)
    return msg('Hello', values)


def ack(version=1, frame_id=0, **over):
    values = dict(selected_version=1, status=0, adapter_luid=LUID, max_in_flight=2, capabilities=0)
    values.update(over)
    return msg('HelloAck', values, frame_id=frame_id, version=version)


def attach(frame_id=0, **over):
    values = dict(section_handle=0x1234, section_bytes=4096, scene_generation=SCENE_GEN, **SCENE_DIGEST)
    values.update(over)
    return msg('SceneAttach', values, frame_id=frame_id)


def attach_ack(**over):
    values = dict(status=0, scene_generation=SCENE_GEN, width=1280, height=720)
    values.update(over)
    return msg('SceneAttachAck', values)


def attach_fail(status, **over):
    return attach_ack(status=status, width=0, height=0, **over)


def submit(frame_id, flags=0, **over):
    values = dict(fence_value=100 + frame_id, resource_slot=frame_id % 8, width=1280, height=720, **GEN)
    values.update(over)
    return msg('FrameSubmit', values, frame_id=frame_id, flags=flags)


def complete(frame_id, status=0, **over):
    values = dict(fence_value=100 + frame_id, status=status, resource_slot=frame_id % 8, **GEN)
    if status == 0:
        values.update(DIGEST)
    values.update(over)
    return msg('FrameComplete', values, frame_id=frame_id)


def stop(frame_id=0):
    return msg('Stop', {}, frame_id=frame_id)


def stop_ack(completed, discarded, **over):
    values = dict(completed_frames=completed, discarded_frames=discarded)
    values.update(over)
    return msg('StopAck', values)


def opened():
    return Script().p(hello()).r(ack())


def attached():
    return opened().p(attach()).r(attach_ack())


def scenarios():
    s = {}
    good = hello()(1)
    s['happy_path'] = attached().p(submit(1)).p(submit(2)).r(complete(1)).r(complete(2)).p(stop()).r(stop_ack(2, 0)).steps
    s['short_header'] = Script().raw(P2R, good[:10], 'short_header').raw(P2R, b'', 'short_header').steps
    s['bad_magic'] = Script().raw(P2R, struct.pack('<I', MAGIC ^ 1) + good[4:], 'bad_magic').steps
    s['bad_version'] = Script().raw(P2R, good[:4] + struct.pack('<H', 2) + good[6:], 'bad_version').raw(P2R, good[:4] + struct.pack('<H', 0) + good[6:], 'bad_version').steps
    s['unknown_type'] = Script().raw(P2R, good[:6] + struct.pack('<H', 99) + good[8:], 'unknown_type').raw(P2R, good[:6] + struct.pack('<H', 0) + good[8:], 'unknown_type') \
        .raw(P2R, good[:6] + struct.pack('<H', 9) + good[8:], 'unknown_type').steps
    s['oversized'] = Script().raw(P2R, good + bytes(4096), 'oversized').steps
    s['payload_size'] = Script().raw(P2R, good[:8] + struct.pack('<I', 16) + good[12:], 'payload_size_mismatch').raw(P2R, good + b'\0', 'payload_size_mismatch') \
        .raw(P2R, good[:-1], 'payload_size_mismatch').raw(P2R, attach()(1)[:-8], 'payload_size_mismatch').raw(R2P, attach_ack()(1) + bytes(8), 'payload_size_mismatch').steps
    s['bad_flags'] = Script().raw(P2R, encode('Hello', dict(min_version=1, max_version=1), flags=1), 'bad_flags').raw(P2R, encode('Hello', dict(min_version=1, max_version=1), flags=0x80000000), 'bad_flags') \
        .raw(P2R, encode('SceneAttach', dict(section_handle=1, section_bytes=1), flags=1), 'bad_flags').steps
    s['wrong_direction'] = Script().r(hello(), 'wrong_direction').p(hello()).p(ack(), 'wrong_direction').r(attach(), 'wrong_direction').p(attach_ack(), 'wrong_direction') \
        .r(stop(), 'wrong_direction').steps
    s['sequence'] = Script().p(hello(), 'out_of_sequence', seq=2).p(hello(), 'out_of_sequence', seq=0).p(hello()).r(ack(), 'out_of_sequence', seq=2).r(ack()) \
        .p(attach(), 'out_of_sequence', seq=3).p(attach()).steps
    s['hello_fields'] = Script().p(msg('Hello', dict(min_version=1, max_version=1, reserved=1)), 'reserved_nonzero').p(hello(min_version=0), 'bad_field') \
        .p(hello(min_version=3, max_version=2), 'bad_field').p(msg('Hello', dict(min_version=1, max_version=1), frame_id=7), 'bad_frame_id').p(hello()).p(hello(), 'unexpected_state').steps
    s['order'] = Script().p(submit(1), 'unexpected_state').r(ack(), 'unexpected_state').p(attach(), 'unexpected_state').r(attach_ack(), 'unexpected_state').p(hello()) \
        .p(submit(1), 'unexpected_state').p(attach(), 'unexpected_state').r(ack()).r(ack(), 'unexpected_state').p(attach()).steps
    s['version_mismatch'] = Script().p(hello(min_version=2, max_version=3)).r(ack(), 'bad_field').r(ack(selected_version=0, status=1, max_in_flight=0)).p(attach(), 'unexpected_state').steps
    s['adapter_mismatch'] = Script().p(hello()).r(ack(adapter_luid=LUID + 1), 'bad_field').r(ack(selected_version=0, status=2, adapter_luid=LUID + 1, max_in_flight=0)).p(stop(), 'unexpected_state').steps
    s['ack_fields'] = Script().p(hello()).r(ack(selected_version=2), 'bad_field').r(ack(max_in_flight=3), 'bad_field').r(ack(status=9), 'bad_field').r(ack(version=2), 'bad_version') \
        .r(msg('HelloAck', dict(selected_version=1, status=0, adapter_luid=LUID, max_in_flight=2, reserved=5)), 'reserved_nonzero') \
        .r(msg('HelloAck', dict(selected_version=1, adapter_luid=LUID, max_in_flight=2), frame_id=1), 'bad_frame_id') \
        .r(ack(selected_version=0, status=1, max_in_flight=0), 'bad_field').r(ack()).steps
    s['busy'] = Script().p(hello()).r(ack(selected_version=0, status=3, max_in_flight=0)).p(attach(), 'unexpected_state').steps
    s['attach_rules'] = opened().r(attach_ack(), 'unexpected_state').p(attach(section_handle=0), 'bad_field').p(attach(section_bytes=0), 'bad_field') \
        .p(attach(section_bytes=MAX_SCENE_BYTES + 1), 'bad_field').p(msg('SceneAttach', dict(section_handle=1, section_bytes=1, reserved=1)), 'reserved_nonzero') \
        .p(attach(frame_id=3), 'bad_frame_id').p(submit(1), 'unexpected_state').p(attach(section_bytes=MAX_SCENE_BYTES)) \
        .p(attach(), 'unexpected_state').p(submit(1), 'unexpected_state').p(stop(), 'ok').r(stop_ack(0, 0), 'unexpected_state') \
        .r(attach_ack(scene_generation=12), 'generation_mismatch').r(attach_ack(status=9, width=0, height=0), 'bad_field').r(attach_ack(width=0), 'bad_field') \
        .r(attach_ack(height=16385), 'bad_field').r(attach_ack(status=1, width=5, height=0), 'bad_field').r(attach_fail(1)).r(stop_ack(0, 0)).steps
    s['attach_flow'] = opened().p(attach()).r(attach_fail(3)).p(submit(1), 'unexpected_state').p(attach(scene_generation=12)).r(attach_ack(scene_generation=12, width=640, height=480)) \
        .p(submit(1), 'generation_mismatch').p(submit(1, scene_generation=12)).p(attach(scene_generation=13), 'unexpected_state').r(complete(1, scene_generation=12)) \
        .p(attach(scene_generation=13)).r(attach_fail(2, scene_generation=13)).p(submit(2, scene_generation=12)).r(complete(2, scene_generation=12)) \
        .p(attach(scene_generation=14)).r(attach_ack(scene_generation=14)).p(submit(3, scene_generation=12), 'generation_mismatch').p(submit(3, scene_generation=14)) \
        .r(complete(3, scene_generation=14)).p(stop()).r(stop_ack(3, 0)).steps
    s['frame_fields'] = attached().p(submit(0), 'bad_frame_id').p(submit(1, width=0), 'bad_field').p(submit(1, height=16385), 'bad_field').p(submit(1, resource_slot=8), 'bad_field') \
        .p(submit(1, reserved=1), 'reserved_nonzero').p(msg('FrameSubmit', dict(width=1, height=1, scene_generation=SCENE_GEN), frame_id=1, flags=2), 'bad_flags') \
        .p(submit(1, scene_generation=SCENE_GEN + 1), 'generation_mismatch') \
        .p(submit(5)).p(submit(5), 'bad_frame_id').p(submit(4), 'bad_frame_id').p(submit(6, width=16384, height=16384, resource_slot=7)).steps
    s['in_flight'] = attached().p(submit(1)).p(submit(2)).p(submit(3), 'too_many_in_flight').p(submit(3, flags=FLAG_SUPERSEDE_PENDING)).r(complete(2), 'unknown_frame') \
        .r(complete(1)).r(complete(3)).p(submit(4, flags=FLAG_SUPERSEDE_PENDING)).p(stop()).r(complete(4)).r(stop_ack(3, 1)).steps
    s['complete_fields'] = attached().p(submit(1)).r(complete(1, fence_value=100), 'bad_field').r(complete(1, settings_generation=0), 'generation_mismatch') \
        .r(complete(1, resource_slot=7), 'generation_mismatch').r(complete(1, status=4), 'bad_field').r(complete(1, reserved32=1), 'reserved_nonzero') \
        .r(complete(1, status=2, output_sha256_0=1), 'bad_field').r(complete(9), 'unknown_frame').r(complete(1, fence_value=500, status=1)) \
        .p(stop()).r(stop_ack(0, 1)).p(submit(2), 'unexpected_state').steps
    s['stop_rules'] = attached().p(submit(1)).p(stop(frame_id=1), 'bad_frame_id').r(stop_ack(0, 0), 'unexpected_state').p(stop()).p(stop(), 'unexpected_state') \
        .p(submit(2), 'unexpected_state').p(attach(), 'unexpected_state').r(stop_ack(0, 0), 'unexpected_state').r(complete(1)) \
        .r(stop_ack(0, 0), 'bad_field').r(stop_ack(1, 0, reserved=1), 'reserved_nonzero').r(stop_ack(1, 0)).r(complete(2), 'unexpected_state').steps
    s['error_keeps_state'] = attached().p(submit(1, width=0), 'bad_field').p(submit(1)).p(submit(1), 'bad_frame_id').p(submit(2)).steps
    return s
