# Bounded clear evidence and initial-content admission (v7)

Runner option `--position-clear-evidence` requires `--position-render-state` and
its selected multi-draw prerequisites. It sets `RRT_POSITION_CLEAR_EVIDENCE=1`.
The new mode retains the existing16-draw/4-per-interval,4096-attempt,16MiB ledger
and120-Present limits. Other modes retain their previous schemas and behavior.

## Capture contract

Before each native Clear, the hook copies at most16 D3DRECTs plus flags, colour,
raw float32 depth bits and stencil value. It also records the currently bound
target0/depth surface lifetime IDs, target descriptor, viewport, scissor enable,
reset epoch and expected clear serial. No caller memory pointer is retained.

Only a successful native call commits this payload as the device's `last_clear`.
A failed Clear leaves the prior successful evidence/serial unchanged. A successful
call whose payload was unavailable, oversized or concurrently superseded advances
the boundary but replaces `last_clear` with null. Thus an older clear cannot be
mistaken for an unrecorded newer clear. Only one bounded latest payload per tracked
device is retained; this is not a complete event history.

Each accepted v7 draw carries that payload under `render_state.last_clear`, or
null. It can refer to another target or an older reset: consumers must check those
identities, not assume the latest device clear initialized the current attachment.
The reader validates exact shape, integer/rectangle bounds, viewport encoding,
serial agreement and reset ordering. Raw depth bits are preserved exactly even
when a depth argument is unused; admission checks the depth range when needed.

## Initial-content assessment

`tools/position_initial_contents.py` assesses already validated records. Grouped
replay reports its result as `initial_content_admission`.

A full-target clear candidate requires matching target identity/descriptor and
reset epoch, no explicit rectangles, a full-target viewport, disabled scissor,
and supported clear flags. Depth/stencil candidates additionally require a
matching bound depth attachment and relevant flags; depth values must be in0..1.
Partial clears, missing payload, mismatched targets/epochs and uncleared required
attachments produce explicit reasons.

**Every result currently remains `initial_contents: unknown` and
`ready_for_stateful_replay: false`.** A full-clear candidate proves observed clear
parameters, not the contents at a later sampled draw. The sampled ledger may omit
intervening draws, copies, locks, resource writes or attachment activity. Promoting
it without ordered write coverage would create incorrect depth/blending results.

The existing grouped GPU replay remains explicitly diagnostic, with its own clear
and depth/blending disabled. Neither captured clear parameters nor recorded depth/
blend state are silently applied as a reconstruction of the game frame.

## Tests and next boundary

Native fixtures verify full and partial clears, exact depth/stencil arguments,
failed-clear preservation and successful17-rectangle unknown fallback while
preserving raster output. Reader mutations cover missing payload, serial/epoch
errors, oversized rectangles and malformed values. Admission tests cover another
target, older reset, partial viewport and the mandatory unknown-content guard.

Next add bounded ordered write coverage and gap markers around sampled draws.
Only a segment with a qualified initialization and no unexplained intervening
writes can be admitted to state-aware replay. MRTs, complete stencil operations,
pixel/material behavior and multisample semantics still need explicit contracts.
