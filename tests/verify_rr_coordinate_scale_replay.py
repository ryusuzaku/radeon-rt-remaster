"""Replay a completed coordinate-scale grid without recomputing references."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import time
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))

from rr_recorded_dispatch import run_recording

SCALES=('unit-tenth','unit-one','unit-ten')
SETTINGS=('none','stability-zero')


def require(value,message):
    if not value: raise ValueError(message)


def bounded(path,limit=3*1024*1024):
    with Path(path).open('rb') as stream: value=stream.read(limit+1)
    require(len(value)<=limit,'artifact exceeds replay bound'); return value


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('baseline','probe','sdk-bin','scene','shader','materials'): parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args(); started=time.monotonic(); require((args.baseline/'verification.json').is_file(),'missing baseline')
    folder=Path(tempfile.mkdtemp(prefix='rr-coordinate-scale-replay-',dir=args.probe.resolve().parent)); outputs={}
    for surface in ('texture','pbr'):
        material=args.materials if surface=='pbr' else None
        for trajectory in ('moving','reset'):
            label=f'{surface}-{trajectory}-seed-7'; recording=args.baseline/f'{label}.rrcapture'
            require(recording.is_file(),'missing baseline recording')
            for scale in SCALES:
                for setting in SETTINGS:
                    stem=f'{label}-{scale}-{setting}'; output=folder/(stem+'.rrrecordout')
                    worker=run_recording(args.probe,args.sdk_bin,recording,output,scene=args.scene,shader=args.shader,materials=material,
                                         query_defaults=setting!='none',filter_setting=setting,coordinate_scale=scale)
                    require(worker['decision']['rr_rendering'] and bounded(output)==bounded(args.baseline/output.name),('replay changed',stem))
                    outputs[stem]=sha256(bounded(output)).hexdigest()
            stem=f'{label}-unconfigured'; output=folder/(stem+'.rrrecordout')
            worker=run_recording(args.probe,args.sdk_bin,recording,output,scene=args.scene,shader=args.shader,materials=material)
            require(worker['decision']['rr_rendering'] and bounded(output)==bounded(args.baseline/output.name),('replay changed',stem))
            outputs[stem]=sha256(bounded(output)).hexdigest()
    summary=dict(result='pass',scope='coordinate-scale-grid-replay',outputs=outputs,output_count=len(outputs),baseline=str(args.baseline),
                 artifacts=str(folder),elapsed_seconds=time.monotonic()-started)
    (folder/'verification.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:summary[k] for k in ('result','scope','output_count','artifacts','elapsed_seconds')}))


if __name__=='__main__':
    try: main()
    except (OSError,ValueError,KeyError,TypeError,OverflowError) as error:
        print(json.dumps(dict(result='unavailable',reason=str(error)))); raise SystemExit(1)
