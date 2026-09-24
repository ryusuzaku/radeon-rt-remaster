"""Compare intercepted single-draw artifacts with the standalone native oracle."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile
p=argparse.ArgumentParser();p.add_argument('--fixture',type=Path,required=True);p.add_argument('--proxy',type=Path,required=True);a=p.parse_args()
root=Path(tempfile.mkdtemp(prefix='shader-proxy-',dir=a.fixture.parent))
clean={k:v for k,v in os.environ.items() if not k.upper().startswith('RRT_')}
def run(name,variables):
    out=root/name;out.mkdir();env=dict(clean,**{k:str(v) for k,v in variables.items()})
    r=subprocess.run([str(a.fixture),'--fixture',str(out)],env=env,capture_output=True,text=True,timeout=30)
    assert r.returncode==0,(name,r.stdout,r.stderr,str(root))
    return out
oracle=run('native',{})
for ordinal in (0,1,2,3):
    snapshot=root/f'captured-{ordinal}.rrshader'
    out=run(f'proxy-{ordinal}',dict(RRT_FIXTURE_PROXY=a.proxy,RRT_SHADER_SNAPSHOT_FILE=snapshot,RRT_SHADER_SNAPSHOT_DRAW=ordinal))
    expected=ordinal if ordinal<3 else 0
    assert snapshot.read_bytes()==(oracle/f'variant-{expected}.rrshader').read_bytes(),str(root)
    for variant in range(3):
        assert (out/f'variant-{variant}.bgr').read_bytes()==(oracle/f'variant-{variant}.bgr').read_bytes()
    pixels=root/f'replay-{ordinal}.bgr'
    r=subprocess.run([str(a.fixture),'--replay',str(snapshot),str(pixels)],env=clean,capture_output=True,text=True,timeout=30)
    assert r.returncode==0,(r.stdout,r.stderr)
    assert pixels.read_bytes()==(oracle/f'variant-{expected}.bgr').read_bytes()
for mode in ('stateblock','recording','discard','failed-draw','reset-missing','retire-missing'):
    snapshot=root/f'{mode}.rrshader'
    run(mode,dict(RRT_FIXTURE_PROXY=a.proxy,RRT_SHADER_SNAPSHOT_FILE=snapshot,RRT_SHADER_FIXTURE_CASE=mode))
    assert not snapshot.exists() and Path(str(snapshot)+'.rejected').is_file(),(mode,str(root))
snapshot=root/'refreshed.rrshader'
run('refreshed',dict(RRT_FIXTURE_PROXY=a.proxy,RRT_SHADER_SNAPSHOT_FILE=snapshot,RRT_SHADER_FIXTURE_CASE='stateblock-refresh'))
assert snapshot.read_bytes()==(oracle/'variant-0.rrshader').read_bytes()
snapshot=root/'retire-refreshed.rrshader'
run('retire-refreshed',dict(RRT_FIXTURE_PROXY=a.proxy,RRT_SHADER_SNAPSHOT_FILE=snapshot,RRT_SHADER_FIXTURE_CASE='retire-refresh'))
assert snapshot.read_bytes()==(oracle/'variant-0.rrshader').read_bytes()
snapshot=root/'reset-refreshed.rrshader'
run('reset-refreshed',dict(RRT_FIXTURE_PROXY=a.proxy,RRT_SHADER_SNAPSHOT_FILE=snapshot,RRT_SHADER_FIXTURE_CASE='reset-refresh'))
assert snapshot.read_bytes()==(oracle/'variant-0.rrshader').read_bytes()
for name,variables in [('off',{}),('disabled',{'RRT_PROXY_DISABLE':'1'})]:
    snapshot=root/f'{name}.rrshader'
    env=dict(RRT_FIXTURE_PROXY=a.proxy,**variables)
    if name=='disabled':env['RRT_SHADER_SNAPSHOT_FILE']=snapshot
    run(name,env)
    assert not snapshot.exists() and not Path(str(snapshot)+'.rejected').exists()
collision=root/'collision.rrshader';collision.write_bytes(b'existing user artifact')
run('collision',dict(RRT_FIXTURE_PROXY=a.proxy,RRT_SHADER_SNAPSHOT_FILE=collision))
assert collision.read_bytes()==b'existing user artifact'
run('missing-directory',dict(RRT_FIXTURE_PROXY=a.proxy,RRT_SHADER_SNAPSHOT_FILE=root/'absent'/'capture.rrshader'))
print(f'PASS proxy shader snapshot: oracle-identical captures/replays, state-block/undefined/failed-draw rejection, default-off, collision preservation. {root}')
