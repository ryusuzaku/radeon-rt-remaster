"""Selection observations and bounded duplicate rejection sampling."""
import copy
import json
import subprocess
from inspect_position_capture import inspect,inspect_bytes

def qualify(fixture,proxy,root,clean,flags,code,pixel):
    base=dict(flags,RRT_POSITION_COMPRESSED_TEXTURES='1',RRT_POSITION_TEXTURE_UPLOADS='1',RRT_POSITION_DIRTY_TEXTURES='1')
    def run(name,selection,sampled,stress=False,case='valid'):
        path=root/(name+'.jsonl');env=dict(clean,**base,RRT_FIXTURE_PROXY=str(proxy),RRT_POSITION_CAPTURE_FILE=str(path),RRT_MATERIAL_FIXTURE_CASE=case)
        env['RRT_POSITION_SELECTION']=selection
        if stress:env['RRT_MATERIAL_SELECTION_STRESS']='1'
        if sampled:env['RRT_POSITION_SURFACE_UPLOADS']='1'
        r=subprocess.run([str(fixture),'--pixel-material'],input=code+'\n'+pixel+'\n',env=env,text=True,capture_output=True,timeout=60)
        assert r.returncode==0,(r.stdout,r.stderr)
        return path,inspect(path),json.loads(r.stdout)
    for name,selection,reason in [('extent','127x96:1','selection_target_mismatch'),('minimum','128x96:4096','selection_primitive_minimum')]:
        old,legacy,baseline=run(name+'-legacy',selection,False)
        path,report,actual=run(name,selection,True)
        assert actual==baseline
        assert report['attempts_total']==legacy['attempts_total'] and report['attempts_recorded']==4,report
        assert legacy['attempts_recorded']>4 and report['rejections']=={reason:4}
        assert path.stat().st_size<old.stat().st_size/2
        assert report['observed_rejection_targets']==[{'target':[128,96,116,0],'recorded_rejections':4}],report
        rows=[json.loads(l) for l in path.read_text().splitlines()]
        for mutation in ['zero','bool','shape','reason','policy']:
            bad=copy.deepcopy(rows);r=bad[1]
            if mutation=='zero':r['selection_observed']['target'][0]=0
            if mutation=='bool':r['selection_observed']['primitives']=True
            if mutation=='shape':r['selection_observed']['extra']=0
            if mutation=='reason':
                r['selection_observed']['target'][:2]=[127,96] if name=='extent' else [127,95]
            if mutation=='policy':bad[0]['selection_rejections']='all'
            try:inspect_bytes(('\n'.join(map(json.dumps,bad))+'\n').encode())
            except ValueError:pass
            else:raise AssertionError(mutation)
    # Matching draws retain every admitted row and the full write history contract.
    _,report,_=run('matching','128x96:1',True)
    assert len(report['captures'])==16 and report['completion']=='capture_limit',report

    # Unfiltered selection: every render-target extent is accepted, so the evidence chain runs without
    # knowing the game's resolution in advance. The exact form above stays unaffected.
    path,report,actual=run('alltargets','any:1',True)
    assert report['selection']=={'any_target':True,'min_primitives':1},report['selection']
    assert len(report['captures'])==16 and report['completion']=='capture_limit',report
    assert not report['rejections'],report
    rows=[json.loads(l) for l in path.read_text().splitlines() if json.loads(l).get('kind')=='draw']
    assert rows and all(r['target'][:2]==[128,96] for r in rows),rows[0]
    # The primitive minimum still applies without a target filter: the same rejection as the exact
    # 128x96 form, never a target mismatch, and the observed target is what the draw really used.
    minimum,minimum_report,_=run('alltargets-minimum','any:4096',True)
    assert not minimum_report['captures'] and set(minimum_report['rejections'])=={'selection_primitive_minimum'},minimum_report
    observed=[json.loads(l)['selection_observed'] for l in minimum.read_text().splitlines() if json.loads(l).get('kind')=='draw']
    assert observed and all(o['target'][:2]==[128,96] and o['primitives']<4096 for o in observed),observed[:1]
    # Unfiltered selection belongs to the bounded multi-draw window; without it the capture fails closed.
    absent=root/'alltargets-nomulti.jsonl'
    env=dict(clean,**{k:v for k,v in base.items() if k not in ('RRT_POSITION_MULTI_DRAW','RRT_POSITION_SELECTION')},RRT_FIXTURE_PROXY=str(proxy),
             RRT_POSITION_CAPTURE_FILE=str(absent),RRT_MATERIAL_FIXTURE_CASE='valid',RRT_POSITION_SELECTION='any:1')
    r=subprocess.run([str(fixture),'--pixel-material'],input=code+'\n'+pixel+'\n',env=env,text=True,capture_output=True,timeout=60)
    assert r.returncode==0,(r.stdout,r.stderr)
    assert not absent.exists()

    path,report,actual=run('stress','127x96:1',True,True)
    assert report['completion']=='attempt_limit' and report['attempts_total']==4096,report
    assert report['attempts_recorded']==67 and path.stat().st_size<1024*1024,report
    rows=[json.loads(l) for l in path.read_text().splitlines() if json.loads(l).get('kind')=='draw']
    assert [r['ordinal'] for r in rows]==sorted(set(range(4))|set(range(0,4096,64)))
    assert actual==baseline

    _,shader_report,shader_native=run('shader-stress','128x96:1',True,True,'unsupportedvs')
    assert shader_report['completion']=='attempt_limit' and shader_report['attempts_recorded']==67,shader_report
    assert shader_report['rejections']=={'unsupported_shader':67} and shader_native==baseline
    assert shader_report['evidence_failures']==[{'stage':'position_material','detail':'unsupported_shader','recorded_rejections':67}]
    for case,stage,detail in [('wrongshader','pixel_material','pixel_material_shader'),('psstateblock','pixel_material','unknown_pixel_constants'),('texalias','texture_inputs','texture_mip_uninitialized')]:
        old,legacy,expected=run(case+'-legacy','128x96:1',False,case=case)
        path,report,actual=run(case,'128x96:1',True,case=case)
        assert actual==expected and not report['captures'] and not legacy['evidence_failures']
        assert report['evidence_failures']==[{'stage':stage,'detail':detail,'recorded_rejections':report['attempts_recorded']}],report
        rows=[json.loads(l) for l in path.read_text().splitlines()]
        for change in ['stage','detail','shape','status','version']:
            bad=copy.deepcopy(rows)
            if change=='stage':bad[1]['evidence_failure']['stage']='invented'
            if change=='detail':bad[1]['evidence_failure']['detail']='x'*97
            if change=='shape':bad[1]['evidence_failure']['extra']=0
            if change=='status':bad[1]['hr']=-1
            if change=='version':
                bad[0]['version']=17;bad[0].pop('selection_rejections');bad[0].pop('shader_rejections')
            try:inspect_bytes(('\n'.join(map(json.dumps,bad))+'\n').encode())
            except ValueError:pass
            else:raise AssertionError(change)

    _,report,_=run('texture-context','128x96:1',True,case='texalias')
    assert report['texture_diagnostics'],report
    for t in report['texture_diagnostics']:
        assert t['tracked'] and t['admission']=='tracked' and t['known_bytes']==0 and t['total_bytes']>0
        assert t['last_invalidation']=='UnlockRect' and t['coverage_bytes']*4==t['total_bytes'],t
    path,report,_=run('upload-context','128x96:1',True,case='upload-rgba-dirtypartial')
    assert report['texture_diagnostics'],report
    for t in report['texture_diagnostics']:
        assert t['descriptor'][4]==0 and t['last_upload']=='source_not_fully_dirty',t
        assert t['upload_source_lock_flags']==32768 and t['coverage_bytes']*4==t['total_bytes'],t
    rows=[json.loads(l) for l in path.read_text().splitlines()]
    for key,value in [('slot',2),('known_bytes',2**30),('tracked',False),('descriptor',[0]*7),('admission','invented'),('last_upload','x'*65),('coverage_bytes',0),('upload_source_lock_flags',-1),('upload_source_invalidation','x'*65)]:
        bad=copy.deepcopy(rows);bad[1]['texture_diagnostic'][key]=value
        try:inspect_bytes(('\n'.join(map(json.dumps,bad))+'\n').encode())
        except ValueError:pass
        else:raise AssertionError(key)

    _,legacy,expected=run('dynamic-legacy','128x96:1',False,case='texdynamic')
    _,report,actual=run('dynamic-context','128x96:1',True,case='texdynamic')
    assert expected==actual and not report['captures'] and not legacy['texture_diagnostics']
    assert report['texture_diagnostics'],report
    for t in report['texture_diagnostics']:
        assert not t['tracked'] and t['admission']=='descriptor_pool_usage_extent' and t['descriptor'][3]==512 and t['descriptor'][4]==0,t

    _,report,_=run('compressed-mask','128x96:1',True,case='dxt5-alias')
    assert report['texture_diagnostics'],report
    for t in report['texture_diagnostics']:
        assert t['coverage_bytes']*16==t['total_bytes'] and t['known_bytes']==0,t

    for case,accepted in [('maskbudget',True),('maskexhaust',False),('maskrelease',True)]:
        _,report,_=run(case,'128x96:1',True,case=case)
        assert bool(report['captures'])==accepted,report
        if accepted:assert len(report['captures'])==16 and report['completion']=='capture_limit'
        else:
            assert any(t['admission']=='shadow_budget' for t in report['texture_diagnostics']),report
        # The footer attributes the shared ceiling, so a budget decision can be made from evidence.
        # Attribution appears exactly when the capture stopped itself; a fixture that exits without a
        # stop reason records no footer and must not claim any.
        retained=report.get('retained')
        if report['completion']=='partial':
            assert retained is None,report
        else:
            assert retained and {'retained','retained_buffers','retained_textures','live_textures'}<=set(retained),retained
            assert retained['retained']==retained['retained_buffers']+retained['retained_textures'],retained
            assert retained['live_textures']>0 and retained['retained_textures']>retained['retained_buffers'],{case:retained}
            # The high-water mark is what a refusal is actually measured against.
            assert retained['retained_peak']>=retained['retained'],retained
            assert retained['retained_peak']==retained['peak_buffers']+retained['peak_textures'],retained
            assert retained['peak_textures']>=retained['retained_textures'],retained

    # DEFAULT-pool destinations pay payload + mask + a fixed 128-entry surface-history charge, so the
    # 128MiB cap admits fewer of them and the refusal surfaces as texture_tracking_missing.
    _,report,_=run('defbudget','128x96:1',True,case='defbudget')
    assert len(report['captures'])==16 and report['completion']=='capture_limit',report
    assert not report['texture_diagnostics'],report
    rows=[json.loads(l) for l in (root/'defbudget.jsonl').read_text().splitlines() if json.loads(l).get('status')=='captured']
    transfers=[t for r in rows for t in r['texture_inputs'] if t['origin']=='observed_private_default_update']
    assert transfers,rows[0]
    for t in transfers:
        assert t['transfer']['operation']=='UpdateTexture' and t['transfer']['scope']=='whole_chain',t
        assert t['transfer']['dirty_proof']=='top_lock' and t['transfer']['source']!=t['id'],t

    _,report,_=run('defexhaust','128x96:1',True,case='defexhaust')
    assert not report['captures'],report
    assert report['rejections'].get('unsupported_or_missing_evidence'),report
    assert report['evidence_failures']==[{'stage':'texture_inputs','detail':'texture_tracking_missing','recorded_rejections':report['attempts_recorded']}],report
    assert report['texture_diagnostics'],report
    for t in report['texture_diagnostics']:
        assert not t['tracked'] and t['admission']=='shadow_budget',t
        assert t['descriptor'][:2]==[512,512] and t['descriptor'][4]==0,t
        assert t['total_bytes']==0 and t['known_bytes']==0,t

    _,report,_=run('defrelease','128x96:1',True,case='defrelease')
    assert len(report['captures'])==16 and report['completion']=='capture_limit',report
