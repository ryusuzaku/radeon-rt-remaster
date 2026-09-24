# Explicit dirty texture evidence (v17)

V17 adds --position-dirty-textures / RRT_POSITION_DIRTY_TEXTURES=1, requiring
v16 texture uploads and all prerequisites. It admits exact NO_DIRTY_UPDATE locks
on tracked private usage-zero SYSTEMMEM textures and observes AddDirtyRect there.
Managed/default-pool lock admission and earlier capture versions stay unchanged.

## Bytes and dirty proof are separate

A successful writable lock establishes initialized bytes only after native
unlock succeeds. NO_DIRTY_UPDATE uses the same bounded row/block copying, but
does not create new dirty proof. Existing creation/full-dirty proof is preserved.
Thus a freshly created texture can still be fully dirty after those writes;
after an UpdateTexture consumes that proof, further such writes need a separate
full notification or a whole top-level write before another full upload.

A successful AddDirtyRect(nullptr) or exact whole-base rectangle proves the
entire chain dirty. A valid partial rectangle preserves existing proof without
upgrading a partial region to a full one. Rectangles are checked against the
base dimensions. Failed/invalid notifications, pending locks, stale epochs or
observed overlap/history gaps invalidate conservatively. The metadata operation
does not initialize any bytes; alias-invalidated contents remain unknown even
after a full notification. Several partial rectangles are not unioned.

The rules follow the D3D9 [dirty-region contract](https://learn.microsoft.com/en-us/windows/win32/direct3d9/texture-dirty-regions).
Every UpdateTexture attempt still consumes proof, and the existing whole-chain
upload checks and memory/asset budgets apply (TEXTURE_UPLOAD_QUALIFICATION.md).

## Capture and replay

Default-pool v17 transfer objects add dirty_proof, one of creation, top_lock or
notification. It records how the source had been proven fully dirty before the
observed upload. It is separate from the source byte revision. The reader
requires this field in v17, rejects it in v16 and validates its values. Managed
records keep their existing shape. Importer and isolated pixel replay preserve
the evidence; replay still uses managed diagnostic textures and does not execute
the recorded lifecycle or prove full-frame equivalence.

## Native qualification

tests/qualify_dirty_texture.py runs through the independent texture_dirty CTest or directly with
--capture <material-ledger> --fixture <exe> --proxy <dll>. For RGBA/DXT1/3/5 it
checks fresh NO_DIRTY_UPDATE initialization, changed chains plus null/full-rect
notifications, a top-level write restoring proof, and partial notifications after
a full one. Every byte/block in all16 captured draws is independently checked;
the first draw of each accepted scenario replays. All24 native float images per
scenario have matching hashes with and without the proxy.

Missing/partial notifications, aliased unknown bytes and invalid rectangles
reject. Old v16 native runs, malformed/missing/downgraded proof fields, managed
NO_DIRTY_UPDATE writes and invalid prerequisites reject. A v17 managed control
remains admitted. Results: dirty-texture-comparison.json beside fixture ledgers.

Release evidence covers20 accepted and16 rejected native scenarios,16 malformed
records and four legacy runs. All36 native/proxy image hashes match;20 restored
draws match at maximum6.93656e-8 normalized error. Regression timings come from
`ctest --test-dir build/x86-vs -C Release -R '^texture_dirty$'`, which regenerates
this evidence rather than recording it in a document.

V18 now qualifies explicit UpdateSurface rectangles (SURFACE_UPLOAD_QUALIFICATION.md).
Next qualify game-sized isolated material comparison. No new HL2 pass is needed
yet. Texture upscaling remains planned after faithful material evidence.
