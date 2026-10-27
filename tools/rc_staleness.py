"""Pure-Python reference model of the Radiance Cache staleness policy.

This is Stage 0 of docs/RC_STALENESS_POLICY.md: the policy expressed as code
that needs no device, no provider DLL and no built binary. The renderer wiring
comes later; nothing here changes a byte of existing behaviour. Four pieces:

1. The generation model. The admission identity carries five revisions -- scene,
   lighting, material, settings and camera. The lighting and settings
   generations are derived from the light/render tuple that already feeds the
   RCRPATH1 settings digest (src/dxr/rc_paths.h:66-69), split so that lighting
   (sun direction, sun radius, light colour, intensity, ambient, shadows) and
   settings (seed, denoise, temporal, render scale, flags) are distinct
   generations: changing one must not move the other. Derivation is
   deterministic and independent of the mapping's key order, because the
   failure class this closes is a forgotten manual bump and a derived value is
   only a fix if it is reproducible. Scene and material generations come from
   caller-supplied digests; camera is a caller-issued revision.

2. The section 3 decision table as `decide()`: the action (`reset` or
   `continue`), the refused entries and the reason. A scene, lighting, material
   or settings generation change is always a hard reset. A camera-only change
   always resets unless camera continuation is opted in, and then continues
   only when every composited entry has
   `age <= max_age`. An unchanged identity continues, and an entry that was not
   refreshed in the current epoch (age above `max_age`) is refused either way.

3. The packed generation+age tag: one u32, the generation in bits 31..16 and
   the age in bits 15..0. The generation wraps modulo 2**16; the age saturates
   at 0xFFFF and at 0. The age must never wrap to a smaller value -- a wrapped
   age would look fresh and pass the `max_age` gate, which is the exact
   fail-open this policy exists to prevent.

4. The section 4 metric math over plain lists: `stale_mse`, `stale_max_abs`,
   `stale_fraction`, `generation_violations` and `age_violations`, the
   definitions the stale-lighting scenario gates on.

Standard library only.
"""
import hashlib
import struct
from typing import NamedTuple

# The five caller-visible revisions of RcFrameAdmission::Identity.
GENERATIONS = ('scene', 'lighting', 'material', 'settings', 'camera')
# The generation-tagged rows of the decision table. A camera change is the one
# row that may continue, so it is not part of this set.
HARD_GENERATIONS = ('scene', 'lighting', 'material', 'settings')

# The light/render tuple split. Lighting fields describe the one global sun;
# settings fields describe how the paths are realized and accumulated. The two
# sets are disjoint so the derived generations are independent.
LIGHTING_FIELDS = ('sun_direction', 'sun_radius', 'light_colour', 'intensity', 'ambient', 'shadows')
SETTINGS_FIELDS = ('seed', 'denoise', 'temporal', 'render_scale', 'flags')

ACTION_RESET = 'reset'
ACTION_CONTINUE = 'continue'

# The Reason column of the section 3 decision table, keyed by the governing
# generation. When more than one hard generation changed, the reasons are
# joined in table order.
ROW_REASONS = {
    'scene': 'Normalized positions denote different world points',
    'lighting': 'Every indirect target changes; one global sun',
    'material': 'No valid subset today; RC paths reject sidecars',
    'settings': 'Path realization or accumulation changes',
    'camera': 'Positions are camera-independent; targets are view-dependent and unmeasured',
    'none': 'Existing behaviour',
}

# Material generation input when no sidecar is present: the RC path export rejects
# sidecars, so the digest input is this fixed tag. src/dxr/rc_generation.h uses
# the same bytes.
MATERIAL_NONE_TAG = b'rrt-rc-material:none'

GENERATION_BITS = 16
AGE_BITS = 16
GENERATION_WRAP = 1 << GENERATION_BITS
AGE_MAX = (1 << AGE_BITS) - 1
TAG_MASK = 0xFFFFFFFF


def _canonical_bytes(value):
    """One deterministic byte form for a generation input value.

    bool is checked before int because it is an int subclass; floats are packed
    as little-endian IEEE-754 doubles so the encoding is exact and stable.
    """
    if isinstance(value, bool):
        return b'b1' if value else b'b0'
    if isinstance(value, int):
        return b'i' + str(value).encode('ascii') + b';'
    if isinstance(value, float):
        return b'f' + struct.pack('<d', value)
    if isinstance(value, (list, tuple)):
        return (b'v' + str(len(value)).encode('ascii') + b':'
                + b''.join(_canonical_bytes(item) for item in value))
    raise TypeError(f'unsupported generation input: {value!r}')


def _derive(fields, source):
    """Reduce the named fields of a mapping to a u32 generation.

    The fields are read in the order of `fields`, never in the mapping's key
    order, so two mappings with the same values in different insertion orders
    derive the same generation.
    """
    payload = bytearray()
    for name in fields:
        payload += name.encode('ascii') + b'\0' + _canonical_bytes(source[name]) + b'\0'
    return int.from_bytes(hashlib.sha256(payload).digest()[:4], 'big')


def lighting_generation(light_render):
    """Derive the lighting generation from the light/render tuple.

    Reads sun direction, sun radius, light colour, intensity, ambient and
    shadows. Nothing else moves this generation.
    """
    return _derive(LIGHTING_FIELDS, light_render)


def settings_generation(light_render):
    """Derive the settings generation from the light/render tuple.

    Reads seed, denoise, temporal, render scale and flags. Nothing else moves
    this generation.
    """
    return _derive(SETTINGS_FIELDS, light_render)


def generation_from_digest(digest):
    """Reduce a caller-supplied digest to a u32 generation.

    Scene and material generations are not derived from a settings tuple: the
    caller owns those digests (the scene digest and the material set or sidecar
    digest) and this maps one to a generation. Accepts raw bytes or an ASCII
    hex form; pick one convention per caller and keep it.
    """
    if isinstance(digest, str):
        digest = digest.encode('ascii')
    return int.from_bytes(hashlib.sha256(bytes(digest)).digest()[:4], 'big')


def pack_tag(generation, age):
    """Pack a generation and an age into one u32 tag.

    Bits 31..16 hold the generation, bits 15..0 hold the age. The generation
    wraps modulo 2**16 -- generations are counters and a wrap is defined. The
    age saturates at 0xFFFF and at 0 -- an age must never wrap to a smaller
    value, which would make a very old entry look fresh and pass the age gate.
    """
    generation16 = int(generation) % GENERATION_WRAP
    age16 = min(max(int(age), 0), AGE_MAX)
    return (generation16 << AGE_BITS) | age16


def unpack_tag(tag):
    """Unpack a u32 tag into its (generation, age) pair.

    Every u32 unpacks; pack_tag(*unpack_tag(tag)) == tag for any tag in range.
    """
    if not 0 <= tag <= TAG_MASK:
        raise ValueError(f'tag out of u32 range: {tag!r}')
    return (tag >> AGE_BITS) & AGE_MAX, tag & AGE_MAX


class Decision(NamedTuple):
    """The outcome of decide(): the action, the refused entries, the reason.

    `refused` lists entry indices whose age exceeds max_age; those entries may
    not be composited. A reset discards the whole epoch regardless.
    `reason` is the decision-table reason text of the governing row.
    """
    action: str
    refused: list
    reason: str


def decide(old_generations, new_generations, entry_ages, max_age=0, camera_continuation=False):
    """Apply the section 3 decision table.

    Both generation mappings use the five names in GENERATIONS; a name absent
    from a mapping reads as generation 0. `entry_ages` holds the age of every
    entry up for compositing, in entry order. `max_age` defaults to 0: a stable
    identity re-submits the same rows every epoch, so their age stays zero and
    continue remains allowed, while an entry that was not refreshed in the
    current epoch is refused.

    A change to scene, lighting, material or settings is a hard reset whatever
    the ages are. A camera-only change always resets unless the caller opted
    in with `camera_continuation=True` (the Stage 3 mode, default off); with
    it, the session continues only when every composited entry has
    age <= max_age. No change continues.
    """
    changed = [name for name in HARD_GENERATIONS
               if old_generations.get(name, 0) != new_generations.get(name, 0)]
    refused = [index for index, age in enumerate(entry_ages) if age > max_age]
    if changed:
        return Decision(ACTION_RESET, refused,
                        '; '.join(ROW_REASONS[name] for name in changed))
    if old_generations.get('camera', 0) != new_generations.get('camera', 0):
        # Camera-only: reset unless camera continuation is opted in, and then
        # only with every composited entry within the age bound. Today's
        # renderer resets here, so the default must not change that.
        if refused or not camera_continuation:
            return Decision(ACTION_RESET, refused, ROW_REASONS['camera'])
        return Decision(ACTION_CONTINUE, refused, ROW_REASONS['camera'])
    return Decision(ACTION_CONTINUE, refused, ROW_REASONS['none'])


def _require_equal_length(*series):
    lengths = {len(values) for values in series}
    if len(lengths) != 1:
        raise ValueError(f'metric inputs must have equal lengths, got {sorted(lengths)}')


def stale_mse(c_policy, c_fresh):
    """Section 4: mean of (C_policy - C_fresh)^2 over the mapped values."""
    _require_equal_length(c_policy, c_fresh)
    if not c_policy:
        return 0.0
    return sum((policy - fresh) ** 2 for policy, fresh in zip(c_policy, c_fresh)) / len(c_policy)


def stale_max_abs(c_policy, c_fresh):
    """Section 4: max of abs(C_policy - C_fresh) over the mapped values."""
    _require_equal_length(c_policy, c_fresh)
    return max((abs(policy - fresh) for policy, fresh in zip(c_policy, c_fresh)), default=0.0)


def stale_fraction(c_policy, c_fresh, c_old):
    """Section 4: fraction of values where the stale pair is the further one.

    Counts the values where abs(C_policy - C_fresh) > abs(C_policy - C_old):
    values the policy action left closer to the old composite than to a fresh
    session. The policy gate is exactly 0; the negative control must be > 0.
    """
    _require_equal_length(c_policy, c_fresh, c_old)
    if not c_policy:
        return 0.0
    hits = sum(1 for policy, fresh, old in zip(c_policy, c_fresh, c_old)
               if abs(policy - fresh) > abs(policy - old))
    return hits / len(c_policy)


def generation_violations(entry_generations, current_generation):
    """Section 4: composited entries whose generation differs from the current one.

    `entry_generations` holds one generation per composited entry; packed tags
    must be unpacked first (see unpack_tag).
    """
    return sum(1 for generation in entry_generations if generation != current_generation)


def age_violations(entry_ages, max_age):
    """Section 4: composited entries with age > max_age."""
    return sum(1 for age in entry_ages if age > max_age)
