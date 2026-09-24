"""Finish a local completed grid whose final audit interrupted manifest publication.

Revalidates saved source/output/execution/report hashes and corrected seed audit.
Does not recompute Monte Carlo references or accept saved estimates into analysis.
Use only for retained local experiment evidence, not third-party certification.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from inspect_rr_record import MAX_BYTES
from rr_worker import strict_json,DLL_HASHES
from rr_recorded_dispatch import admit_record,assess_recording,decode_recording_output,IDENTITIES
from rr_setting_surfaces import SEEDS,PRESETS,require,seed_fingerprints,audit_seeds,paired_summary


def read(path,maximum):
    with path.open('rb') as stream: data=stream.read(maximum+1)
    require(len(data)<=maximum,'artifact oversized'); return data


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('folder',type=Path); args=parser.parse_args()
    folder=args.folder.resolve(); require(not (folder/'verification.json').exists(),'manifest already exists')
    cases={}; samples=None
    for surface in ('texture','pbr'):
        for seed in SEEDS:
            label=f'{surface}-seed-{seed}'; raw=read(folder/(label+'.rrcapture'),MAX_BYTES); data=admit_record(raw)
            require(data['count']==4 and data['settings']['seed']==seed,'unexpected capture contract')
            signal,guides=seed_fingerprints(data)
            reference_hash=sha256(read(folder/(label+'-reference.npz'),16*1024*1024)).hexdigest(); reports={}
            for preset in PRESETS:
                stem=folder/(label+'-'+preset)
                execution_bytes=read(Path(str(stem)+'-execution.json'),1024*1024); execution=strict_json(execution_bytes.decode('utf-8'))
                require(execution['input_sha256']==raw[-32:].hex() and execution['sdk_sha256']==DLL_HASHES,'execution pin/input mismatch')
                require(execution.get('filter_setting','none')==preset and execution.get('albedo_encoding','linear')=='linear','execution preset/encoding mismatch')
                decision=assess_recording(execution['worker'],raw,query_defaults=True,filter_setting=preset)
                require(decision['status']=='recording-report-ready','saved worker not admitted')
                output=read(Path(str(stem)+'.rrrecordout'),2*1024*1024); decode_recording_output(output,raw,filter_setting=preset)
                report=strict_json(read(Path(str(stem)+'-quality.json'),512*1024).decode('utf-8'))
                require(report['recording_sha256']==raw[-32:].hex() and report['output_sha256']==output[-32:].hex(),'quality input/output mismatch')
                require(report['execution_sha256']==sha256(execution_bytes).hexdigest() and report['reference_file_sha256']==reference_hash,'quality execution/reference mismatch')
                require(report['source_identities']=={key:data[key] for key in IDENTITIES},'quality source mismatch')
                require(report['filter_setting']==preset and report['albedo_encoding']=='linear' and report['surface_reference'] is True,'quality mode mismatch')
                require(report['quality_acceptance']=='not-qualified' and report['reference_seed']==20260903,'quality/reference policy mismatch')
                require(report['raw_sdk_acceptance']==decision['context']['raw_sdk_acceptance'],'raw SDK evidence mismatch')
                for name,digest in report['implementation_sha256'].items():
                    require(name in ('rr_reference.py','rr_quality.py','rr_surface_reference.py','rr_fallback.py'),'unknown reference implementation')
                    require(sha256(Path(__file__).resolve().parents[1].joinpath('tools',name).read_bytes()).hexdigest()==digest,'reference implementation changed')
                if samples is None: samples=report['samples_per_batch']
                require(samples==report['samples_per_batch']==1024 and report['total_samples_per_hit']==2048,'sample policy mismatch')
                reports[preset]=report
            cases[label]=dict(surface=surface,input_seed=seed,recording_sha256=raw[-32:].hex(),signal_sha256=signal,
                              guide_camera_sha256=guides,reference_sha256=reference_hash,reports=reports)
    audit_seeds(cases)
    summary=dict(result='measured',quality_acceptance='not-qualified',scope='six-recording-three-preset-surface-comparison',seeds=list(SEEDS),
                 samples_per_batch=samples,cases=cases,paired_summary=paired_summary(cases),artifacts=str(folder),elapsed_seconds=None,
                 recovery='completed local per-preset evidence; corrected stochastic-distance seed audit; references not recomputed')
    with (folder/'verification.json').open('x',encoding='utf-8') as stream: json.dump(summary,stream,indent=2,allow_nan=False)
    print(json.dumps(dict(result='measured',paired_summary=summary['paired_summary'],artifacts=str(folder))))


if __name__=='__main__': main()
