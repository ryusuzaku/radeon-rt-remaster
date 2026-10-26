"""Contract: the staleness policy reference model matches the Stage 0 table.

docs/RC_STALENESS_POLICY.md section 3 states the decision table and section 4
states the metrics. Stage 0 is only a declaration unless something checks it,
and the failure class the policy closes -- a forgotten revision letting a
stale composite through -- is exactly what a wrong row or a lost
lighting/settings split would re-open silently. This test pins:

  * the decision table row by row, including both branches of the camera row;
  * generation derivation: deterministic, independent of dict key order, and
    split so a lighting field never moves the settings generation and
    the other way round;
  * the packed tag: round-trips, the generation wrap and the age saturation;
  * the metric math on synthetic arrays, including a negative-control case
    where stale_fraction must be non-zero and a policy case where every gate
    gives zero;
  * the fail-closed property: decide() never returns continue across a
    scene, lighting, material or settings generation change.

It needs no built binary, no scene file and no provider DLL.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))

from rc_staleness import (
    ACTION_CONTINUE,
    ACTION_RESET,
    HARD_GENERATIONS,
    LIGHTING_FIELDS,
    ROW_REASONS,
    SETTINGS_FIELDS,
    age_violations,
    decide,
    generation_from_digest,
    generation_violations,
    lighting_generation,
    pack_tag,
    settings_generation,
    stale_fraction,
    stale_max_abs,
    stale_mse,
    unpack_tag,
)

# The light/render tuple the derivations read. One value per field of the split,
# in the shape the renderer's frame settings provide.
LIGHT_RENDER = {
    'sun_direction': (0.4, 0.5, 0.6),
    'sun_radius': 0.02,
    'light_colour': (1.0, 1.0, 1.0),
    'intensity': 3.0,
    'ambient': 0.15,
    'shadows': 1,
    'seed': 7,
    'denoise': True,
    'temporal': False,
    'render_scale': 1.0,
    'flags': 5,
}

# One replacement value per field, used to move exactly one generation at a
# time. The tuples replace a whole vector; the scalars replace a whole value.
FIELD_MUTATIONS = {
    'sun_direction': (0.4, 0.5, 0.7),
    'sun_radius': 0.03,
    'light_colour': (1.0, 0.9, 0.8),
    'intensity': 4.0,
    'ambient': 0.25,
    'shadows': 0,
    'seed': 8,
    'denoise': False,
    'temporal': True,
    'render_scale': 0.5,
    'flags': 6,
}


def identity(**overrides):
    """One five-revision identity derived from the reference tuple."""
    generations = {
        'scene': generation_from_digest(b'scene-bounds-v1'),
        'lighting': lighting_generation(LIGHT_RENDER),
        'material': generation_from_digest(b'material-set-v1'),
        'settings': settings_generation(LIGHT_RENDER),
        'camera': 3,
    }
    generations.update(overrides)
    return generations


def decision_table_row_by_row():
    camera_reason = ROW_REASONS['camera']
    # Rows 1-4: any of the generation-tagged changes is a hard reset, with the
    # row's own reason, whatever the ages and the bound are.
    for name in HARD_GENERATIONS:
        old = identity()
        new = identity(**{name: old[name] + 1})
        for entry_ages, max_age in (([0, 0], 0), ([0, 1, 2], 8), ([], 0)):
            result = decide(old, new, entry_ages, max_age=max_age)
            assert result.action == ACTION_RESET, (name, entry_ages, max_age, result)
            assert result.reason == ROW_REASONS[name], (name, result.reason)

    # Row 5: camera only. Reset by default; the optional continue exists only
    # when every composited entry has age <= max_age.
    old = identity()
    new = identity(camera=old['camera'] + 1)
    within = decide(old, new, [0, 0], max_age=0)
    assert within.action == ACTION_CONTINUE, within
    assert within.refused == [] and within.reason == camera_reason
    within = decide(old, new, [1, 2], max_age=2)
    assert within.action == ACTION_CONTINUE and within.refused == [], within
    defaulted = decide(old, new, [0, 1], max_age=0)
    assert defaulted.action == ACTION_RESET, defaulted
    assert defaulted.refused == [1] and defaulted.reason == camera_reason
    defaulted = decide(old, new, [1, 3], max_age=2)
    assert defaulted.action == ACTION_RESET and defaulted.refused == [1], defaulted
    # An entry over the bound is refused even when the camera is unchanged, and
    # the session still continues.
    same = identity()
    continued = decide(same, dict(same), [0, 1, 2], max_age=1)
    assert continued.action == ACTION_CONTINUE, continued
    assert continued.refused == [2] and continued.reason == ROW_REASONS['none']
    # Row 6: no change at all continues with nothing refused.
    clean = decide(same, dict(same), [0, 0], max_age=0)
    assert clean.action == ACTION_CONTINUE and clean.refused == [], clean
    assert clean.reason == ROW_REASONS['none']


def derivation_determinism_and_split():
    reordered = dict(reversed(list(LIGHT_RENDER.items())))
    assert lighting_generation(reordered) == lighting_generation(LIGHT_RENDER)
    assert settings_generation(reordered) == settings_generation(LIGHT_RENDER)
    # The two halves are distinct generations.
    assert lighting_generation(LIGHT_RENDER) != settings_generation(LIGHT_RENDER)
    # Split: a lighting field must not move the settings generation, and a
    # settings field must not move the lighting generation.
    for name in LIGHTING_FIELDS:
        moved = dict(LIGHT_RENDER)
        moved[name] = FIELD_MUTATIONS[name]
        assert lighting_generation(moved) != lighting_generation(LIGHT_RENDER), name
        assert settings_generation(moved) == settings_generation(LIGHT_RENDER), name
    for name in SETTINGS_FIELDS:
        moved = dict(LIGHT_RENDER)
        moved[name] = FIELD_MUTATIONS[name]
        assert settings_generation(moved) != settings_generation(LIGHT_RENDER), name
        assert lighting_generation(moved) == lighting_generation(LIGHT_RENDER), name
    # Scene and material generations come from caller-supplied digests and are
    # stable per digest.
    assert generation_from_digest(b'scene-bounds-v1') == generation_from_digest(b'scene-bounds-v1')
    assert generation_from_digest(b'scene-bounds-v1') != generation_from_digest(b'scene-bounds-v2')
    assert generation_from_digest(b'material-set-v1') != generation_from_digest(b'scene-bounds-v1')


def tag_round_trip_and_saturation():
    for generation, age in ((0, 0), (1, 2), (65535, 65535), (40000, 300), (9, 5)):
        assert unpack_tag(pack_tag(generation, age)) == (generation, age)
    # Layout: generation in the high half, age in the low half.
    tag = pack_tag(9, 5)
    assert tag >> 16 == 9 and tag & 0xFFFF == 5
    # The generation wraps modulo 2**16.
    assert unpack_tag(pack_tag(65536 + 7, 3)) == (7, 3)
    assert unpack_tag(pack_tag(-1, 3)) == (65535, 3)
    # The age saturates at 0xFFFF and at 0; it must never wrap to a value that
    # would look fresher than the entry is.
    assert unpack_tag(pack_tag(1, 65536)) == (1, 65535)
    assert unpack_tag(pack_tag(1, 10 ** 6)) == (1, 65535)
    assert unpack_tag(pack_tag(1, -4)) == (1, 0)
    # Every u32 round-trips through unpack then pack unchanged.
    for tag in (0, 1, 0xFFFF, 0x10000, 0x12345678, 0xFFFFFFFF):
        assert pack_tag(*unpack_tag(tag)) == tag


def metric_math():
    # N is the 516 mapped RGB values of the 128x96 fixture (172 queries x 3).
    n = 516
    c_old = [0.75] * n
    c_fresh = [0.5] * n
    # Policy gate: a reset composites exactly the fresh session, so every
    # stale metric is zero and stale_fraction must give zero.
    c_policy = list(c_fresh)
    assert stale_mse(c_policy, c_fresh) == 0.0
    assert stale_max_abs(c_policy, c_fresh) == 0.0
    assert stale_fraction(c_policy, c_fresh, c_old) == 0.0
    assert generation_violations([3] * n, 3) == 0
    assert age_violations([0] * n, 0) == 0
    # Negative control: a forced continue keeps the old composite, every value
    # is closer to C_old than to C_fresh, so stale_fraction must be non-zero.
    c_stale = list(c_old)
    assert stale_mse(c_stale, c_fresh) == 0.0625
    assert stale_max_abs(c_stale, c_fresh) == 0.25
    assert stale_fraction(c_stale, c_fresh, c_old) == 1.0
    # Partial staleness: half the values stayed on the old composite.
    c_mixed = [0.75] * (n // 2) + [0.5] * (n - n // 2)
    assert stale_fraction(c_mixed, c_fresh, c_old) == 0.5
    assert stale_max_abs(c_mixed, c_fresh) == 0.25
    # Half the values moved by 0.25, so the mean square is half of 0.0625.
    assert stale_mse(c_mixed, c_fresh) == 0.03125
    # The two violation counters count what the table says they count.
    assert generation_violations([3, 4, 3], 3) == 1
    assert generation_violations([4, 4], 3) == 2
    assert age_violations([0, 1, 2], 1) == 1
    # age_violations and decide()'s refused list are the same gate.
    result = decide(identity(), identity(), [0, 1, 2], max_age=1)
    assert result.refused == [2]
    assert age_violations([0, 1, 2], 1) == len(result.refused)
    # Mismatched lengths are refused rather than truncated.
    try:
        stale_mse([1.0, 2.0], [1.0])
    except ValueError:
        pass
    else:
        raise AssertionError('stale_mse accepted mismatched lengths')


def never_continue_across_a_generation_change():
    base = identity()
    for mask in range(1, 1 << len(HARD_GENERATIONS)):
        changed = [name for bit, name in enumerate(HARD_GENERATIONS) if mask >> bit & 1]
        for camera_moves in (False, True):
            for entry_ages, max_age in (([], 0), ([0, 0], 0), ([0, 1, 2], 8), ([5], 0)):
                old = dict(base)
                new = dict(base)
                for name in changed:
                    new[name] = base[name] + 1
                if camera_moves:
                    new['camera'] = base['camera'] + 1
                result = decide(old, new, entry_ages, max_age=max_age)
                assert result.action == ACTION_RESET, (changed, camera_moves, entry_ages, max_age)
                for name in changed:
                    assert ROW_REASONS[name] in result.reason, (name, result.reason)
    # A camera-only change is the table's one optional continue and is covered
    # by the row-by-row test above; anything else with a generation change
    # resets.


def main():
    decision_table_row_by_row()
    derivation_determinism_and_split()
    tag_round_trip_and_saturation()
    metric_math()
    never_continue_across_a_generation_change()
    print('PASS: staleness decision table, generation derivation split, tag packing '
          'and metric math match docs/RC_STALENESS_POLICY.md')
    return 0


if __name__ == '__main__':
    sys.exit(main())
