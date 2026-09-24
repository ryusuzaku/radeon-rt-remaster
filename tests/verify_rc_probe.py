"""Radiance Cache support-query contract; no context is a rendering claim."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--probe',type=Path,required=True); parser.add_argument('--sdk-bin',type=Path,required=True)
    args=parser.parse_args(); folder=Path(tempfile.mkdtemp(prefix='rc-probe-',dir=args.probe.parent))
    def run(extra):
        return subprocess.run([str(args.probe),*map(str,extra)],capture_output=True,text=True,timeout=60)
    assert run(['--help']).returncode==0
    for extra in ([],['--sdk-bin','relative'],['--sdk-bin',folder],['--unknown'],
                  ['--sdk-bin',args.sdk_bin,'--cycles','2'],['--sdk-bin',args.sdk_bin,'--context-test','--cycles','4'],
                  ['--sdk-bin',args.sdk_bin,'--context-test','--budget-mib','257'],
                  ['--sdk-bin',args.sdk_bin,'--context-test','--worker-timeout-ms','60001']):
        result=run(extra); assert result.returncode==1 and not result.stdout,(extra,result)
    result=run(['--sdk-bin',args.sdk_bin,'--debug']); assert result.returncode in (0,77),result.stderr
    data=json.loads(result.stdout); assert data['sdk_api']=='0.9.0' and data['dispatches']==data['contexts_created']==data['contexts_destroyed']==0
    assert data['shader_model_6_6'] and data['wave_lane_min']<=32<=data['wave_lane_max']
    assert bool(data['providers'])==(result.returncode==0)
    for provider in data['providers']:
        assert type(provider['id']) is int and provider['id']>0 and provider['name']=='0.9.0'
    data['contract_test']='pass'; (folder/'verification.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(result='pass',scope='radiance-cache-support-query',artifacts=str(folder))))


if __name__=='__main__':
    main()
