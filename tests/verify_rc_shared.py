"""Strict same-adapter cross-process D3D12 shared-buffer/fence contract."""
import argparse
import json
from pathlib import Path
import subprocess

EXPECTED_HASH=10972558891643204389
EXPECTED_CACHE_HASHES=[920219675992757029,16317131794596865829,18030334235379617445,9233023709800616485,12161962213042174405]


def need(value,message):
    if not value: raise AssertionError(message)


def run(executable,*args,ok=True):
    process=subprocess.run([str(executable),*map(str,args)],capture_output=True,text=True,timeout=60)
    need((process.returncode==0)==ok,(args,process.stdout,process.stderr))
    return json.loads(process.stdout) if ok else process


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--probe',type=Path,required=True)
    parser.add_argument('--provider-probe',type=Path); parser.add_argument('--sdk-bin',type=Path); args=parser.parse_args()
    first=run(args.probe); repeat=run(args.probe)
    for row in (first,repeat):
        need(row=={'result':'shared-roundtrip-pass','adapter_luid_low':row['adapter_luid_low'],'adapter_luid_high':row['adapter_luid_high'],
                   'bytes':1573120,'payload_hash_fnv1a64':EXPECTED_HASH,'shared_resources':2,'shared_fences':1,'allowlisted_handles':3,
                   'fence_values':[1,2,3],'child_reaped':True,'child_exit_code':0,'cpu_payload_transfer_bytes':0},'shared report mismatch')
        need(type(row['adapter_luid_low']) is int and type(row['adapter_luid_high']) is int,'adapter identity type mismatch')
    need(first==repeat,'shared round trip is not exact')
    cache_first=run(args.probe,'--cache-layout'); cache_repeat=run(args.probe,'--cache-layout')
    expected_cache={'result':'cache-shared-layout-pass','external_buffer_bytes':716808,
                    'sizes':[540672,147456,22528,6144,8],'strides':[44,12,44,12,4],
                    'hashes_fnv1a64':EXPECTED_CACHE_HASHES,'immutable_buffers':[0,2,3],
                    'writable_buffers':[1,4],'counters_cleared':True,'shared_resources':5,
                    'shared_fences':1,'allowlisted_handles':6,'fence_values':[10,11,12],
                    'child_reaped':True,'cpu_payload_transfer_bytes':0}
    need(cache_first==expected_cache and cache_repeat==expected_cache,'cache shared layout report mismatch')
    run(args.probe,'--adapter','32',ok=False)
    run(args.probe,'--shared-child','0','1','2','3',str(first['adapter_luid_low']),str(first['adapter_luid_high']),ok=False)
    run(args.probe,'--cache-child','0','1','1','1','1','1','1',str(first['adapter_luid_low']),str(first['adapter_luid_high']),ok=False)
    if args.provider_probe:
        need(args.sdk_bin and args.sdk_bin.is_absolute(),'provider SDK directory must be absolute')
        provider_expected={'result':'shared-provider-dispatch-pass','external_buffer_bytes':716808,
                           'output_hash_fnv1a64':8439070038676242095,'finite_output_values':36864,
                           'counters_cleared':True,'inputs_unchanged':True,'shared_resources':5,
                           'shared_fences':1,'allowlisted_handles':6,'fence_values':[20,21,22],
                           'child_reaped':True,'child_exit_code':0,'cpu_payload_transfer_bytes':0}
        provider_first=run(args.provider_probe,'--sdk-bin',args.sdk_bin,'--shared-dispatch')
        provider_repeat=run(args.provider_probe,'--sdk-bin',args.sdk_bin,'--shared-dispatch')
        need(provider_first==provider_expected and provider_repeat==provider_expected,'shared provider dispatch report mismatch')
        run(args.provider_probe,'--sdk-bin',args.sdk_bin,'--shared-worker-child',*(['1']*6),
            first['adapter_luid_low'],first['adapter_luid_high'],ok=False)
        run(args.provider_probe,'--sdk-bin',args.sdk_bin,'--shared-path-worker-child',*(['1']*6),
            first['adapter_luid_low'],first['adapter_luid_high'],'172','172','1','32',ok=False)
    print('cross-process shared D3D12 transport contract passed'); return 0


if __name__=='__main__': raise SystemExit(main())
