"""Fresh cross-build replay of retained exact-zero floor evidence."""
import argparse
import json
from pathlib import Path
import subprocess
import sys


FILES=('black.rrcapture','history.rrrecordout','active.rrinputs','active.rrout',
       'zero-albedo.rrinputs','zero-albedo.rrout','zero-distance.rrinputs','zero-distance.rrout',
       'background.rrinputs','background.rrout')


def need(ok,reason):
    if not ok:
        raise AssertionError(reason)


def main():
    parser=argparse.ArgumentParser()
    for key in ('baseline','probe','sdk-bin','dxr','scene'):
        parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args(); baseline=args.baseline.resolve(strict=True)
    tool=Path(__file__).resolve().parents[1]/'tools'/'rr_black_floor.py'
    process=subprocess.run([sys.executable,str(tool),'--probe',str(args.probe),'--sdk-bin',str(args.sdk_bin),
                            '--dxr',str(args.dxr),'--scene',str(args.scene),'--seed','1'],
                           capture_output=True,text=True,timeout=180)
    need(process.returncode==0,(process.stdout,process.stderr))
    result=json.loads(process.stdout); need(result['result']=='pass',result); replay=Path(result['artifacts'])
    for name in FILES:
        need((replay/name).read_bytes()==(baseline/name).read_bytes(),name+' changed across builds')
    old=json.loads((baseline/'verification.json').read_text(encoding='utf-8'))
    new=json.loads((replay/'verification.json').read_text(encoding='utf-8'))
    for key in ('quality_acceptance','raw_sdk_acceptance','seed','recording_sha256','history_output_sha256',
                'history','history_first_matches_active'):
        need(new[key]==old[key],key+' summary changed')
    for name in old['variants']:
        for key in ('input_sha256','output_sha256','active_pixels','statistics','rgb_matches_active'):
            need(new['variants'][name][key]==old['variants'][name][key],name+' '+key+' changed')
    print(json.dumps(dict(result='pass',scope='fresh-cross-build-exact-zero-floor-replay',
                          files=len(FILES),baseline=str(baseline),artifacts=str(replay))))


if __name__=='__main__':
    main()
