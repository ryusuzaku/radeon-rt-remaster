"""Bounded three-preset tradeoff check on an existing noisy constant-colour recording.

One recording is not multi-seed or general quality acceptance. All sources and
SDK dispatches are verified by the existing execution/reference tools.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import time
import numpy as np

from rr_recorded_dispatch import run_recording,admit_record
from inspect_rr_record import MAX_BYTES
from rr_quality import analyze


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('probe','sdk-bin','recording','scene','shader'): parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--samples',type=int,choices=(64,128,256,512,1024),default=512)
    args=parser.parse_args(); started=time.monotonic()
    # Existing admission enforces source/reference dimensions and work caps.
    with args.recording.open('rb') as stream: raw=stream.read(MAX_BYTES+1)
    data=admit_record(raw)
    if data['count']*args.samples>4096: raise ValueError('reference work budget')
    folder=Path(tempfile.mkdtemp(prefix='rr-setting-noise-',dir=args.probe.resolve().parent))
    reports={}; shared=None
    for preset in ('none','stability-half','stability-zero'):
        print(preset+': noisy recording/reference',flush=True)
        output=folder/(preset+'.rrrecordout'); execution=folder/(preset+'-execution.json')
        worker=run_recording(args.probe,args.sdk_bin,args.recording,output,scene=args.scene,shader=args.shader,query_defaults=True,filter_setting=preset)
        execution.write_text(json.dumps(worker),encoding='utf-8')
        if worker['input_sha256']!=raw[-32:].hex(): raise RuntimeError('recording changed during comparison')
        if not worker['decision']['rr_rendering']: raise RuntimeError('recording execution failed; worker evidence retained')
        report,arrays=analyze(args.recording,output,args.scene,args.shader,execution,samples=args.samples,fallback=True,filter_setting=preset)
        if shared is None:
            shared=arrays
            with (folder/'reference.npz').open('xb') as stream: np.savez_compressed(stream,**arrays)
        elif any(not np.array_equal(arrays[k],shared[k]) for k in shared):
            raise RuntimeError('setting changed independent reference/fallback')
        report['reference_file_sha256']=sha256((folder/'reference.npz').read_bytes()).hexdigest()
        (folder/(preset+'-quality.json')).write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
        reports[preset]=dict(gates=report['gates'],frames=[dict(index=f['index'],all=f['all'],temporal=f['temporal'],disoccluded=f['groups']['disoccluded']) for f in report['frames']])
    summary=dict(result='measured',quality_acceptance='not-qualified',scope='one-recording-noise-tradeoff',input_sha256=raw[-32:].hex(),
                 samples_per_batch=args.samples,reports=reports,artifacts=str(folder),elapsed_seconds=time.monotonic()-started)
    (folder/'verification.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(result='measured',artifacts=str(folder),gates={k:v['gates'] for k,v in reports.items()})))


if __name__=='__main__': main()
