"""Render equivalence and actual trace assertions; retains artifacts in the build tree."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from inspect_trace import inspect

parser=argparse.ArgumentParser()
parser.add_argument('--sample',required=True,type=Path)
parser.add_argument('--ex',action='store_true')
options=parser.parse_args()
sample=options.sample.resolve()
artifacts=Path(tempfile.mkdtemp(prefix='verify-ex-' if options.ex else 'verify-classic-',dir=sample.parent))
base_env={k:v for k,v in os.environ.items() if not k.startswith('RRT_')}

def run(name,runtime='proxy',trace=True,**variables):
    path=artifacts/(name+'.rrt.jsonl')
    pixels=artifacts/(name+'.pixels')
    env=base_env.copy()
    if trace: env['RRT_TRACE_FILE']=str(path)
    env.update({k:str(v) for k,v in variables.items()})
    command=[str(sample),'--runtime',runtime,'--frames','12','--pixels',str(pixels)]
    if options.ex: command+=['--ex']
    result=subprocess.run(command,env=env,text=True,capture_output=True,timeout=30)
    if result.returncode:
        raise AssertionError(f'{name} failed ({result.returncode}): {result.stdout}\n{result.stderr}\nArtifacts: {artifacts}')
    return json.loads(result.stdout),pixels.read_bytes(),path

baseline=run('system',runtime='system',trace=False)
assert len({baseline[1][i:i+3] for i in range(0,len(baseline[1]),3)})>=5, 'fixture did not render the four-color texture and background'
capture=run('capture')
repeat=run('repeat')
disabled=run('disabled',RRT_PROXY_DISABLE=1)
off=run('off',trace=False)
assert baseline[:2]==capture[:2]==repeat[:2]==disabled[:2]==off[:2], 'render output differs from system D3D9'
assert not disabled[2].exists() and not off[2].exists(), 'disabled tracing produced a file'
report=inspect(capture[2],frame=0)
again=inspect(repeat[2],frame=0)
# OS thread IDs are capture provenance, not deterministic scene identities.
for summary in (report,again):
    for event in summary['timeline']: event.pop('thread_id')
assert report==again, 'trace identities/counters/metadata are not repeatable'
assert report['presents']==12 and report['draws']==36, report
assert report['fixed_draws']==24 and report['shader_draws']==12, report
assert report['methods'].get('ResetEx' if options.ex else 'Reset')==2, report
assert report['failed_calls']>=3, report
assert report['live_objects_at_end']==0, 'COM wrappers leaked'
for interface in ('IDirect3DVertexBuffer9','IDirect3DIndexBuffer9','IDirect3DTexture9','IDirect3DStateBlock9','IDirect3DVertexShader9','IDirect3DPixelShader9'):
    assert report['resource_types'].get(interface,0)>=2, interface
selection=run('selection',RRT_TRACE_START_FRAME=2,RRT_TRACE_FRAME_COUNT=3)
selected=inspect(selection[2])
assert selected['completion']=='frame_limit' and selected['presents']==3 and selected['draws']==9,selected
assert set(selected['frames'])=={2,3,4},selected
assert selection[:2]==baseline[:2]
bounded=run('bounded',RRT_TRACE_MAX_BYTES=4096)
trigger=artifacts/'capture.trigger'
trigger.write_text('capture\n',encoding='ascii')
triggered=run('triggered',RRT_TRACE_TRIGGER_FILE=trigger,RRT_TRACE_START_FRAME=2,RRT_TRACE_FRAME_COUNT=3)
triggered_report=inspect(triggered[2])
assert triggered_report['presents']==3 and triggered_report['draws']==9 and set(triggered_report['frames'])=={2,3,4},triggered_report
assert triggered[:2]==baseline[:2]
never=run('never-triggered',RRT_TRACE_TRIGGER_FILE=artifacts/'absent.trigger')
assert inspect(never[2])['events']==0 and never[:2]==baseline[:2]
directory_trigger=run('directory-trigger',RRT_TRACE_TRIGGER_FILE=artifacts)
assert inspect(directory_trigger[2])['events']==0 and directory_trigger[:2]==baseline[:2]
assert inspect(bounded[2])['completion']=='byte_limit'
assert bounded[2].stat().st_size<=4096
assert bounded[:2]==baseline[:2]
# A trace failure must not change rendering or overwrite existing user captures.
before=capture[2].read_bytes()
collision=run('collision',RRT_TRACE_FILE=capture[2])
assert collision[:2]==baseline[:2] and capture[2].read_bytes()==before
badpath=run('badpath',RRT_TRACE_FILE=artifacts/'missing'/'trace.jsonl')
assert badpath[:2]==baseline[:2]
print(f"PASS {'D3D9Ex' if options.ex else 'D3D9'}: exact pixels, identity/lifetimes, 36 draws, 12 presents, reset recovery, repeatability, selection, bounds, trace failure isolation.")
print(f'Artifacts: {artifacts}')
