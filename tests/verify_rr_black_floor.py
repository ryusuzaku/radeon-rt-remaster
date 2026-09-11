"""Exact-zero localization integration contract; the positive floor remains a failed gate."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from verify_dxr import encode_scene,fixture


def need(ok,reason):
    if not ok:
        raise AssertionError(reason)


def main():
    parser=argparse.ArgumentParser()
    for key in ('probe','sdk-bin','dxr'):
        parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args()
    folder=Path(tempfile.mkdtemp(prefix='rr-black-floor-contract-',dir=args.probe.parent))
    scene=folder/'source.rrscene'; scene.write_bytes(encode_scene(fixture()))
    tool=Path(__file__).resolve().parents[1]/'tools'/'rr_black_floor.py'
    command=[sys.executable,str(tool),'--probe',str(args.probe),'--sdk-bin',str(args.sdk_bin),
             '--dxr',str(args.dxr),'--scene',str(scene),'--seed','1']
    process=subprocess.run(command,capture_output=True,text=True,timeout=180)
    need(process.returncode==0,(process.stdout,process.stderr))
    summary=json.loads(process.stdout); need(summary['result']=='pass',summary)
    artifacts=Path(summary['artifacts']); report=json.loads((artifacts/'verification.json').read_text(encoding='utf-8'))
    need(report['quality_acceptance']=='failed-zero-light-oracle' and report['raw_sdk_acceptance']=='failed','failure hidden')
    active=report['variants']['active']; total=128*96
    need(0<active['active_pixels']<total,'fixture must mix active/background pixels')
    for name,row in report['variants'].items():
        stats=row['statistics']
        if name=='background':
            need(row['active_pixels']==0 and stats['all']['nonzero']==0,'background invented light')
        else:
            need(stats['active']['nonzero']==stats['active']['values'] and stats['background']['nonzero']==0,
                 (name,'floor localization changed'))
    need(report['variants']['active']['rgb_matches_active'],'active self comparison failed')
    need(report['variants']['zero-distance']['rgb_matches_active'],'zero distance changed black RGB')
    need(not report['variants']['background']['rgb_matches_active'],'background unexpectedly retained floor')
    need(report['history_first_matches_active'],'recorded/direct reset mismatch')
    need(len(report['history'])==8 and all(x['active']['nonzero']==x['active']['values'] and not x['background']['nonzero'] for x in report['history']),
         'history floor/background localization changed')
    need(report['history'][-1]['active']['mean']>0 and report['history'][-1]['active']['mean']<report['history'][0]['active']['mean'],
         'history no longer has persistent slowly decaying floor')
    print(json.dumps(dict(result='pass',scope='exact-zero-floor-contract',artifacts=str(artifacts))))


if __name__=='__main__':
    main()
