"""Measure recorded RR against an independent, matched-primary CPU reference.

An analysis completing successfully does not mean its quality gates passed.
Requires NumPy. Default: constant textures/vertex colours, no material sidecar,
and zero sun radius. Explicit surface mode admits bounded textures/PBR;
optional fallback comparison uses a matched-input CPU algorithm port.
Neither the renderer nor the SDK is loaded by this tool.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import numpy as np

from inspect_rr_record import MAX_BYTES,verify_source
from scene_io import decode_scene
from rr_recorded_dispatch import admit_record,assess_recording,decode_recording_output
from rr_dispatch import read_exact,OUTPUT_BYTES,output_bytes
from rr_worker import strict_json,DLL_HASHES
from rr_reference import Reference,require

SCENE_MAX_BYTES=65536 # deliberately small fixture subset, including surface mode


def errors(raw,candidate,reference,variance,mask):
    count=int(mask.sum())
    if not count: return dict(pixels=0,raw_mse=None,rr_mse=None,reference_mean_variance=None)
    raw_mse=float(np.mean((raw[mask]-reference[mask])**2)); rr_mse=float(np.mean((candidate[mask]-reference[mask])**2))
    uncertainty=float(np.mean(variance[mask]))
    return dict(pixels=count,raw_mse=raw_mse,rr_mse=rr_mse,reference_mean_variance=uncertainty,
                rr_minus_raw_mse=rr_mse-raw_mse,reference_noise_ratio=uncertainty/raw_mse if raw_mse else None,
                reference_noise_small=uncertainty<=raw_mse*.01)


def measure(scene,data,outputs,*,samples=512,seed=20260903,progress=None,surface_reference=False,materials=None,fallback=False,_estimates=None):
    if not surface_reference: require(data['material_sha256']=='0'*64 and materials is None,'reference does not support material sidecars')
    require(len(outputs)==len(data['frames'])==data['count'],'quality frame count mismatch')
    require(type(samples) is int and samples in (64,128,256,512,1024) and data['count']*samples<=4096,'reference work bound')
    if surface_reference:
        from rr_surface_reference import SurfaceReference
        require(data['material_sha256']=='0'*64 or materials is not None,'verified materials required')
        tracer=SurfaceReference(scene,data['settings'],materials or {})
    else: tracer=Reference(scene,data['settings'])
    primary=[tracer.primary(f) for f in data['frames']]
    fallback_rows=[]; previous_fallback=None
    means=[]; variances=[]; differences=[]; mask_rows=[]; frames=[]; previous_raw=previous_rr=None
    for i,(frame,hit,rows) in enumerate(zip(data['frames'],primary,outputs)):
        if progress: progress(i,len(primary))
        if _estimates is not None and i in _estimates:
            mean,variance,difference=_estimates[i]
        else:
            mean,variance,difference=tracer.estimate(hit,samples,seed,i)
            if _estimates is not None:
                # Only the private, source-bound comparison path supplies this
                # in-memory cache. No saved or caller-provided estimates enter it.
                for value in (mean,variance,difference): value.setflags(write=False)
                _estimates[i]=(mean,variance,difference)
        raw=np.array(frame['records'])[:,:3].astype(np.float16).astype(np.float64); rr=np.array(rows)[:,:3]
        require(rr.shape==raw.shape and np.all(np.isfinite(rr)),'invalid candidate shape/values')
        masks,mapping=tracer.visibility(hit,primary[i-1] if i else hit,frame,data['frames'][i-1] if i else frame)
        report=dict(index=i,reset=frame['reset'],all=errors(raw,rr,mean,variance,hit['hit']),
                    groups={name:errors(raw,rr,mean,variance,mask) for name,mask in masks.items()},
                    batch_difference_mse=float(np.mean(difference[hit['hit']]**2)) if hit['hit'].any() else None)
        if fallback:
            from rr_fallback import spatial
            filtered=spatial(frame,raw,hit); fallback_rows.append(filtered)
            for name,mask in dict(all=hit['hit'],**masks).items():
                entry=report['all'] if name=='all' else report['groups'][name]
                metric=errors(raw,filtered,mean,variance,mask)
                entry['fallback_mse']=metric['rr_mse']
                entry['rr_minus_fallback_mse']=entry['rr_mse']-entry['fallback_mse'] if entry['pixels'] else None
                entry['reference_noise_small_vs_fallback']=entry['reference_mean_variance']<=entry['fallback_mse']*.01 if entry['pixels'] else None
        temporal=dict(pixels=0,raw_residual_mse=None,rr_residual_mse=None)
        stable=masks['stable']; ids=mapping[stable]
        if stable.any():
            raw_residual=(raw[stable]-mean[stable])-(previous_raw[ids]-means[-1][ids])
            rr_residual=(rr[stable]-mean[stable])-(previous_rr[ids]-means[-1][ids])
            raw_error=float(np.mean(raw_residual**2)); uncertainty=float(np.mean(variance[stable]+variances[-1][ids]))
            temporal=dict(pixels=int(stable.sum()),raw_residual_mse=raw_error,rr_residual_mse=float(np.mean(rr_residual**2)),
                          reference_residual_variance=uncertainty,reference_noise_small=uncertainty<=raw_error*.01)
            if fallback:
                residual=(filtered[stable]-mean[stable])-(previous_fallback[ids]-means[-1][ids])
                temporal['fallback_residual_mse']=float(np.mean(residual**2))
        report['temporal']=temporal
        frames.append(report); means.append(mean); variances.append(variance); differences.append(difference)
        mask_rows.append(np.stack([masks[k] for k in ('stable','disoccluded','offscreen','unmatched')]))
        previous_raw,previous_rr=raw,rr
        if fallback: previous_fallback=filtered
    full=[f['all'] for f in frames if f['all']['pixels']]
    dis=[f['groups']['disoccluded'] for f in frames if f['groups']['disoccluded']['pixels']]
    temporal=[f['temporal'] for f in frames if f['temporal']['pixels']]
    gates=dict(reference_noise_small=bool(full) and all(f['reference_noise_small'] for f in full),
               disocclusion_reference_noise_small=all(f['reference_noise_small'] for f in dis) if dis else None,
               spatial_non_regression=bool(full) and all(f['rr_mse']<=f['raw_mse'] for f in full),
               disocclusion_non_regression=all(f['rr_mse']<=f['raw_mse'] for f in dis) if dis else None,
               temporal_non_regression=all(f['rr_residual_mse']<=f['raw_residual_mse'] for f in temporal) if temporal else None)
    gates['temporal_reference_noise_small']=all(f['reference_noise_small'] for f in temporal) if temporal else None
    if fallback:
        gates['rr_vs_fallback_non_regression']=bool(full) and all(f['rr_mse']<=f['fallback_mse'] for f in full)
        gates['reference_noise_small_vs_fallback']=bool(full) and all(f['reference_noise_small_vs_fallback'] for f in full)
    report=dict(schema='rr-quality-1',result='measured',quality_acceptance='not-qualified',gates=gates,frames=frames,
                method='float64 triangle tracing; two independent PCG64 streams; cosine-weighted one-bounce diffuse',
                samples_per_batch=samples,total_samples_per_hit=2*samples,reference_seed=seed,numpy_version=np.__version__,
                raw_baseline='half-float packed indirect RGB',temporal_metric='nearest compatible previous pixel error residual, not motion-compensated ground truth',
                reference_convergence='estimated reference-mean variance <= 1% of raw MSE; diagnostic, not a formal confidence bound')
    report['visibility_mask_order']=['stable','disoccluded','offscreen','unmatched']
    report['surface_reference']=surface_reference
    if fallback: report['fallback']='float64 CPU port of default presentationColor spatial kernel on matched half-float indirect RGB; not GPU-equivalent legacy output'
    arrays=dict(mean=np.array(means),mean_variance=np.array(variances),batch_difference=np.array(differences),
                draw_ids=np.array([p['draw'] for p in primary]),visibility_masks=np.array(mask_rows))
    if fallback: arrays['fallback']=np.array(fallback_rows)
    return report,arrays


def _analyze(recording,output,scene_path,shader,execution,*,samples=512,seed=20260903,progress=None,surface_reference=False,materials=None,fallback=False,albedo_encoding='linear',filter_setting='none',coordinate_scale='none',guide_preset='none',_estimates=None):
    from rr_dispatch import validate_albedo_encoding
    validate_albedo_encoding(albedo_encoding)
    from rr_settings import validate_setting
    validate_setting(filter_setting)
    from rr_scale import validate_scale
    validate_scale(coordinate_scale)
    from rr_guides import validate_guide
    validate_guide(guide_preset)
    with Path(recording).open('rb') as stream: raw=stream.read(MAX_BYTES+1)
    data=admit_record(raw); verify_source(shader,data['shader_sha256'])
    if fallback:
        from rr_fallback import SHADER_SOURCE_SHA256
        reviewed=Path(__file__).resolve().parents[1]/'src/dxr/render.hlsl'
        require(sha256(reviewed.read_bytes()).hexdigest()==SHADER_SOURCE_SHA256,'fallback shader source changed; review CPU port before comparison')
    with Path(scene_path).open('rb') as stream: scene_bytes=stream.read(SCENE_MAX_BYTES+1)
    require(len(scene_bytes)<=SCENE_MAX_BYTES,'reference scene byte bound')
    scene=decode_scene(scene_bytes)
    require(scene_bytes[-32:].hex()==data['scene_sha256'],'reference scene identity mismatch')
    with Path(execution).open('rb') as stream: execution_bytes=stream.read(1024*1024+1)
    require(len(execution_bytes)<=1024*1024,'execution report oversized')
    evidence=strict_json(execution_bytes.decode('utf-8'))
    require(evidence['sdk_sha256']==DLL_HASHES and evidence['input_sha256']==raw[-32:].hex(),'execution identity/pin mismatch')
    require(evidence.get('albedo_encoding','linear')==albedo_encoding,'execution encoding mismatch')
    require(evidence.get('filter_setting','none')==filter_setting,'execution filter setting mismatch')
    require(evidence.get('coordinate_scale','none')==coordinate_scale,'execution coordinate scale mismatch')
    require(evidence.get('guide_preset','none')==guide_preset,'execution guide preset mismatch')
    decision=assess_recording(evidence['worker'],raw,albedo_encoding=albedo_encoding,query_defaults=evidence.get('query_defaults',False),filter_setting=filter_setting,coordinate_scale=coordinate_scale,guide_preset=guide_preset)
    require(decision['status']=='recording-report-ready','unverified execution report')
    candidate=read_exact(output,88+data['count']*output_bytes(data['frames'][0])); _,rows=decode_recording_output(candidate,raw,albedo_encoding=albedo_encoding,filter_setting=filter_setting,coordinate_scale=coordinate_scale,guide_preset=guide_preset)
    for frame,pixels,dispatch in zip(data['frames'],rows,decision['sequence']['frames']):
        source=np.array(frame['records']); packed=source[:,:3].astype(np.float16).astype(np.float64)
        changed=int(np.sum((source[:,23]>0)&np.any(np.array(pixels)[:,:3]!=packed,axis=1)))
        require(changed==dispatch['changed_pixels'],'candidate/execution changed-count mismatch')
    factors=None
    if surface_reference:
        from rr_surface_reference import read_materials
        factors=read_materials(materials,scene,data['material_sha256'])
    else: require(materials is None,'materials require explicit surface reference')
    if _estimates is not None:
        identity=(raw[-32:].hex(),sha256(scene_bytes).hexdigest(),samples,seed,surface_reference,fallback)
        require(_estimates.setdefault('identity',identity)==identity,'comparison source/reference identity changed')
    report,arrays=measure(scene,data,rows,samples=samples,seed=seed,progress=progress,surface_reference=surface_reference,materials=factors,fallback=fallback,_estimates=_estimates)
    report.update(recording_sha256=raw[-32:].hex(),output_sha256=candidate[-32:].hex(),execution_sha256=sha256(execution_bytes).hexdigest(),
                  implementation_sha256={name:sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in ('rr_reference.py','rr_quality.py')},
                  source_identities={k:data[k] for k in ('scene_sha256','material_sha256','shader_sha256','settings_sha256')},
                  raw_sdk_acceptance=decision['context']['raw_sdk_acceptance'])
    report['albedo_encoding']=albedo_encoding
    report['default_inspection']=decision['default_inspection']
    report['filter_setting']=filter_setting
    report['coordinate_scale']=coordinate_scale
    report['guide_preset']=guide_preset
    arrays['recording_sha256']=np.frombuffer(raw[-32:],dtype=np.uint8)
    for name,enabled in [('rr_surface_reference.py',surface_reference),('rr_fallback.py',fallback)]:
        if enabled: report['implementation_sha256'][name]=sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
    if guide_preset!='none': report['implementation_sha256']['rr_guides.py']=sha256(Path(__file__).with_name('rr_guides.py').read_bytes()).hexdigest()
    if fallback: report['fallback_shader_source_sha256']=sha256(Path(__file__).resolve().parents[1].joinpath('src/dxr/render.hlsl').read_bytes()).hexdigest()
    return report,arrays


def analyze(recording,output,scene_path,shader,execution,*,samples=512,seed=20260903,progress=None,surface_reference=False,materials=None,fallback=False,albedo_encoding='linear',filter_setting='none',coordinate_scale='none',guide_preset='none'):
    return _analyze(recording,output,scene_path,shader,execution,samples=samples,seed=seed,progress=progress,
                    surface_reference=surface_reference,materials=materials,fallback=fallback,albedo_encoding=albedo_encoding,filter_setting=filter_setting,coordinate_scale=coordinate_scale,guide_preset=guide_preset)


def analyze_comparison(recording,candidates,scene_path,shader,*,samples=1024,seed=20260903,progress=None,surface_reference=False,materials=None):
    """Three independently admitted settings; one private reference per recording.

    candidates maps the exact fixed preset names to (output, execution) paths.
    No external cache is accepted. Every source, primary guide and candidate is
    revalidated; an input changing between calls fails closed, not cache-hit.
    """
    presets=('none','stability-half','stability-zero')
    require(type(candidates) is dict and set(candidates)==set(presets),'comparison requires all three stability presets')
    estimates={}; shared=None; reports={}
    for preset in presets:
        pair=candidates[preset]
        require(type(pair) in (tuple,list) and len(pair)==2,'comparison requires output/execution pairs')
        report,arrays=_analyze(recording,*pair[:1],scene_path,shader,pair[1],samples=samples,seed=seed,progress=progress,
                              surface_reference=surface_reference,materials=materials,fallback=True,filter_setting=preset,_estimates=estimates)
        if shared is None: shared=arrays
        else:
            require(set(arrays)==set(shared) and all(np.array_equal(arrays[k],shared[k]) for k in shared),
                    'comparison reference/fallback changed')
        reports[preset]=report
    return reports,shared


def analyze_scale_comparison(recording,candidates,scene_path,shader,*,samples=512,seed=20260903,progress=None,surface_reference=False,materials=None):
    """Six scale/setting candidates with one private matched reference."""
    scales=('unit-tenth','unit-one','unit-ten'); settings=('none','stability-zero')
    expected={(scale,setting) for scale in scales for setting in settings}
    require(type(candidates) is dict and set(candidates)==expected,'scale comparison requires the fixed six candidates')
    estimates={}; shared=None; reports={}
    for scale in scales:
        reports[scale]={}
        for setting in settings:
            pair=candidates[(scale,setting)]
            require(type(pair) in (tuple,list) and len(pair)==2,'scale comparison requires output/execution pairs')
            report,arrays=_analyze(recording,pair[0],scene_path,shader,pair[1],samples=samples,seed=seed,progress=progress,
                                   surface_reference=surface_reference,materials=materials,fallback=True,
                                   filter_setting=setting,coordinate_scale=scale,_estimates=estimates)
            if shared is None: shared=arrays
            else: require(set(arrays)==set(shared) and all(np.array_equal(arrays[k],shared[k]) for k in shared),
                                 'scale comparison reference/fallback changed')
            reports[scale][setting]=report
    return reports,shared


def analyze_setting_pair(recording,candidates,scene_path,shader,*,samples=256,seed=20260903,progress=None,surface_reference=False,materials=None,coordinate_scale='unit-one'):
    """Default/zero candidates with one private same-recording reference."""
    presets=('none','stability-zero')
    require(type(candidates) is dict and set(candidates)==set(presets),'setting pair requires default and zero')
    estimates={}; shared=None; reports={}
    for preset in presets:
        pair=candidates[preset]
        require(type(pair) in (tuple,list) and len(pair)==2,'setting pair requires output/execution pairs')
        report,arrays=_analyze(recording,pair[0],scene_path,shader,pair[1],samples=samples,seed=seed,progress=progress,
                               surface_reference=surface_reference,materials=materials,fallback=True,
                               filter_setting=preset,coordinate_scale=coordinate_scale,_estimates=estimates)
        if shared is None: shared=arrays
        else: require(set(arrays)==set(shared) and all(np.array_equal(arrays[k],shared[k]) for k in shared),
                              'setting-pair reference/fallback changed')
        reports[preset]=report
    return reports,shared


def analyze_guide_comparison(recording,candidates,scene_path,shader,*,samples=512,seed=20260904,progress=None,surface_reference=True,materials=None):
    """Five fixed guide/range candidates with one private matched reference."""
    definitions={
        'baseline':('none','none'),
        'material-draw':('material-draw','none'),
        'normal-half':('none','normal-half'),
        'material-normal-half':('material-draw','normal-half'),
        'max-radiance-one':('none','max-radiance-one')}
    require(type(candidates) is dict and set(candidates)==set(definitions),'guide comparison requires fixed five candidates')
    estimates={}; shared=None; reports={}
    for label,(guide,setting) in definitions.items():
        pair=candidates[label]
        require(type(pair) in (tuple,list) and len(pair)==2,'guide comparison requires output/execution pairs')
        report,arrays=_analyze(recording,pair[0],scene_path,shader,pair[1],samples=samples,seed=seed,progress=progress,
                               surface_reference=surface_reference,materials=materials,fallback=True,
                               filter_setting=setting,coordinate_scale='unit-one',guide_preset=guide,_estimates=estimates)
        if shared is None: shared=arrays
        else: require(set(arrays)==set(shared) and all(np.array_equal(arrays[k],shared[k]) for k in shared),
                              'guide comparison reference/fallback changed')
        reports[label]=report
    return reports,shared


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('recording','output','scene','shader','execution','report','reference'): parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--samples',type=int,default=512); parser.add_argument('--seed',type=int,default=20260903)
    parser.add_argument('--surface-reference',action='store_true',help='admit bounded textures, vertex colour and PBR sidecars')
    parser.add_argument('--materials',type=Path)
    parser.add_argument('--albedo-encoding',choices=('linear','sqrt'),default='linear')
    from rr_settings import PRESETS
    parser.add_argument('--filter-setting',choices=PRESETS,default='none')
    from rr_scale import PRESETS as SCALE_PRESETS
    parser.add_argument('--coordinate-scale',choices=SCALE_PRESETS,default='none')
    from rr_guides import PRESETS as GUIDE_PRESETS
    parser.add_argument('--guide-preset',choices=GUIDE_PRESETS,default='none')
    parser.add_argument('--fallback',action='store_true',help='compare the matched-input CPU port of the default spatial algorithm')
    parser.add_argument('--require-gates',action='store_true',help='exit 2 after saving evidence unless every narrow diagnostic gate is true; not general quality acceptance')
    args=parser.parse_args()
    try:
        destinations=[args.report.resolve(),args.reference.resolve()]
        require(destinations[0]!=destinations[1] and all(not p.exists() and p.parent.is_dir() for p in destinations),'report/reference require distinct new paths')
        report,arrays=analyze(args.recording,args.output,args.scene,args.shader,args.execution,samples=args.samples,seed=args.seed,
                              surface_reference=args.surface_reference,materials=args.materials,fallback=args.fallback,albedo_encoding=args.albedo_encoding,filter_setting=args.filter_setting,coordinate_scale=args.coordinate_scale,
                              guide_preset=args.guide_preset,progress=lambda i,n:print(f'Reference frame {i+1}/{n}',flush=True))
        with args.reference.open('xb') as stream: np.savez_compressed(stream,**arrays)
        report['reference_file_sha256']=sha256(args.reference.read_bytes()).hexdigest()
        with args.report.open('x',encoding='utf-8') as stream: json.dump(report,stream,indent=2,allow_nan=False); stream.write('\n')
        print(json.dumps(dict(result='measured',quality_acceptance=report['quality_acceptance'],gates=report['gates'])))
        return 2 if args.require_gates and not all(value is True for value in report['gates'].values()) else 0
    except (OSError,ValueError,KeyError,TypeError,OverflowError) as error:
        print(json.dumps(dict(result='unavailable',reason=str(error)))); return 1


if __name__=='__main__': raise SystemExit(main())
