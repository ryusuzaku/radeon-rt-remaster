"""Local-evidence reconstruction, matrix and output-preservation checks."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from reconstruct_positions import reconstruct,inverse
p=argparse.ArgumentParser();p.add_argument('--capture',type=Path,required=True);a=p.parse_args()
root=Path(tempfile.mkdtemp(prefix='position-reconstruction-',dir=a.capture.parent))
matrix=[[2,1,0,5],[0,3,0,-2],[0,0,4,7],[0,0,0,1]];inv=inverse(matrix)
assert inv and all(abs(sum(matrix[i][k]*inv[k][j] for k in range(4))-(i==j))<1e-12 for i in range(4) for j in range(4))
assert inverse([[0]*4 for _ in range(4)]) is None
out=root/'mesh';report=reconstruct(a.capture,out)
assert report['draws'] and len(list(out.glob('*.obj')))==2*len(report['draws'])
for draw in report['draws']:
    for space in ('input','model-output'):
        lines=(out/f'draw-{draw["ordinal"]}-{space}.obj').read_text().splitlines()
        vertices=[line for line in lines if line.startswith('v ')];faces=[line for line in lines if line.startswith('f ')]
        assert len(vertices)==draw['vertices'] and len(faces)==draw['triangles']
        assert all(1<=int(index)<=len(vertices) for face in faces for index in face.split()[1:])
assert sorted(x for group in report['render_groups'] for x in group)==sorted(d['ordinal'] for d in report['draws'])
before=(out/'manifest.json').read_bytes()
try:reconstruct(a.capture,out)
except FileExistsError:pass
else:raise AssertionError('existing output overwritten')
assert (out/'manifest.json').read_bytes()==before
bad=root/'bad.jsonl';bad.write_text('{"kind":"header","schema":"rrt-position-capture","version":1}\n')
try:reconstruct(bad,root/'should-not-exist')
except ValueError:pass
else:raise AssertionError('empty partial capture admitted')
assert not (root/'should-not-exist').exists()
print(f'PASS reconstruction indices/counts, matrix inverse, render grouping, partial rejection, collision preservation: {root}')
