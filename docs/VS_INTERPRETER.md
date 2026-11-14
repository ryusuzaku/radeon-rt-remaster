# vs_2_0 position interpreter

Position capture used to need one hand-written CPU evaluator per vertex program ([first](HL2_POSITION_CONTRACT.md),
[static-prop](HL2_FLEX_POSITION_CONTRACT.md), [skinned](HL2_SKINNED_POSITION_CONTRACT.md)). The 20 programs still refused in the
2026-11-10 gameplay frame compute the same formulas, but the compiler reorders instructions, commutes operands and places `def`
constants differently. Five match the first program's position path instruction for instruction; the rest do not. Q12 in the
[codebase map](../CODEBASE_MAP.md) asked whether to keep writing evaluators or build a generic path. This is the generic path: an
interpreter that runs each program's own position instructions.

## What it does

`src/shader/vs_interpreter.cpp`:

- **Analyse** parses the `vs_2_0` token stream (`dcl`, `def`, the `CTAB` constant table, instructions with relative addressing)
  and takes the backward slice of `oPos`, per register component through write masks, swizzles and `a0`. Lighting, texture and fog
  code drops out.
- **Refusals**, each named:
  - other shader models;
  - predication and subroutines;
  - opcodes in the slice other than `mov add mul mad dp3 dp4 min max abs mova`;
  - source modifiers other than negate, and result modifiers or shifts;
  - a slice instruction inside flow control;
  - an uninitialised temporary or address register;
  - an undeclared input.
- **Evaluate** runs only the slice, in program order, one float32 operation at a time. Unknown constants and nonfinite values
  refuse the vertex.
- **The camera** comes from the program's constant table: `cViewProj`, or `cModelViewProj` with `cModel`. It is the title's own
  naming, read from the program rather than assumed.

## How it is verified

- **Equality with the hand-written evaluators.** On the three hand-admitted programs the interpreter equals all three evaluators
  bit for bit: 4,000 random trials each, with random constants and inputs.
- **GPU point oracle for any program.** The program is instrumented:
  - its `oPos` writes go to a free temporary, and its own `oT7` writes to another;
  - two instructions are appended, `oPos = v[free]` and `oT7 = temporary`;
  - every vertex is drawn as a one-pixel point at a fixed screen position.

  Each pixel of an RGBA32F target then holds the hardware's full clip vector for one vertex. Unlike the earlier raster oracles,
  this compares clip z directly, not only through clipping, and it works for any constants. Each program runs with its own
  declaration from the inventory, 2,048 vertices in four variants with both settings of the boolean constants.
- **Synthetic programs**, assembled token by token, cover what the title's programs never exercise:
  - `mova` rounding of fractional and negative values;
  - the negate modifier;
  - `min`, `max`, `abs` and `dp3`, with swizzles and partial write masks.

  Building them found three `vs_2_0` validation rules the runtime enforces: at most one input register and one constant register
  per instruction, no `_abs` source modifier, and no `sub`. The interpreter refuses `sub` and `_abs`, which no valid program
  contains.
- **Mutations** each fail an oracle:
  - `dp4` dropping w;
  - `mova` truncating;
  - negate ignored;
  - D3DCOLOR read as RGBA;
  - `min` computed as `max`;
  - `dp3` reading w;
  - `abs` ignored.
- **An independent Python implementation** (`tools/vs_interpreter.py`) in the reader. It evaluates in double precision with a
  float32 rounding bound carried through every operation. A `mova` too close to a rounding boundary for that bound to decide is
  refused as ambiguous. C++ and Python agree on the slice length of all 23 programs in the frame.

Result on an RX 9070 XT, 2026-11-10: all 20 refused programs, and the three hand-admitted ones, pass the point oracle with maximum
error 0.

## Admission and capture

Interpretation is still pinned per program. `docs/schemas/interpreted-vertex-programs.json` lists the 20 programs that passed the
oracle; `src/shader/interpreted_programs.h` holds the same list for the proxy, and `tests/verify_interpreted_program_list.py` keeps
them identical. The three hand-admitted programs keep their own evaluators. Admitting another program means running its oracle and
adding its digest; no C++ changes.

`CaptureInterpreted` (position-only; material capture refuses these programs) requires:

- exactly one declaration element per input the slice reads, of a supported type (FLOAT1-4, D3DCOLOR, UBYTE4(N), SHORT2/4(N),
  USHORT2/4N);
- a tracked buffer on each stream it uses, with frequency 1;
- the observed bytes of every corner's inputs;
- every float register the slice reads, statically or per vertex through `a0`, to be known.

The proxy now passes the shadow of every bound stream, not only streams 0 and 2.

The record holds:

- the program and declaration;
- each input's stream, offset, type and raw bytes per corner;
- the registers read, plus the camera's, with their values;
- the camera the constant table names, or `null` when its registers are unknown or the program names none;
- one clip position per corner.

The reader re-derives all of it: the inputs must be exactly the slice's, each input must lie inside its buffer, the registers must
be exactly those the vertices read plus the camera's, and every clip component must match.

The converter places a vertex at `VP^-1 * clip` under an identity world, with `VP` = `cViewProj`, or `cModelViewProj * cModel^-1`.
Draws with a `null` camera are refused rather than placed under an assumed camera; four of the 20 programs (screen-space overlays
and a `cModelViewProj`-only program) have none. Grouping by camera keeps a draw whose derived camera differs, such as a weapon view
model with its own field of view, in a scene of its own.

## Tests

- `vs_interpreter` (`tests/verify_vs_interpreter.py`, local evidence, `RRT_HL2_FRAME_INVENTORY`). For every admitted program in the
  inventory it runs:
  - the self-test and the synthetic oracle;
  - the point oracle and the C++/Python slice agreement;
  - a proxy capture of four draws, accepted by the reader.

  It then requires the reader to refuse altered input bytes, a dropped register, a wrong camera, a changed program byte and a
  missing input.
- `vs_interpreter_python` (`tests/test_vs_interpreter.py`, also in the Linux CI job): the Python interpreter on synthetic token
  programs. It checks the slice, evaluation semantics, `mova` rounding and relative reads, the float32 allowance, input conversion,
  ambiguity, and 11 refusals.
- `interpreted_program_list` (also in CI): the list contract.
- `position_to_scene`: both camera forms in one scene, a scaled clip refused by the gate, and the camera-less refusal.

## What it does not establish

- Programs outside the admitted list, other titles or later shader models: each needs its oracle run first.
- Anything about non-position outputs or materials.
- That a `null`-camera draw belongs to the frame's camera.
- World-space meaning, units or handedness, as for the hand-admitted programs.
