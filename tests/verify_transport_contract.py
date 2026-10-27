"""Contract: the transport schema, the C++ header and the Python codec describe one protocol.

docs/schemas/transport-v1.json is the machine-readable definition, src/transport/transport.h the C++
implementation (built into both the x86 proxy and the x64 renderer) and tools/transport_io.py the Python
reference. This test needs no binary, no GPU and no game content:

  * the schema is internally consistent (contiguous naturally aligned fields, sizes, unique types);
  * the C++ header's sizeof/offsetof static_asserts and constants equal the schema;
  * the C++ error enum lists the schema's errors in the same order;
  * the Python codec round-trips every message and reproduces each golden scenario's hand-written outcome.

Behaviour of the compiled C++ monitor against the same scenarios is checked by tests/verify_transport_layout.py
(the transport_layout ctest), which needs the built check program.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'tests'))
import transport_io as t  # noqa: E402
from transport_vectors import scenarios  # noqa: E402

schema = json.loads((ROOT / 'docs' / 'schemas' / 'transport-v1.json').read_text(encoding='utf-8'))
header_source = (ROOT / 'src' / 'transport' / 'transport.h').read_text(encoding='utf-8')
SIZES = {'u16': 2, 'u32': 4, 'u64': 8}


def need(condition, message):
    if not condition: raise AssertionError(message)


def product(expression):
    result = 1
    for factor in expression.split('*'):
        result *= int(factor.strip().rstrip('ul'))
    return result


def snake(name):
    return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()


def check_layout(fields, size, label):
    cursor = 0
    for field in fields:
        width = SIZES[field['type']]
        need(field['offset'] == cursor, f'{label}.{field["name"]}: offset {field["offset"]} leaves a gap or overlap (expected {cursor})')
        need(field['offset'] % width == 0, f'{label}.{field["name"]}: not naturally aligned')
        cursor += width
    need(cursor == size, f'{label}: fields end at {cursor}, declared size {size}')
    need(size % 8 == 0, f'{label}: size {size} is not a multiple of 8')


# --- the schema on its own -----------------------------------------------------
need(schema['schema'] == 'rrt-transport' and schema['version'] == 1 and schema['endianness'] == 'little', 'schema identity')
need(schema['magic'] == int.from_bytes(schema['magic_ascii'].encode('ascii'), 'little'), 'magic does not spell magic_ascii')
need(schema['supported_versions'] == [1], 'supported_versions changed without updating this contract')
check_layout(schema['header']['fields'], schema['header']['size'], 'Header')
types = [m['type'] for m in schema['messages']]
need(len(set(types)) == len(types) and sorted(types) == list(range(1, len(types) + 1)), 'message types must be 1..N and unique')
need(len({m['name'] for m in schema['messages']}) == len(types), 'duplicate message names')
for m in schema['messages']:
    check_layout(m['fields'], m['payload_size'], m['name'])
    need(m['direction'] in ('proxy->renderer', 'renderer->proxy'), f'{m["name"]}: bad direction')
    need(schema['header']['size'] + m['payload_size'] <= schema['max_message_bytes'], f'{m["name"]}: exceeds max_message_bytes')
need(len(schema['errors']) == len(set(schema['errors'])) and schema['errors'][0] == 'ok', 'errors must be unique and start with ok')

# --- the C++ header --------------------------------------------------------------
sizeof = {name: int(value) for name, value in re.findall(r'sizeof\((\w+)\)\s*==\s*(\d+)', header_source)}
offsets = {}
for struct_name, member, value in re.findall(r'offsetof\((\w+),\s*(\w+)\)\s*==\s*(\d+)', header_source):
    offsets.setdefault(struct_name, {})[snake(member)] = int(value)
need(sizeof.get('Header') == schema['header']['size'], 'C++ Header size differs from the schema')
need({f['name']: f['offset'] for f in schema['header']['fields']} == offsets['Header'], 'C++ Header offsets differ from the schema')
gens = {'scene': 0, 'camera': 4, 'lighting': 8, 'material': 12, 'settings': 16}
need(offsets['Generations'] == gens and sizeof['Generations'] == 20, 'C++ Generations layout changed')
for m in schema['messages']:
    if not m['payload_size']:
        continue
    need(sizeof.get(m['name']) == m['payload_size'], f'C++ {m["name"]} size differs from the schema')
    cpp = dict(offsets[m['name']])
    for array in ('sha256', 'output_sha256'):  # a digest is an array of four u64 words in C++
        if array in cpp:
            base = cpp.pop(array)
            for i in range(4): cpp[f'{array}_{i}'] = base + 8 * i
    if 'generations' in cpp:  # the five generation fields are one nested struct
        base = cpp.pop('generations')
        for g, delta in gens.items(): cpp[f'{g}_generation'] = base + delta
    want = {f['name']: f['offset'] for f in m['fields']}
    need(cpp == want, f'C++ {m["name"]} offsets differ from the schema: {cpp} != {want}')
constants = {
    'Magic': int(re.search(r'Magic\s*=\s*(0x[0-9A-Fa-f]+)u', header_source).group(1), 16),
    'MaxMessageBytes': int(re.search(r'MaxMessageBytes\s*=\s*(\d+)', header_source).group(1)),
    'MaxInFlight': int(re.search(r'MaxInFlight\s*=\s*(\d+)', header_source).group(1)),
    'MaxDimension': int(re.search(r'MaxDimension\s*=\s*(\d+)', header_source).group(1)),
    'MaxSlots': int(re.search(r'MaxSlots\s*=\s*(\d+)', header_source).group(1)),
    'MaxSceneBytes': product(re.search(r'MaxSceneBytes\s*=\s*([0-9ul\s*]+);', header_source).group(1)),
    'SupportedVersion': int(re.search(r'SupportedVersion\s*=\s*(\d+)', header_source).group(1)),
}
scene_h = (ROOT / 'src' / 'scene' / 'scene.h').read_text(encoding='utf-8')
need(constants['MaxSceneBytes'] == schema['max_scene_bytes'] == product(re.search(r'MaxBytes\s*=\s*([0-9*]+)', scene_h).group(1)), 'max scene bytes differ between the transport and the scene format')
need(constants['Magic'] == schema['magic'] and constants['MaxMessageBytes'] == schema['max_message_bytes'] and constants['MaxInFlight'] == schema['max_in_flight'], 'C++ constants differ from the schema')
need(constants['MaxDimension'] == t.MAX_DIMENSION and constants['MaxSlots'] == t.MAX_SLOTS and [constants['SupportedVersion']] == schema['supported_versions'], 'C++ limits differ from the Python codec')
need(re.search(r'FlagSupersedePending\s*=\s*1u\s*<<\s*0', header_source) and t.FLAG_SUPERSEDE_PENDING == 1, 'supersede flag bit differs')
enum_body = re.search(r'enum class Error : std::uint8_t \{(.*?)\};', header_source, re.S).group(1)
cpp_errors = [snake(name.strip()) for name in enum_body.replace('\n', ' ').split(',') if name.strip()]
need(cpp_errors == schema['errors'], f'C++ Error enum differs from the schema errors: {cpp_errors}')
for name, value in schema['hello_ack_status'].items():
    need(re.search(r'Ack%s\s*=\s*%d' % (''.join(p.title() for p in name.split('_')), value), header_source), f'C++ HelloAckStatus {name}')
for name, value in schema['scene_attach_status'].items():
    need(re.search(r'Scene%s\s*=\s*%d' % (''.join(p.title() for p in name.split('_')), value), header_source), f'C++ SceneAttachStatus {name}')
for name, value in schema['frame_complete_status'].items():
    need(re.search(r'Frame%s\s*=\s*%d' % (''.join(p.title() for p in name.split('_')), value), header_source), f'C++ FrameCompleteStatus {name}')
for m in schema['messages']:
    need(re.search(r'%s = %d' % (m['name'], m['type']), header_source), f'C++ Type {m["name"]} value')

# --- the Python codec ----------------------------------------------------------
for m in schema['messages']:
    values = {f['name']: (1 if not f['name'].startswith('reserved') else 0) for f in m['fields']}
    data = t.encode(m['name'], values, sequence=7, frame_id=3)
    need(len(data) == schema['header']['size'] + m['payload_size'], f'{m["name"]}: encoded length')
    header, name, fields = t.parse(data)
    need(name == m['name'] and fields == values and header['sequence'] == 7 and header['frame_id'] == 3, f'{m["name"]}: round trip')
need(t.negotiate(1, 1) == 1 and t.negotiate(1, 5) == 1 and t.negotiate(2, 5) == 0 and t.negotiate(0, 0) == 0, 'negotiation')

# --- the golden scenarios -----------------------------------------------------
total = 0
for name, steps in scenarios().items():
    session = t.Session()
    for index, (direction, data, expected) in enumerate(steps):
        got = session.feed(direction, data)
        need(got == expected, f'scenario {name} step {index}: expected {expected}, got {got}')
        need(got in t.ERRORS, f'scenario {name} step {index}: unknown error {got}')
        total += 1
covered = {expected for steps in scenarios().values() for _, _, expected in steps}
need(covered == set(t.ERRORS), f'scenarios never produce: {sorted(set(t.ERRORS) - covered)}')
print(f'PASS transport schema, C++ header and Python codec agree; {total} golden steps in {len(scenarios())} scenarios cover all {len(t.ERRORS)} outcomes')
