"""Actual native shader capture followed by independent-process exact raster replay."""
import argparse
from pathlib import Path
import subprocess
import tempfile

p=argparse.ArgumentParser();p.add_argument('--fixture',type=Path,required=True);a=p.parse_args()
root=Path(tempfile.mkdtemp(prefix='shader-snapshot-',dir=a.fixture.parent))
def run(*args):
    r=subprocess.run([str(a.fixture),*map(str,args)],capture_output=True,text=True,timeout=30)
    assert r.returncode==0,(r.stdout,r.stderr,str(root))
run('--fixture',root)
images=[]
for i in range(3):
    snapshot=root/f'variant-{i}.rrshader';output=root/f'replay-{i}.bgr'
    run('--replay',snapshot,output)
    expected=(root/f'variant-{i}.bgr').read_bytes()
    assert len(expected)==128*96*3 and output.read_bytes()==expected, str(root)
    assert len(set(expected[j:j+3] for j in range(0,len(expected),3)))>=2,'blank fixture'
    images.append(expected)
assert len(set(images))==3,'constant/buffer mutations did not change rendering'
assert (root/'reset-replay.bgr').read_bytes()==images[0],'snapshot depended on pre-reset state'
print(f'PASS: 3 shader snapshots replay pixel-exactly in fresh processes; negatives passed. Artifacts: {root}')
