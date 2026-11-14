"""Pure-Python checks of tools/vs_interpreter.py, the reader's independent vs_2_0 position interpreter. No GPU, no game content.

Synthetic programs are assembled token by token, as the fixture's GPU oracle does:
  * the slice keeps exactly the instructions that reach oPos, through partial write masks, swizzles and a0;
  * evaluation follows the instruction semantics (mova rounding of negative and fractional values, negate, min, max, abs, dp3,
    dp4, mad, relative reads) and reports the relative reads;
  * the float32 allowance accepts a cancelling row and refuses a shifted result;
  * refusals: other shader models, sub, _abs, saturate, subroutines, a slice inside flow control, an uninitialised temporary or
    address, an undeclared input, an unknown constant, and a mova too close to a rounding boundary to decide.
"""
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import vs_interpreter as vi  # noqa: E402

TEMP, IN, CONST, ADDR, RASTOUT, TEXOUT = 0, 1, 2, 3, 4, 6
dst = lambda t, r, m=15, sat=False: 0x80000000 | ((t & 7) << 28) | (m << 16) | (1 << 20 if sat else 0) | r
src = lambda t, r, s=0xE4, mod=0, rel=False: 0x80000000 | ((t & 7) << 28) | (s << 16) | (mod << 24) | (1 << 13 if rel else 0) | r
addr = lambda c: 0x80000000 | (ADDR << 28) | (c * 0x55 << 16)
op = lambda o, n: o | (n << 24)
swz = lambda x, y, z, w: x | (y << 2) | (z << 4) | (w << 6)
dcl = lambda reg, usage, index=0: [op(31, 2), 0x80000000 | usage | (index << 16), dst(IN, reg)]


def program(body, extra=()):
    return [0xfffe0200] + dcl(0, 0) + dcl(1, 5) + list(extra) + body + [0xffff]


def refuses(tokens, reason):
    try:
        vi.analyse(tokens)
    except vi.Refused as error:
        assert str(error) == reason, (reason, str(error)); return
    raise AssertionError(f'expected refusal {reason}')


def exact(v): return (list(v), [0.0] * 4)


def main():
    # Slice: r5 and the oT0 write are not on the position path; r1.zw is written in two halves.
    tokens = program([op(1, 2), dst(TEMP, 0), src(IN, 0, swz(0, 1, 2, 0)),                        # mov r0, v0.xyzx
                      op(2, 3), dst(TEMP, 0), src(TEMP, 0), src(CONST, 1, 0xE4, 1),               # add r0, r0, -c1
                      op(1, 2), dst(TEMP, 5), src(IN, 1),                                          # mov r5, v1        (unused)
                      op(1, 2), dst(TEXOUT, 0), src(TEMP, 5),                                      # mov oT0, r5       (not position)
                      op(1, 2), dst(TEMP, 4), src(IN, 1),                                          # mov r4, v1
                      op(10, 3), dst(TEMP, 1, 3), src(TEMP, 0, swz(2, 0, 1, 3)), src(TEMP, 4, swz(3, 2, 1, 0)),
                      op(11, 3), dst(TEMP, 1, 12), src(TEMP, 0, 0xE4, 1), src(CONST, 2, swz(1, 1, 0, 0)),
                      op(35, 2), dst(TEMP, 2), src(IN, 1, 0xE4, 1),                                # abs r2, -v1
                      op(8, 3), dst(TEMP, 3, 1), src(TEMP, 1), src(TEMP, 2, swz(3, 1, 0, 2)),      # dp3 r3.x, r1, r2.wyxz
                      op(4, 4), dst(TEMP, 3, 14), src(TEMP, 1, swz(1, 2, 3, 0)), src(CONST, 3, swz(3, 3, 3, 3), 1), src(TEMP, 2),
                      op(1, 2), dst(RASTOUT, 0), src(TEMP, 3)])
    p = vi.analyse(tokens)
    assert sum(i['slice'] for i in p['code']) == 9 and [i['op'] for i in p['code'] if not i['slice']] == [1, 1], 'slice'
    assert [(i['reg'], i['usage']) for i in p['inputs']] == [(0, 0), (1, 5)] and p['constants'] == {1, 2, 3}
    v0, v1 = [3.0, -1.5, 0.25, 1.0], [0.5, -2.0, 1.25, -0.75]
    c = {1: (0.5, 1.0, -1.0, 2.0), 2: (-0.25, 0.75, 9.0, 9.0), 3: (9.0, 9.0, 9.0, 1.5)}
    clip, magnitude, reads = vi.evaluate(p, {0: exact(v0), 1: exact(v1)}, c.get)
    r0 = [v0[0] - 0.5, v0[1] - 1.0, v0[2] + 1.0, v0[0] - 2.0]           # v0.xyzx - c1
    r1 = [min(r0[2], v1[3]), min(r0[0], v1[2]), max(-r0[2], -0.25), max(-r0[3], -0.25)]  # c2.yyxx: z and w take c2.x
    r2 = [abs(-x) for x in v1]
    expected = [r1[0] * r2[3] + r1[1] * r2[1] + r1[2] * r2[0]] + [r1[(k + 1) % 4] * -1.5 + r2[k] for k in (1, 2, 3)]
    assert all(abs(a - b) < 1e-12 for a, b in zip(clip, expected)), (clip, expected)
    assert reads == [] and vi.matches(clip, clip, magnitude) and not vi.matches([clip[0] + 1e-3] + clip[1:], clip, magnitude)

    # mova rounds to nearest, negative and fractional values included; relative reads are reported.
    mova = program([op(46, 2), dst(ADDR, 0, 3), src(IN, 1),
                    op(1, 3), dst(TEMP, 1), src(CONST, 100, 0xE4, 0, True), addr(0),
                    op(2, 4), dst(TEMP, 0), src(TEMP, 1), src(CONST, 150, 0xE4, 0, True), addr(1),
                    op(1, 2), dst(RASTOUT, 0), src(TEMP, 0)])
    p = vi.analyse(mova); assert p['relative'] == [150, 100], p['relative']
    table = {r: (float(r), 0.0, 0.0, 1.0) for r in range(256)}
    for x, y in ((2.7, -0.6), (0.2, 3.49), (-0.3, 10.51)):
        clip, _, reads = vi.evaluate(p, {0: exact([0, 0, 0, 1]), 1: exact([x, y, 0, 1])}, table.get)
        ax, ay = int(vi.math.floor(x + 0.5)), int(vi.math.floor(y + 0.5))
        assert reads == [100 + ax, 150 + ay] and clip[0] == 100 + ax + 150 + ay, (x, y, reads, clip)
    try:
        vi.evaluate(p, {0: exact([0, 0, 0, 1]), 1: ([2.5, 0, 0, 1], [1.0, 0, 0, 0])}, table.get); raise AssertionError('ambiguous mova accepted')
    except vi.Refused as error: assert str(error) == 'ambiguous_address'
    try:
        vi.evaluate(p, {0: exact([0, 0, 0, 1]), 1: exact([1, 1, 0, 1])}, lambda r: None if r == 101 else table.get(r)); raise AssertionError('unknown constant accepted')
    except vi.Refused as error: assert str(error) == 'unknown position constant'

    # Cancellation: a map-sized position against a near-plane row is accepted with its float32 allowance, a shifted one is not.
    dot = program([op(9, 3), dst(TEMP, 0), src(IN, 0), src(CONST, 4), op(1, 2), dst(RASTOUT, 0), src(TEMP, 0)])
    p = vi.analyse(dot); row = (0.86, 0.5, 0.01, 5420.0)
    position = [-5731.37, -748.61, 251.93, 1.0]
    f32 = lambda x: struct.unpack('<f', struct.pack('<f', x))[0]
    total = 0.0
    for k in range(4): total = f32(total + f32(f32(position[k]) * f32(row[k])))
    clip, magnitude, _ = vi.evaluate(p, {0: exact([f32(x) for x in position])}, {4: tuple(f32(x) for x in row)}.get)
    assert vi.matches([total] * 4, clip, magnitude) and not vi.matches([total + 0.05] * 4, clip, magnitude)

    # Input conversion follows the declaration types.
    assert vi.convert(4, bytes([10, 20, 30, 40]))[0] == [30 / 255, 20 / 255, 10 / 255, 40 / 255]
    assert vi.convert(6, struct.pack('<2h', -3, 7))[0] == [-3.0, 7.0, 0.0, 1.0]
    assert vi.convert(2, struct.pack('<3f', 1, 2, 3))[0] == [1.0, 2.0, 3.0, 1.0]

    # Refusals.
    simple = [op(1, 2), dst(RASTOUT, 0), src(IN, 0)]
    refuses([0xfffe0300] + simple + [0xffff], 'unsupported_shader_model')
    refuses(program([op(3, 3), dst(TEMP, 0), src(IN, 0), src(CONST, 1), op(1, 2), dst(RASTOUT, 0), src(TEMP, 0)]), 'unsupported_slice_opcode')
    refuses(program([op(1, 2), dst(TEMP, 0), src(IN, 0, 0xE4, 11), op(1, 2), dst(RASTOUT, 0), src(TEMP, 0)]), 'unsupported_source_modifier')
    refuses(program([op(1, 2), dst(TEMP, 0, 15, True), src(IN, 0), op(1, 2), dst(RASTOUT, 0), src(TEMP, 0)]), 'unsupported_result_modifier')
    refuses(program([op(25, 1), 0x80000000] + simple), 'subroutines')
    refuses(program([op(40, 1), src(14, 0), op(1, 2), dst(TEMP, 0), src(IN, 0), op(43, 0), op(1, 2), dst(RASTOUT, 0), src(TEMP, 0)]), 'position_in_flow_control')
    refuses(program([op(1, 2), dst(TEMP, 0, 3), src(IN, 0), op(1, 2), dst(RASTOUT, 0), src(TEMP, 0)]), 'uninitialised_temporary')
    refuses(program([op(1, 3), dst(TEMP, 0), src(CONST, 10, 0xE4, 0, True), addr(0), op(1, 2), dst(RASTOUT, 0), src(TEMP, 0)]), 'uninitialised_address')
    refuses(program([op(1, 2), dst(RASTOUT, 0), src(IN, 7)]), 'undeclared_input')
    refuses(program([op(1, 2), dst(TEXOUT, 0), src(IN, 0)]), 'no_position_output')
    # Not refused: flow control away from the slice, and a slice write that a later write outside the block replaces.
    vi.analyse(program([op(40, 1), src(14, 0), op(1, 2), dst(TEMP, 0), src(IN, 1), op(43, 0), op(1, 2), dst(TEMP, 0), src(IN, 0), op(1, 2), dst(RASTOUT, 0), src(TEMP, 0)]))
    print('PASS vs_interpreter: slice, evaluation, mova rounding and relative reads, float32 allowance, input conversion and 11 refusals')


if __name__ == '__main__':
    main()
