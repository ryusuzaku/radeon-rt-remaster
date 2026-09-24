"""Inspect captured scene candidates, or import explicit assignments offline.

Assignments are caller assertions, never inferred game-object correspondence.
The source digest scopes draw ordinals to one immutable ledger snapshot.
"""
import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import struct

from inspect_position_capture import inspect_bytes
from texture_assets import TextureAssets
from position_scene import Geometry, Instance, Scene


@dataclass(frozen=True)
class Candidate:
    ordinal: int
    geometry: Geometry
    constants: tuple
    device: int | None
    provenance: tuple | None
    target: tuple
    viewport: str
    draw_range: tuple
    timing: tuple | None
    render_state_json: str | None
    write_evidence_json: str | None
    surface_scope_json: str | None
    color_replay_json: str | None
    material_inputs_json: str | None
    pixel_material_json: str | None
    texture_inputs_json: str | None


PROVENANCE = ('vb_id', 'vb_revision', 'ib_id', 'ib_revision',
              'reset_epoch', 'knowledge_revision')
DRAW_RANGE = ('offset', 'stride', 'base', 'minimum', 'vertices',
              'start', 'primitives', 'vb_size', 'ib_size')
TIMING = ('reset_epoch', 'present_interval', 'indexed_draw')


class Capture:
    def __init__(self, path):
        with Path(path).open('rb') as stream:
            data = stream.read(16 * 1024 * 1024 + 1)
        report = inspect_bytes(data, include_records=True, assets=TextureAssets(path))
        if report['completion'] not in ('capture_limit', 'attempt_limit', 'byte_limit', 'present_limit'):
            raise ValueError('completed non-I/O-error capture required')
        self.digest = hashlib.sha256(data).hexdigest()
        self.version = report['version']
        self.session = report['session']
        self.selection = report['selection']
        self.limits = report['limits']
        self.candidates = tuple(Candidate(
            r['ordinal'], Geometry(bytes.fromhex(r['positions'])),
            struct.unpack('<32f', bytes.fromhex(r['constants'])),
            r.get('device') if self.version >= 2 else None,
            tuple(r['provenance'][k] for k in PROVENANCE) if self.version >= 2 else None,
            tuple(r['target']), r['viewport'], tuple(r[k] for k in DRAW_RANGE),
            tuple(r['timing'][k] for k in TIMING) if self.version >= 3 else None,
            json.dumps(r['render_state'],sort_keys=True) if self.version>=6 else None,
            json.dumps(r['write_evidence'],sort_keys=True) if self.version>=8 else None,
            json.dumps(r['surface_scope'],sort_keys=True) if self.version>=9 else None,
            json.dumps(r['color_replay'],sort_keys=True) if self.version>=10 else None,
            json.dumps(r['material_inputs'],sort_keys=True) if self.version>=11 else None,
            json.dumps(r['pixel_material'],sort_keys=True) if self.version>=12 else None,
            json.dumps(r['texture_inputs'],sort_keys=True) if self.version>=13 else None,
        ) for r in report['records'])

    def _assign(self, digest, assignments):
        if digest != self.digest:
            raise ValueError('assignment source digest mismatch')
        if type(assignments) is not dict or len(assignments) > self.limits['total']:
            raise ValueError('bounded ordinal-to-instance assignment map required')
        by_ordinal = {c.ordinal: c for c in self.candidates}
        updates = []
        for ordinal, identity in assignments.items():
            if type(ordinal) is not int or ordinal not in by_ordinal:
                raise ValueError('assignment must name an accepted draw ordinal')
            c = by_ordinal[ordinal]
            updates.append(Instance(identity, c.geometry, c.constants))
        if len({u.identity for u in updates}) != len(updates):
            raise ValueError('ambiguous assignment: multiple draws target one instance')
        return updates

    def report(self, assignments=None):
        assignments = {} if assignments is None else assignments
        self._assign(self.digest, assignments)
        return {'schema': 'rrt-position-scene-import', 'version': 1,
                'source_sha256': self.digest, 'capture_version': self.version,
                'capture_session': self.session,
                'selection': self.selection,
                'limits': self.limits,
                'coverage': {'submitted_draws': len(self.candidates),
                             'position_content_count': len({c.geometry.key for c in self.candidates}),
                             'submitted_triangles': sum(len(c.geometry.corners)//36 for c in self.candidates)},
                'scope': 'offline position-only; assignments are caller assertions, not tracked objects',
                'candidates': [{
                    'ordinal': c.ordinal, 'geometry_key': c.geometry.key,
                    'triangles': len(c.geometry.corners) // 36,
                    'instance': assignments.get(c.ordinal),
                    'correspondence': 'explicit' if c.ordinal in assignments else 'unresolved',
                    'device': c.device,
                    'render_state': json.loads(c.render_state_json) if c.render_state_json is not None else None,
                    'write_evidence': json.loads(c.write_evidence_json) if c.write_evidence_json is not None else None,
                    'surface_scope': json.loads(c.surface_scope_json) if c.surface_scope_json is not None else None,
                    'color_replay': json.loads(c.color_replay_json) if c.color_replay_json is not None else None,
                    'material_inputs': json.loads(c.material_inputs_json) if c.material_inputs_json is not None else None,
                    'pixel_material': json.loads(c.pixel_material_json) if c.pixel_material_json is not None else None,
                    'texture_inputs': json.loads(c.texture_inputs_json) if c.texture_inputs_json is not None else None,
                    'timing': dict(zip(TIMING, c.timing)) if c.timing is not None else None,
                    'resource_provenance': dict(zip(PROVENANCE, c.provenance)) if c.provenance is not None else None,
                    'draw_range': dict(zip(DRAW_RANGE, c.draw_range)),
                    'target': c.target, 'viewport': c.viewport,
                } for c in self.candidates]}

    def apply(self, scene, epoch, sequence, digest, assignments, removes=()):
        updates = self._assign(digest, assignments)
        # Build the evidence report before the sole mutating operation.
        report = self.report(assignments)
        report['scene_delta'] = scene.apply(epoch, sequence, updates, removes)
        return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('capture', type=Path)
    p.add_argument('--assign', action='append', default=[], metavar='ORDINAL=INSTANCE')
    p.add_argument('--source-sha256', help='required with --assign; guards saved assignments')
    args = p.parse_args()
    try:
        capture = Capture(args.capture)
        assignments = {}
        for entry in args.assign:
            ordinal, identity = entry.split('=', 1)
            ordinal = int(ordinal)
            if ordinal in assignments:
                raise ValueError('duplicate draw assignment')
            assignments[ordinal] = identity
        report = (capture.apply(Scene(), 0, 0, args.source_sha256, assignments)
                  if assignments else capture.report())
        print(json.dumps(report, indent=2))
    except (OSError, ValueError, TypeError, KeyError) as e:
        p.exit(2, f'capture scene rejected: {e}\n')


if __name__ == '__main__':
    main()
