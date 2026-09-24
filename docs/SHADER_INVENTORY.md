# Bounded shader/layout inventory

The proxy now offers a separate diagnostic path for opaque shader programs. It
does not broaden the shader snapshot allowlist or execute captured programs.
Only `DrawIndexedPrimitive` calls on D3D9/9Ex devices are sampled. Queries use
the native pre-draw state; records include the subsequent native HRESULT.

Opt-in environment:

- `RRT_SHADER_INVENTORY_FILE`: exclusive-create JSONL output. Existing files
  are preserved; unavailable output disables the diagnostic, not the game.
- `RRT_SHADER_INVENTORY_TRIGGER_FILE`: optional regular, non-reparse marker.
  Metadata polling is throttled to 100 ms until activation. Nothing is captured
  before activation; activation is at an indexed draw, not a Present boundary.
- `RRT_SHADER_INVENTORY_DRAWS`: 1–4096 indexed attempts, default 512.

Limits: 16 KiB per shader, 65 declaration elements including terminator,
16 referenced streams, 16 MiB total output. Each record contains complete
opaque shader bytes (or explicit null binding), declaration bytes, stream
offset/stride/frequency/bound status, index format, topology, wrapper-generation
device ID, query status and HRESULT. No vertex/index buffer readback, constants,
textures, transformation semantics or world-space reconstruction is included.
Queries acquire only temporary native COM references. Failed queries are explicit.

The ledger deliberately repeats bytecode for each bounded sample. Consequently
the byte budget may stop sampling before the draw budget. A footer distinguishes
draw limit, byte limit and internal/I/O error. Process exit before a limit leaves
a partial ledger; a truncated record is rejected. This is not whole-game coverage
or a real-time performance qualification.

`python tools/inspect_shader_inventory.py path/to/shader-inventory.jsonl`
validates bounded JSONL on the CPU and groups successful draws by program hashes,
declaration, stream stride/frequency/bound status, topology and index format.
Stream offset is preserved in source evidence but excluded from family identity.
Shader version tokens are reported as raw tokens, not interpreted capabilities.
Failed native draws do not contribute family counts.

Game runner: `run PASS --mode proxy --name inventory --wait-trigger
--shader-inventory` arms independent trace and inventory outputs. The existing
`trigger PASS --name inventory` command activates both; their start boundaries
and budgets are independent. The runner selects 4096 inventory attempts and
retains existing baseline/hash-guarded deployment and cleanup requirements.

Tests cover unchanged pixels, unknown-but-equivalent program evidence while
snapshot admission still rejects it, bounded draw/byte stops, partial capture,
failed native draws, trigger gating, disabled mode, collisions, absent output
parents, malformed reader inputs and real runner activation/cleanup.
