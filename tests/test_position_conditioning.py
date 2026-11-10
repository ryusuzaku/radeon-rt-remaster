"""Contract: the position reader's calculation check tolerates float32 cancellation and nothing else.

The proxy evaluates the admitted vertex program in float32; the reader recomputes it in double precision. A map-sized
position against a row whose products cancel leaves a small result carrying rounding of the size of the products, which
a tolerance relative to the result alone refuses. A real HL2 frame capture hit exactly that (one draw per frame, clip z
0.0933 from products near 4,945). The synthetic cases below reproduce the shape without any captured data:

  * a float32 evaluation of a cancelling row is accepted, in every summation order;
  * the same result is refused by the old result-relative rule, so the case is a real regression guard;
  * a wrong constant, a wrong position or an error a few rounding units larger is still refused;
  * well-conditioned values keep the 2e-4 relative behaviour.
"""
from itertools import permutations
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from inspect_position_capture import F32_ROUNDING, position_matches


def f32(value):
    return struct.unpack('<f', struct.pack('<f', value))[0]


def evaluate_f32(constants, position, order=(0, 1, 2, 3)):
    """The program in float32: q = position * c0.y + c0.x, then one dot product per row, summed in `order`."""
    a, b = constants[:2]
    q = [f32(f32(position[0] * b) + a), f32(f32(position[1] * b) + a), f32(f32(position[2] * b) + a), f32(f32(position[0] * a) + b)]
    out = []
    for row in range(1, 8):
        total = 0.0
        for j in order: total = f32(total + f32(q[j] * constants[row * 4 + j]))
        out.append(total)
    return out + [1.0]


def old_rule(constants, position, result):
    a, b = constants[:2]; q = [position[0] * b + a, position[1] * b + a, position[2] * b + a, position[0] * a + b]
    calculated = [sum(q[j] * constants[i * 4 + j] for j in range(4)) for i in range(1, 8)] + [1.0]
    return all(abs(x - y) / (1 + abs(y)) <= 2e-4 for x, y in zip(result, calculated))


def constants_with(clip_z):
    rows = [[0.0, 1.0, 0.0, 0.0],                      # c0: the affine (0, 1) preparation
            [0.9, 0.1, 0.0, 30.0], [0.0, 0.2, 1.7, -90.0], clip_z, [0.8, -0.5, 0.3, 4000.0],   # c4..c7 clip rows
            [1.0, 0.0, 0.0, 12.0], [0.0, 1.0, 0.0, -7.0], [0.0, 0.0, 1.0, 3.0]]                # c58..c60 model rows
    return [f32(x) for row in rows for x in row]


def main():
    position = (f32(-5731.37), f32(-748.61), f32(251.93))
    # A clip z row whose products are thousands and whose sum is a fraction: 0.86 * x + 0.5 * y + 0.01 * z + w.
    target = 0.1
    w = -(0.86 * position[0] + 0.5 * position[1] + 0.01 * position[2]) + target
    cancelling = constants_with([0.86, 0.5, 0.01, w])

    refused_by_old = 0
    for order in permutations(range(4)):
        result = evaluate_f32(cancelling, position, order)
        assert abs(result[2]) < 1.0, result[2]                         # the result really is small against ~4,900 products
        assert position_matches(cancelling, position, result), (order, result[2])
        refused_by_old += not old_rule(cancelling, position, result)
    assert refused_by_old, 'the cancelling case must be one the result-relative rule refuses, or it guards nothing'

    result = evaluate_f32(cancelling, position)
    magnitude = sum(abs(position[j] * cancelling[12 + j]) for j in range(3)) + abs(cancelling[15])
    for factor in (4.0, -4.0):  # a few rounding units beyond the allowance, far below a plausible defect
        wrong = list(result); wrong[2] += factor * (F32_ROUNDING * magnitude + 2e-4 * 1.2)
        assert not position_matches(cancelling, position, wrong), factor
    for index in (12, 13, 15, 4, 20):  # a constant off by one part in a thousand
        mutated = list(cancelling); mutated[index] = f32(mutated[index] * 1.001)
        assert not position_matches(mutated, position, result), index
    assert not position_matches(cancelling, (position[0] + 1.0, position[1], position[2]), result)
    assert not position_matches(cancelling, position, result[:7] + [0.999])

    # Well-conditioned: the relative 2e-4 still decides, and the added allowance is negligible beside it.
    plain = constants_with([0.0, 0.0, 1.0, 5.0]); near = (1.5, -2.25, 3.0)
    result = evaluate_f32(plain, near)
    assert position_matches(plain, near, result) and old_rule(plain, near, result)
    inside = list(result); inside[2] *= 1 + 1.5e-4
    outside = list(result); outside[2] *= 1 + 3e-4
    assert position_matches(plain, near, inside) and not position_matches(plain, near, outside)

    print('position conditioning: PASS')


if __name__ == '__main__':
    main()
