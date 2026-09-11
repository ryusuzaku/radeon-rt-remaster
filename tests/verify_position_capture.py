"""Proxy-backed position evidence plus inventory in one native fixture session."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import struct
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from inspect_shader_inventory import inspect as inventory
from inspect_position_capture import inspect,DIGEST
from capture_position_scene import Capture
from position_scene import Scene
p=argparse.ArgumentParser();p.add_argument('--fixture',type=Path,required=True);p.add_argument('--proxy',type=Path,required=True);p.add_argument('--inventory',type=Path,required=True);a=p.parse_args()
inventory(a.inventory);code=None
with a.inventory.open(encoding='utf-8') as stream:
    for _ in range(4098):
        line=stream.readline(70001)
        if not line:break
        assert len(line)<=70000
        row=json.loads(line);candidate=row.get('vs')
        if isinstance(candidate,str) and len(candidate)==1224 and hashlib.sha256(bytes.fromhex(candidate)).hexdigest()==DIGEST:code=candidate;break
assert code
# Audit generated inherited wrappers as well as native examples: a newly omitted
# writer must not silently disappear from the process-wide history.
generated=(Path(__file__).resolve().parents[1]/'src/proxy/generated_observers.inc').read_text()
for interface,methods in {
    'IDirect3DDevice9':['DrawPrimitive','DrawIndexedPrimitive','DrawPrimitiveUP','DrawIndexedPrimitiveUP','DrawRectPatch','DrawTriPatch','Clear','UpdateSurface','UpdateTexture','StretchRect','ColorFill','GetRenderTargetData','GetFrontBufferData','Reset','SetRenderTarget','SetDepthStencilSurface','Present'],
    'IDirect3DDevice9Ex':['DrawIndexedPrimitive','ComposeRects','ResetEx','PresentEx'],
    'IDirect3DSurface9':['LockRect','UnlockRect','GetDC','ReleaseDC'],
    'IDirect3DBaseTexture9':['GenerateMipSubLevels'],
    'IDirect3DTexture9':['LockRect','UnlockRect','GenerateMipSubLevels','AddDirtyRect'],
    'IDirect3DCubeTexture9':['LockRect','UnlockRect','GenerateMipSubLevels','AddDirtyRect'],
    'IDirect3DVolumeTexture9':['LockBox','UnlockBox','GenerateMipSubLevels','AddDirtyBox'],
    'IDirect3DVolume9':['LockBox','UnlockBox'],
    'IDirect3DStateBlock9':['Apply'],
    'IDirect3DSwapChain9':['Present'],
    'IDirect3DSwapChain9Ex':['Present'],
}.items():
    wrapper=generated.split('class '+interface+'Observer final',1)[1].split('\n};',1)[0]
    for method in methods:
        body=wrapper.split('STDMETHODCALLTYPE '+method+'(',1)[1].split('\n    }',1)[0]
        assert body.index('BeforeWriter(')<body.index('inner_->'+method+'(')<body.index('AfterWriter(')
        if 'return result;' in body:assert body.index('AfterWriter(')<body.index('return result;')
        if method=='DrawIndexedPrimitive':assert body.index('AfterWriter(')<body.index('shader::hook::Commit(')
for interface,methods in [('IDirect3DDevice9',['CreateRenderTarget']),('IDirect3DDevice9Ex',['CreateRenderTarget','CreateRenderTargetEx'])]:
    wrapper=generated.split('class '+interface+'Observer final',1)[1].split('\n};',1)[0]
    for method in methods:
        body=wrapper.split('STDMETHODCALLTYPE '+method+'(',1)[1].split('\n    }',1)[0]
        assert body.index('inner_->'+method+'(')<body.index('shader::hook::CreatedTarget(')<body.index('WrapReturned(')
        assert 'if(SUCCEEDED(result) && ppSurface && *ppSurface)' in body and 'pSharedHandle==nullptr' in body and 'Lockable!=FALSE' in body
        if method=='CreateRenderTargetEx':assert 'Usage==0' in body
root=Path(tempfile.mkdtemp(prefix='position-capture-',dir=a.fixture.parent))
for interface in ('IDirect3DDevice9','IDirect3DDevice9Ex'):
    wrapper=generated.split('class '+interface+'Observer final',1)[1].split('\n};',1)[0]
    for method in ('SetRenderState','SetPixelShader','SetPixelShaderConstantF','SetVertexShader','SetViewport','SetNPatchMode','SetStreamSource','SetIndices'):
        body=wrapper.split('STDMETHODCALLTYPE '+method+'(',1)[1].split('\n    }',1)[0]
        assert body.index('BeforeColorState(')<body.index('inner_->'+method+'(')<body.index('AfterColorState(')
clean={k:v for k,v in os.environ.items() if not k.upper().startswith('RRT_')}
for interface in ('IDirect3DDevice9','IDirect3DDevice9Ex'):
    wrapper=generated.split('class '+interface+'Observer final',1)[1].split('\n};',1)[0]
    body=wrapper.split('STDMETHODCALLTYPE SetPixelShaderConstantF(',1)[1].split('\n    }',1)[0]
    assert body.index('inner_->SetPixelShaderConstantF(')<body.index('shader::hook::PixelConstants(id,StartRegister,Vector4fCount,result)')
for interface in ('IDirect3DBaseTexture9','IDirect3DTexture9','IDirect3DCubeTexture9','IDirect3DVolumeTexture9'):
    wrapper=generated.split('class '+interface+'Observer final',1)[1].split('\n};',1)[0]
    for method in ('SetLOD','SetAutoGenFilterType'):
        body=wrapper.split('STDMETHODCALLTYPE '+method+'(',1)[1].split('\n    }',1)[0]
        assert body.index('BeforeColorState(')<body.index('inner_->'+method+'(')<body.index('AfterColorState(')
texture_wrapper=generated.split('class IDirect3DTexture9Observer final',1)[1].split('\n};',1)[0]
body=texture_wrapper.split('STDMETHODCALLTYPE AddDirtyRect(',1)[1].split('\n    }',1)[0]
assert body.index('BeforeWriter(')<body.index('inner_->AddDirtyRect(')<body.index('TextureDirty(')<body.index('AfterWriter(')
body=texture_wrapper.split('STDMETHODCALLTYPE UnlockRect(',1)[1].split('\n    }',1)[0]
assert body.index('TextureBeforeUnlock(')<body.index('inner_->UnlockRect(')<body.index('TextureAfterUnlock(inner_,Level,result)')
body=texture_wrapper.split('STDMETHODCALLTYPE LockRect(',1)[1].split('\n    }',1)[0]
assert body.index('inner_->LockRect(')<body.index('TextureLock(inner_,Level,pLockedRect,pRect,Flags,result)')
for interface in ('IDirect3DDevice9','IDirect3DDevice9Ex'):
    wrapper=generated.split('class '+interface+'Observer final',1)[1].split('\n};',1)[0]
    body=wrapper.split('STDMETHODCALLTYPE CreateTexture(',1)[1].split('\n    }',1)[0]
    assert body.index('inner_->CreateTexture(')<body.index('TextureCreated(*ppTexture,pSharedHandle==nullptr)')<body.index('WrapReturned(')
    body=wrapper.split('STDMETHODCALLTYPE UpdateTexture(',1)[1].split('\n    }',1)[0]
    assert body.index('BeforeWriter(')<body.index('BeforeTextureUpload(')<body.index('inner_->UpdateTexture(')<body.index('AfterTextureUpload(')<body.index('AfterWriter(')
    body=wrapper.split('STDMETHODCALLTYPE UpdateSurface(',1)[1].split('\n    }',1)[0]
    assert body.index('BeforeWriter(')<body.index('BeforeSurfaceUpload(')<body.index('inner_->UpdateSurface(')<body.index('AfterSurfaceUpload(')<body.index('AfterWriter(')
    for method in (('Reset','ResetEx') if interface.endswith('Ex') else ('Reset',)):
        body=wrapper.split('STDMETHODCALLTYPE '+method+'(',1)[1].split('\n    }',1)[0]
        assert body.index('inner_->'+method+'(')<body.index('TextureReset(result)')
def run(name,extra=None):
    capture=root/f'{name}.jsonl';ledger=root/f'{name}-inventory.jsonl'
    env=dict(clean,RRT_FIXTURE_PROXY=str(a.proxy),RRT_POSITION_CAPTURE_FILE=str(capture),RRT_SHADER_INVENTORY_FILE=str(ledger))
    env.update({k:str(v) for k,v in (extra or {}).items()})
    r=subprocess.run([str(a.fixture),'--hl2-position'],input=code+'\n',env=env,capture_output=True,text=True,timeout=60)
    assert r.returncode==0,(name,r.stdout,r.stderr,root)
    assert 'max_normalized_error=0 ' in r.stdout
    return capture,ledger
capture,ledger=run('combined');report=inspect(capture)
assert report['completion']=='capture_limit' and len(report['captures'])==4 and all(x['corners']==3 for x in report['captures']),report
assert inventory(ledger)['draws']==48 and inventory(ledger)['failed_draws']==0
assert report['version']==2 and report['resource_provenance']
fresh=inspect(capture,include_records=True)['records']
assert len({r['provenance']['vb_id'] for r in fresh})==4
assert len({r['provenance']['ib_id'] for r in fresh})==4
reused,_=run('reuse',{'RRT_POSITION_FIXTURE_CASE':'reuse'})
records=inspect(reused,include_records=True)['records'];assert len(records)==4
for kind in ('vb','ib'):
    assert len({r['provenance'][kind+'_id'] for r in records})==1
    revisions=[r['provenance'][kind+'_revision'] for r in records]
    assert revisions==sorted(set(revisions)) and len(revisions)==4
assert all(r['provenance']['reset_epoch']==0 for r in records)
sessions=set()
for case in ('frames','swapframes','presentlimit','resetframes'):
    source,_=run(case,{'RRT_POSITION_FRAME_SAMPLING':'1','RRT_POSITION_FIXTURE_CASE':case})
    sampled=inspect(source,include_records=True)
    assert sampled['version']==3 and sampled['frame_sampling'] and sampled['session'] not in sessions
    sessions.add(sampled['session'])
    assert sampled['completion']==('present_limit' if case=='presentlimit' else 'capture_limit'),sampled
    accepted=sampled['records']
    assert [r['timing']['present_interval'] for r in accepted]==([0,1,0,1] if case=='resetframes' else list(range(1 if case=='presentlimit' else 4)))
    assert all(r['timing']['indexed_draw']==0 for r in accepted)
    assert [r['timing']['reset_epoch'] for r in accepted]==([0,0,1,1] if case=='resetframes' else [0]*len(accepted))
    imported=Capture(source).report()
    assert imported['capture_session']==sampled['session']
    assert [r['timing'] for r in imported['candidates']]==[r['timing'] for r in accepted]
    # The fixture supplies correspondence explicitly; the adapter does not infer it.
    temporal=Scene();bundle=Capture(source)
    for sequence,row in enumerate(accepted):
        delta=bundle.apply(temporal,0,sequence,bundle.digest,{row['ordinal']:'explicit-fixture-instance'})
        assert delta['scene_delta']['instances']==1
        assert delta['scene_delta']['new_assets']==(1 if sequence==0 else 0)
        assert temporal.snapshot()['instances']['explicit-fixture-instance'].constants==struct.unpack('<32f',bytes.fromhex(row['constants']))
    if case=='frames':
        from reconstruct_positions import reconstruct
        rebuilt=reconstruct(source,root/'frame-reconstruction')
        assert len(rebuilt['render_groups'])==4
        assert [r['timing'] for r in rebuilt['draws']]==[r['timing'] for r in accepted]
        frame_rows=[json.loads(line) for line in source.read_text().splitlines()]
        import copy
        for mutation in ('session','timing','epoch','duplicate','present_count'):
            changed=copy.deepcopy(frame_rows)
            draws=[r for r in changed if r.get('status')=='captured']
            if mutation=='session':changed[0]['session']='invalid'
            if mutation=='timing':draws[0]['timing']['indexed_draw']=-1
            if mutation=='epoch':draws[0]['timing']['reset_epoch']=1
            if mutation=='duplicate':draws[1]['timing']=dict(draws[0]['timing'])
            if mutation=='present_count':changed[-1].update(reason='present_limit',presents=3)
            bad=root/f'bad-frame-{mutation}.jsonl';bad.write_text(''.join(json.dumps(r)+'\n' for r in changed))
            try:inspect(bad)
            except ValueError:pass
            else:raise AssertionError(('invalid timing accepted',mutation))
source,_=run('no-presents',{'RRT_POSITION_FRAME_SAMPLING':'1'})
assert len(inspect(source)['captures'])==1 and inspect(source)['completion']=='partial'
source,_=run('invalid-frame-mode',{'RRT_POSITION_FRAME_SAMPLING':'2'})
assert not source.exists()
source,_=run('selected',{'RRT_POSITION_FRAME_SAMPLING':'1','RRT_POSITION_SELECTION':'128x96:1','RRT_POSITION_FIXTURE_CASE':'selectedframes'})
selected=inspect(source,include_records=True)
assert selected['version']==4 and selected['completion']=='capture_limit'
assert selected['selection']=={'target_width':128,'target_height':96,'min_primitives':1}
assert selected['rejections']=={'selection_target_mismatch':4}
assert [r['timing']['present_interval'] for r in selected['records']]==[0,1,2,3]
assert all(r['timing']['indexed_draw']==1 and r['target'][:2]==[128,96] for r in selected['records'])
assert Capture(source).report()['selection']==selected['selection']
selected_rows=[json.loads(line) for line in source.read_text().splitlines()]
for field,value in [('target_width',127),('target_height',95),('min_primitives',2),('target_width',0),('min_primitives',True)]:
    changed=copy.deepcopy(selected_rows);changed[0]['selection'][field]=value
    bad=root/f'bad-selection-{field}-{value}.jsonl';bad.write_text(''.join(json.dumps(r)+'\n' for r in changed))
    try:inspect(bad)
    except ValueError:pass
    else:raise AssertionError('selection violation admitted')
for name,policy,reason in [('wrong-target','127x96:1','selection_target_mismatch'),('too-small','128x96:2','selection_primitive_minimum')]:
    source,_=run(name,{'RRT_POSITION_FRAME_SAMPLING':'1','RRT_POSITION_SELECTION':policy,'RRT_POSITION_FIXTURE_CASE':'presentlimit'})
    rejected=inspect(source)
    assert rejected['completion']=='present_limit' and not rejected['captures'] and rejected['rejections']=={reason:2}
for i,policy in enumerate(('0x96:1','128x0:1','128x96:0','16385x96:1','128x96:4097','128x96','0128x96:1','128x96:1junk','9'*33)):
    source,_=run(f'invalid-selection-{i}',{'RRT_POSITION_FRAME_SAMPLING':'1','RRT_POSITION_SELECTION':policy})
    assert not source.exists()
source,_=run('selection-no-frames',{'RRT_POSITION_SELECTION':'128x96:1'})
assert not source.exists()
for case in ('multiframes','multinopresent','multipresentlimit'):
    source,_=run(case,{'RRT_POSITION_FRAME_SAMPLING':'1','RRT_POSITION_SELECTION':'128x96:1','RRT_POSITION_MULTI_DRAW':'1','RRT_POSITION_FIXTURE_CASE':case})
    multi=inspect(source,include_records=True);assert multi['version']==5 and multi['limits']=={'per_interval':4,'total':16}
    assert len(multi['records'])==(16 if case=='multiframes' else 4)
    assert multi['completion']=={'multiframes':'capture_limit','multinopresent':'partial','multipresentlimit':'present_limit'}[case]
    assert multi['rejections']['native_draw_failed']==(4 if case=='multiframes' else 1)
    assert [r['timing']['present_interval'] for r in multi['records']]==[i//4 for i in range(len(multi['records']))]
    assert [r['timing']['indexed_draw'] for r in multi['records']]==[0,2,3,4]*(4 if case=='multiframes' else 1)
    if case!='multinopresent':
        bundle=Capture(source);scene=Scene();mapping={c.ordinal:f'explicit-{c.ordinal}' for c in bundle.candidates}
        assert bundle.report()['coverage']=={'submitted_draws':len(mapping),'position_content_count':1,'submitted_triangles':len(mapping)}
        assert bundle.apply(scene,0,0,bundle.digest,mapping)['scene_delta']['instances']==len(mapping)
        rebuilt=reconstruct(source,root/(case+'-reconstructed'))
        assert len(rebuilt['draws'])==len(mapping)
    if case=='multipresentlimit':
        from verify_recorded_positions import verify
        replay=verify(source,a.fixture)
        assert len(replay['draws'])==4 and all(r['status']=='matched' for r in replay['draws'])
    if case=='multiframes':
        rows_multi=[json.loads(line) for line in source.read_text().splitlines()]
        for mutation in ('quota','duplicate','limits','early'):
            changed=copy.deepcopy(rows_multi);accepted=[r for r in changed if r.get('status')=='captured']
            if mutation=='quota':accepted[4]['timing'].update(present_interval=0,indexed_draw=100)
            if mutation=='duplicate':accepted[1]['timing']=dict(accepted[0]['timing'])
            if mutation=='limits':changed[0]['limits']['total']=17
            if mutation=='early':changed=[r for r in changed if r not in accepted[4:]];changed[-1]['captured']=4
            bad=root/f'bad-multi-{mutation}.jsonl';bad.write_text(''.join(json.dumps(r)+'\n' for r in changed))
            try:inspect(bad)
            except ValueError:pass
            else:raise AssertionError(('invalid multi capture admitted',mutation))
for name,env in [('multi-no-selection',{'RRT_POSITION_FRAME_SAMPLING':'1','RRT_POSITION_MULTI_DRAW':'1'}),('multi-invalid',{'RRT_POSITION_FRAME_SAMPLING':'1','RRT_POSITION_SELECTION':'128x96:1','RRT_POSITION_MULTI_DRAW':'2'})]:
    source,_=run(name,env);assert not source.exists()
for case in ('multiframes','composition'):
    source,_=run('state-'+case,{'RRT_POSITION_FRAME_SAMPLING':'1','RRT_POSITION_SELECTION':'128x96:1','RRT_POSITION_MULTI_DRAW':'1','RRT_POSITION_RENDER_STATE':'1','RRT_POSITION_FIXTURE_CASE':case})
    evidence=inspect(source,include_records=True);assert evidence['version']==6 and len(evidence['records'])==16
    rows_state=evidence['records'];states=[r['render_state'] for r in rows_state]
    assert all(s['depth_id']==0 and s['depth_desc'] is None and s['states']['z_enable']==0 and s['states']['blend_enable']==0 for s in states)
    assert [r['render_state'] for r in Capture(source).report()['candidates']]==states
    from replay_position_groups import groups
    if case=='multiframes':
        assert len({s['target_id'] for s in states})==1
        assert len(groups(source)[2])==4
        assert all(len({s['clear_serial'] for s in states[i:i+4]})==1 for i in range(0,16,4))
        assert len({s['clear_serial'] for s in states})==4
    else:
        assert len({s['target_id'] for s in states})==13
        assert [s['states']['alpha_ref'] for s in states]==[0,1,2,3]*4
        assert len(groups(source)[2])==16
        assert all(len({s['clear_serial'] for s in states[i:i+4]})==4 for i in range(0,16,4))
        assert all(len({s['binding_serial'] for s in states[i:i+4]})==4 for i in range(0,16,4))
    state_rows=[json.loads(line) for line in source.read_text().splitlines()]
    for mutation in ('missing','id','depth','states','rect','serial','legacy'):
        changed=copy.deepcopy(state_rows);r=next(r for r in changed if r.get('status')=='captured');s=r['render_state']
        if mutation=='missing':del r['render_state']
        if mutation=='id':s['target_id']=0
        if mutation=='depth':s['depth_id']=1
        if mutation=='states':s['states']['z_enable']=True
        if mutation=='rect':s['scissor']=[0]
        if mutation=='serial':s['clear_serial']=-1
        if mutation=='legacy':changed[0]['version']=5
        bad=root/f'bad-state-{case}-{mutation}.jsonl';bad.write_text(''.join(json.dumps(r)+'\n' for r in changed))
        try:inspect(bad)
        except ValueError:pass
        else:raise AssertionError(('bad render state admitted',mutation))
for name,env in [('state-no-multi',{'RRT_POSITION_RENDER_STATE':'1'}),('state-invalid',{'RRT_POSITION_FRAME_SAMPLING':'1','RRT_POSITION_SELECTION':'128x96:1','RRT_POSITION_MULTI_DRAW':'1','RRT_POSITION_RENDER_STATE':'2'})]:
    source,_=run(name,env);assert not source.exists()
source,_=run('depth-state',{'RRT_POSITION_FRAME_SAMPLING':'1','RRT_POSITION_SELECTION':'128x96:1','RRT_POSITION_MULTI_DRAW':'1','RRT_POSITION_RENDER_STATE':'1','RRT_POSITION_FIXTURE_CASE':'depthstate'})
depth_records=inspect(source,include_records=True)['records'];assert len(depth_records)==16
depth_states=[r['render_state'] for r in depth_records]
assert len({s['depth_id'] for s in depth_states})==1 and depth_states[0]['depth_id']>0
assert all(s['depth_desc']==[128,96,75,0] and s['states']['blend_enable']==1 and s['states']['src_blend']==2 and s['states']['dst_blend']==1 for s in depth_states)
from position_initial_contents import assess
for case in ('multiframes','clearpartial','clearoversized','clearfailed','cleardepth'):
    source,_=run('clear-'+case,{'RRT_POSITION_FRAME_SAMPLING':'1','RRT_POSITION_SELECTION':'128x96:1','RRT_POSITION_MULTI_DRAW':'1','RRT_POSITION_RENDER_STATE':'1','RRT_POSITION_CLEAR_EVIDENCE':'1','RRT_POSITION_FIXTURE_CASE':case})
    inspected=inspect(source,include_records=True);assert inspected['version']==7 and len(inspected['records'])==16
    accepted=inspected['records']
    assert [c['render_state'] for c in Capture(source).report()['candidates']]==[r['render_state'] for r in accepted]
    for r in accepted:
        clear=r['render_state']['last_clear'];admission=assess(r)
        assert not admission['ready_for_stateful_replay'] and admission['initial_contents']=='unknown'
        if case=='clearoversized':assert clear is None and admission['reasons']==['clear_evidence_unavailable'];continue
        assert clear['target_id']==r['render_state']['target_id'] and clear['serial']==r['render_state']['clear_serial']
        assert clear['flags']==(7 if case=='cleardepth' else 1) and clear['color']==0
        assert clear['rects']==([[0,0,8,8]] if case=='clearpartial' else [])
        assert admission['full_target_clear_candidate']==(case!='clearpartial')
        if case=='cleardepth':assert clear['depth_bits']==struct.unpack('<I',struct.pack('<f',.375))[0] and clear['stencil']==7 and admission['depth_clear_candidate'] and admission['stencil_clear_candidate']
    if case=='multiframes':
        rows_clear=[json.loads(line) for line in source.read_text().splitlines()]
        for mutation in ('serial','rects','flags','viewport','missing','future'):
            changed=copy.deepcopy(rows_clear);r=next(r for r in changed if r.get('status')=='captured');clear=r['render_state']['last_clear']
            if mutation=='serial':clear['serial']+=1
            if mutation=='rects':clear['rects']=[[0,0,1,1]]*17
            if mutation=='flags':clear['flags']=True
            if mutation=='viewport':clear['viewport']='00'
            if mutation=='missing':del r['render_state']['last_clear']
            if mutation=='future':clear['reset_epoch']=r['timing']['reset_epoch']+1
            bad=root/f'bad-clear-{mutation}.jsonl';bad.write_text(''.join(json.dumps(r)+'\n' for r in changed))
            try:inspect(bad)
            except ValueError:pass
            else:raise AssertionError(('bad clear admitted',mutation))
        for mutation,reason in [('target','clear_targets_other_surface'),('reset','clear_from_older_reset'),('viewport','full_surface_clear_not_established')]:
            r=copy.deepcopy(accepted[0])
            if mutation=='target':r['render_state']['target_id']+=10000
            if mutation=='reset':r['timing']['reset_epoch']+=1
            if mutation=='viewport':r['render_state']['last_clear']['viewport']=struct.pack('<4I2f',0,0,64,48,0,1).hex()
            assert reason in assess(r)['reasons'] and not assess(r)['ready_for_stateful_replay']
source,_=run('clear-no-state',{'RRT_POSITION_CLEAR_EVIDENCE':'1'});assert not source.exists()
# v8 retains successful writers excluded by shader/primitive/interval selection,
# failures and explicit lookback exhaustion. Every native raster oracle stays exact.
from position_write_evidence import assess_writes
write_env=dict(RRT_POSITION_FRAME_SAMPLING='1',RRT_POSITION_SELECTION='128x96:1',RRT_POSITION_MULTI_DRAW='1',RRT_POSITION_RENDER_STATE='1',RRT_POSITION_CLEAR_EVIDENCE='1',RRT_POSITION_WRITE_EVIDENCE='1')
for case,operation in [('multiframes',None),('writefailed',None),('writenonindexed','DrawPrimitive'),('writeup','DrawPrimitiveUP'),('writeindexedup','DrawIndexedPrimitiveUP'),('writerejected','DrawIndexedPrimitive'),('writefill','ColorFill'),('writelock','LockRect'),('writecopy','GetRenderTargetData'),('writebinding','SetRenderTarget'),('writeoverflow','ColorFill'),('resetframes',None),('composition',None)]:
    source,_=run('writes-'+case,dict(write_env,RRT_POSITION_FIXTURE_CASE=case))
    report=inspect(source,include_records=True);assert report['version']==8 and len(report['records'])==16
    accepted=report['records'];all_rows=[json.loads(line) for line in source.read_text().splitlines()]
    assert [c['write_evidence'] for c in Capture(source).report()['candidates']]==[r['write_evidence'] for r in accepted]
    for r in accepted:
        evidence=r['write_evidence'];coverage=assess_writes(r)
        assert evidence['events'][-1]['captured_ordinal']==r['ordinal']
        assert not coverage['complete_surface_write_coverage'] and not assess(r)['ready_for_stateful_replay']
        assert 'unobserved_external_alias_or_mrt_writes' in coverage['reasons']
        if operation:
            assert any(e['operation']==operation and e['hr']>=0 and e['captured_ordinal']==-1 for e in evidence['events'])
            assert coverage['observed_segment']==('unavailable' if case=='writeoverflow' else 'gapped')
        else: assert coverage['observed_segment']=='captured_draws_only'
        if case=='writeoverflow':assert 'history_prefix_overflow' in coverage['reasons'] and 'clear_anchor_not_in_history' in coverage['reasons']
        if case=='writefailed':assert any(e['operation']=='ColorFill' and e['hr']<0 for e in evidence['events'])
    if case=='multiframes':
        assert assess_writes(accepted[3])['intervening_captured_ordinals']==[r['ordinal'] for r in accepted[:3]]
        # A draw beyond the per-interval quota still exists in the next snapshot.
        assert any(e['operation']=='DrawIndexedPrimitive' and e['hr']>=0 and e['captured_ordinal']==-1 for e in accepted[4]['write_evidence']['events'])
        for mutation in ('missing','unobserved','sequence','overflow','outcome','reference','endpoint','operation','oversized','legacy','history'):
            changed=copy.deepcopy(all_rows);r=next(r for r in changed if r.get('status')=='captured');w=r['write_evidence']
            if mutation=='missing':del r['write_evidence']
            if mutation=='unobserved':w['unobserved']=False
            if mutation=='sequence':w['events'][0]['serial']+=1
            if mutation=='overflow':w['dropped_through']+=1
            if mutation=='outcome':w['events'][0]['hr']=True
            if mutation=='reference':w['events'][0]['captured_ordinal']=4095
            if mutation=='endpoint':w['events'][-1]['target_id']+=1
            if mutation=='operation':w['events'][0]['operation']='InvisibleWrite'
            if mutation=='oversized':w['events']*=65
            if mutation=='legacy':changed[0]['version']=7
            if mutation=='history':
                later=[r for r in changed if r.get('status')=='captured'][1]
                later['write_evidence']['events'][0]['hr']=-1
            bad=root/f'bad-write-{mutation}.jsonl';bad.write_text(''.join(json.dumps(r)+'\n' for r in changed))
            try:inspect(bad)
            except ValueError:pass
            else:raise AssertionError(('bad write evidence admitted',mutation))
        for gap in ('observer_gap','overlap'):
            changed=copy.deepcopy(accepted[0]);changed['write_evidence'][gap]=True
            assert assess_writes(changed)['observed_segment']=='gapped'
    if case=='resetframes':assert {r['timing']['reset_epoch'] for r in accepted}=={0,1}
source,_=run('write-no-clear',{'RRT_POSITION_WRITE_EVIDENCE':'1'});assert not source.exists()
from position_surface_scope import assess_scope
scope_env=dict(write_env,RRT_POSITION_SURFACE_SCOPE='1')
for case,qualified in [('multiframes',True),('scopeclosedaccess',True),('scopefailedaccess',True),('resetframes',True),('composition',True),('scopetexture',False),('scopemrt',False),('scopelockable',False),('scopeaccess',False),('scopeaccessoverflow',False),('depthstate',False),('writefill',False),('writeoverflow',False),('clearpartial',False),('clearoversized',False),('clearfailed',True)]:
    source,_=run('scope-'+case,dict(scope_env,RRT_POSITION_FIXTURE_CASE=case))
    report=inspect(source,include_records=True);assert report['version']==9 and len(report['records'])==16,(case,report)
    records_scope=report['records']
    assert [c['surface_scope'] for c in Capture(source).report()['candidates']]==[r['surface_scope'] for r in records_scope]
    for r in records_scope:
        coverage=assess_scope(r)
        assert coverage['qualified']==coverage['complete_color_write_call_coverage']==qualified,(case,coverage,r['surface_scope'])
        assert not coverage['ready_for_stateful_replay'] and not assess(r)['ready_for_stateful_replay']
        assert assess(r)['color_scope']==coverage
        scope=r['surface_scope']
        if case=='scopeaccess':assert scope['clear']['open_accesses']==scope['draw']['open_accesses']==1
        if case=='scopeaccessoverflow':assert scope['clear']['access_gap'] and scope['draw']['access_gap'] and scope['draw']['open_accesses']==0
        if case=='scopetexture':assert not scope['draw']['origin']['observed']
        if case=='scopemrt':assert scope['draw']['attachments'][1]>0
    if case=='multiframes':
        rows_scope=[json.loads(line) for line in source.read_text().splitlines()]
        for mutation in ('missing','identity','origin','overflow','slots','access','clear','legacy','origin_history','gap_history'):
            changed=copy.deepcopy(rows_scope);r=next(r for r in changed if r.get('status')=='captured');s=r['surface_scope']
            if mutation=='missing':del r['surface_scope']
            if mutation=='identity':s['draw']['attachments'][0]+=1
            if mutation=='origin':s['draw']['origin']['observed']=False
            if mutation=='overflow':s['draw']['open_accesses']=65
            if mutation=='slots':s['draw']['attachments']=[1]*5
            if mutation=='access':s['draw']['access_gap']=0
            if mutation=='clear':s['clear']=None
            if mutation=='legacy':changed[0]['version']=8
            if mutation=='origin_history':
                later=[r for r in changed if r.get('status')=='captured'][1]
                later['surface_scope']['draw']['origin']['private']=False
            if mutation=='gap_history':s['draw']['access_gap']=True
            bad=root/f'bad-scope-{mutation}.jsonl';bad.write_text(''.join(json.dumps(r)+'\n' for r in changed))
            try:inspect(bad)
            except ValueError:pass
            else:raise AssertionError(('bad scope admitted',mutation))
        for mutation in ('shared','epoch','open_before_clear','gap','mrt_before_clear'):
            r=copy.deepcopy(records_scope[0]);s=r['surface_scope']
            if mutation=='shared':s['draw']['origin']['private']=False
            if mutation=='epoch':s['draw']['origin']['reset_epoch']+=1
            if mutation=='open_before_clear':s['clear']['open_accesses']=1
            if mutation=='gap':s['draw']['access_gap']=True
            if mutation=='mrt_before_clear':s['clear']['attachments']=[s['clear']['attachments'][0],9876]
            assert not assess_scope(r)['qualified'],mutation
source,_=run('scope-no-writes',{'RRT_POSITION_SURFACE_SCOPE':'1'});assert not source.exists()
from position_color_replay import PROGRAM,assess_color,prefix as color_prefix,payload as color_payload
from replay_position_colors import replay as replay_colors
color_env=dict(scope_env,RRT_POSITION_COLOR_REPLAY='1')
for case,supported in [('coloroverwrite',True),('colorblend',True),('colorfog',False),('multiframes',False)]:
    source,_=run('color-'+case,dict(color_env,RRT_POSITION_FIXTURE_CASE=case))
    report=inspect(source,include_records=True);assert report['version']==10 and len(report['records'])==16
    color_rows=report['records'];raw=[json.loads(line) for line in source.read_text().splitlines()]
    assert [c['color_replay'] for c in Capture(source).report()['candidates']]==[r['color_replay'] for r in color_rows]
    assert all(assess_color(r)['supported_draw']==supported for r in color_rows),(case,[assess_color(r) for r in color_rows])
    result=replay_colors(source,a.fixture)
    assert all(s['status']==('matched' if supported else 'unqualified') for s in result['segments']),(case,result)
    if supported:assert all(s['max_normalized_error']==0 and s['ready_for_stateful_replay'] for s in result['segments'])
    if case=='colorblend':
        assert len(result['segments'])==8 and all(s['draws']==2 for s in result['segments'])
        background=[32/255,64/255,96/255,64/255]
        first=[.75,.25,.5,.5];second=[.25,.75,.125,.25]
        blend=lambda src,dst:[x*src[3]+y*(1-src[3]) for x,y in zip(src,dst)]
        expected=blend(second,blend(first,background))
        assert all(abs(x-y)<2e-6 for x,y in zip(result['segments'][0]['center'],expected)),result['segments'][0]
        assert all(abs(x-y)<2e-6 for x,y in zip(result['segments'][0]['background'],background))
        def color_probe(rows):
            native=subprocess.run([str(a.fixture),'--position-group'],input=color_payload(rows),env=clean,capture_output=True,text=True,timeout=30)
            assert native.returncode==0,(native.stdout,native.stderr)
            return json.loads(native.stdout)
        swapped=copy.deepcopy(color_rows[:2]);swapped[0]['color_replay']['rgba'],swapped[1]['color_replay']['rgba']=swapped[1]['color_replay']['rgba'],swapped[0]['color_replay']['rgba']
        swapped_result=color_probe(swapped);swapped_expected=blend(first,blend(second,background))
        assert all(abs(x-y)<2e-6 for x,y in zip(swapped_result['center'],swapped_expected))
        assert swapped_result['fingerprint_fnv1a64']!=result['segments'][0]['fingerprint_fnv1a64']
        overwritten=copy.deepcopy(color_rows[:2]);overwritten[-1]['render_state']['states']['blend_enable']=0
        assert all(abs(x-y)<2e-6 for x,y in zip(color_probe(overwritten)['center'],second))
        additive=copy.deepcopy(color_rows[:2])
        for r in additive:r['render_state']['states'].update(src_blend=2,dst_blend=2)
        assert all(abs(x-y)<2e-6 for x,y in zip(color_probe(additive)['center'],[a+b+c for a,b,c in zip(first,second,background)]))
        valid_payload=color_payload(color_rows[:2])
        malformed=[valid_payload+'x',valid_payload.replace('RRT_POSITION_COLOR1','unknown',1),valid_payload.replace('\n2\n','\n17\n',1)]
        invalid_factor=valid_payload.splitlines();invalid_factor[-1]='99';malformed.append('\n'.join(invalid_factor)+'\n')
        for payload_text in malformed:
            native=subprocess.run([str(a.fixture),'--position-group'],input=payload_text,env=clean,capture_output=True,text=True,timeout=30)
            assert native.returncode!=0,'malformed native color payload admitted'
        try:color_prefix(color_rows[1:],color_rows[1])
        except ValueError:pass
        else:raise AssertionError('missing first blend draw admitted')
        for mutation in ('shader','fog','blend','rgba','viewport','depth','npatch'):
            changed=copy.deepcopy(color_rows[:2]);r=changed[0]
            if mutation=='shader':r['color_replay']['pixel_shader']='00000000'
            if mutation=='fog':r['color_replay']['extra_states'][0]=1
            if mutation=='blend':r['render_state']['states']['blend_op']=2
            if mutation=='rgba':r['color_replay']['rgba']=struct.pack('<4f',float('nan'),0,0,1).hex()
            if mutation=='viewport':r['viewport']=struct.pack('<4I2f',0,0,64,96,0,1).hex()
            if mutation=='depth':r['render_state']['states']['z_enable']=1
            if mutation=='npatch':r['color_replay']['npatch_mode']=struct.unpack('<I',struct.pack('<f',2))[0]
            try:color_prefix(changed,changed[-1])
            except ValueError:pass
            else:raise AssertionError(('unsupported prefix admitted',mutation))
        for mutation in ('missing','extra','rgba_shape','state_type','legacy'):
            changed=copy.deepcopy(raw);r=next(r for r in changed if r.get('status')=='captured');c=r['color_replay']
            if mutation=='missing':del r['color_replay']
            if mutation=='extra':c['fabricated']=True
            if mutation=='rgba_shape':c['rgba']='00'
            if mutation=='state_type':c['extra_states'][0]=False
            if mutation=='legacy':changed[0]['version']=9
            bad=root/f'bad-color-{mutation}.jsonl';bad.write_text(''.join(json.dumps(r)+'\n' for r in changed))
            try:inspect(bad)
            except ValueError:pass
            else:raise AssertionError(('invalid color metadata admitted',mutation))
source,_=run('color-no-scope',{'RRT_POSITION_COLOR_REPLAY':'1'});assert not source.exists()
# Audited 48-byte inputs: native pinned VS versus independently evaluated
# passthrough, with distinct clip W and separate UV/color/fog probes.
material_env=dict(color_env,RRT_POSITION_MATERIAL_INPUTS='1')
for case in ('valid','stateblock'):
    source=root/f'material-{case}.jsonl'
    env=dict(clean,**material_env,RRT_FIXTURE_PROXY=str(a.proxy),RRT_POSITION_CAPTURE_FILE=str(source),RRT_MATERIAL_FIXTURE_CASE=case)
    native=subprocess.run([str(a.fixture),'--material-inputs'],input=code+'\n',env=env,capture_output=True,text=True,timeout=60)
    assert native.returncode==0,(native.stdout,native.stderr,root)
    result=json.loads(native.stdout);assert result['status']=='matched' and result['probes']==24 and result['nonzero_lanes']>100 and result['max_normalized_error']<=2e-4,result
    report=inspect(source,include_records=True);assert report['version']==11
    if case=='stateblock':
        assert not report['records'] and sum(report['rejections'].values())==24,report
        continue
    assert len(report['records'])==16 and report['completion']=='capture_limit',report
    for candidate,row in zip(Capture(source).report()['candidates'],report['records']):assert candidate['material_inputs']==row['material_inputs']
    first_material=report['records'][0]['material_inputs']
    assert struct.unpack('<I',bytes.fromhex(first_material['color'])[:4])[0]==0x204080c0
    assert struct.unpack('<f',bytes.fromhex(first_material['uv'])[:4])[0]==-1
    raw=[json.loads(line) for line in source.read_text().splitlines()]
    for mutation in ('missing','color','nan','constants','output','layout','legacy'):
        changed=copy.deepcopy(raw);row=next(r for r in changed if r.get('status')=='captured');m=row['material_inputs']
        if mutation=='missing':del row['material_inputs']
        if mutation=='color':m['color']='00000000'+m['color'][8:]
        if mutation=='nan':m['uv']=struct.pack('<f',float('nan')).hex()+m['uv'][8:]
        if mutation=='constants':m['constants']='00000000'*8
        if mutation=='output':m['evaluated']='00000000'+m['evaluated'][8:]
        if mutation=='layout':row['stride']=44
        if mutation=='legacy':changed[0]['version']=10
        bad=root/f'bad-material-{mutation}.jsonl';bad.write_text(''.join(json.dumps(r)+'\n' for r in changed))
        try:inspect(bad)
        except ValueError:pass
        else:raise AssertionError(('invalid material admitted',mutation))
native=subprocess.run([str(a.fixture),'--material-inputs'],input=code+'\n',env=dict(clean,RRT_MATERIAL_FIXTURE_CASE='wrongcpu'),capture_output=True,text=True,timeout=60)
assert native.returncode!=0 and 'material interpolation mismatch' in native.stderr,(native.stdout,native.stderr)
source,_=run('material-wrong-layout',material_env);assert not inspect(source)['captures']
source,_=run('material-no-color',{'RRT_POSITION_MATERIAL_INPUTS':'1'});assert not source.exists()
# Exact paired PS with two initialized fixture textures. This compares vertex
# paths under the same native PS, not an independently reconstructed PS.
from position_pixel_material import DIGEST as PIXEL_DIGEST
pixel_code=None
with a.inventory.open(encoding='utf-8') as stream:
    for line in stream:
        row=json.loads(line);ps=row.get('ps')
        if row.get('vs')==code and type(ps) is str and hashlib.sha256(bytes.fromhex(ps)).hexdigest()==PIXEL_DIGEST:pixel_code=ps;break
assert pixel_code
pixel_env=dict(material_env,RRT_POSITION_PIXEL_MATERIAL='1')
for case in ('valid','psrefresh','missingps','failedps','psstateblock','nulltexture','wrongshader'):
    source=root/f'pixel-{case}.jsonl'
    env=dict(clean,**pixel_env,RRT_FIXTURE_PROXY=str(a.proxy),RRT_POSITION_CAPTURE_FILE=str(source),RRT_MATERIAL_FIXTURE_CASE=case)
    native=subprocess.run([str(a.fixture),'--pixel-material'],input=code+'\n'+pixel_code+'\n',env=env,capture_output=True,text=True,timeout=60)
    assert native.returncode==0,(case,native.stdout,native.stderr,root)
    result=json.loads(native.stdout);assert result['status']=='matched' and result['probes']==24 and result['nonzero_lanes']>100,result
    report=inspect(source,include_records=True);assert report['version']==12
    if case not in ('valid','psrefresh'):
        assert not report['records'] and sum(report['rejections'].values())==24,report
        continue
    records=report['records'];assert len(records)==16 and report['completion']=='capture_limit'
    for candidate,row in zip(Capture(source).report()['candidates'],records):assert candidate['pixel_material']==row['pixel_material']
    first=records[0]['pixel_material'];fourth=records[3]['pixel_material']
    assert all(abs(x-y)<1e-6 for x,y in zip(struct.unpack('<16f',bytes.fromhex(first['constants'])),[.1,.2,.3,.4,.6,.8,.7,.9,.2,.3,.4,.5,1,0,0,0]))
    assert first['constants']!=fourth['constants']
    for slot,width in ((0,4),(1,8)):
        sampler=first['samplers'][slot];t=sampler['texture']
        assert t['contents']=='unknown' and t['descriptors'][0]==[width,4,21,0,1,0,0]
        assert t['levels']==(3 if slot==0 else 4) and t['lod']==0
        assert sampler['states'][0]==1 and sampler['states'][10]==0
        assert fourth['samplers'][1-slot]['texture']['id']==t['id']
        assert fourth['samplers'][slot]['states'][0]==3 and fourth['samplers'][slot]['states'][10]==1
    assert fourth['samplers'][1]['texture']['lod']==1
    raw=[json.loads(line) for line in source.read_text().splitlines()]
    for mutation in ('missing','shader','constants','nan','states','identity','descriptor','levels','contents','legacy'):
        changed=copy.deepcopy(raw);row=next(r for r in changed if r.get('status')=='captured');m=row['pixel_material'];t=m['samplers'][0]['texture']
        if mutation=='missing':del row['pixel_material']
        if mutation=='shader':row['color_replay']['pixel_shader']=PROGRAM
        if mutation=='constants':m['constants']='00'
        if mutation=='nan':m['constants']=struct.pack('<f',float('nan')).hex()+m['constants'][8:]
        if mutation=='states':m['samplers'][0]['states'][0]=False
        if mutation=='identity':t['id']=0
        if mutation=='descriptor':t['descriptors'][1][0]=4
        if mutation=='levels':t['levels']=17
        if mutation=='contents':t['contents']='initialized'
        if mutation=='legacy':changed[0]['version']=11
        bad=root/f'bad-pixel-{mutation}.jsonl';bad.write_text(''.join(json.dumps(r)+'\n' for r in changed))
        try:inspect(bad)
        except ValueError:pass
        else:raise AssertionError(('invalid pixel material admitted',mutation))
source,_=run('pixel-no-material',{'RRT_POSITION_PIXEL_MATERIAL':'1'});assert not source.exists()
# V13 contains actual initialized mip snapshots; native PS execution still uses
# the original textures, allowing capture transparency checks without replay claims.
texture_env=dict(pixel_env,RRT_POSITION_TEXTURE_INPUTS='1')
for case in ('valid','texpartial','texrefresh','texreadonly','texalias','texfailedlock','texcopy','texgenerated','texincomplete'):
    source=root/f'texture-{case}.jsonl'
    env=dict(clean,**texture_env,RRT_FIXTURE_PROXY=str(a.proxy),RRT_POSITION_CAPTURE_FILE=str(source),RRT_MATERIAL_FIXTURE_CASE=case)
    native=subprocess.run([str(a.fixture),'--pixel-material'],input=code+'\n'+pixel_code+'\n',env=env,capture_output=True,text=True,timeout=60)
    assert native.returncode==0,(case,native.stdout,native.stderr,root)
    result=json.loads(native.stdout);assert result['status']=='matched' and result['probes']==24 and result['nonzero_lanes']>100,result
    report=inspect(source,include_records=True);assert report['version']==13
    if case not in ('valid','texpartial','texrefresh','texreadonly'):
        assert not report['records'] and sum(report['rejections'].values())==24,report
        continue
    records=report['records'];assert len(records)==16 and report['completion']=='capture_limit'
    for candidate,row in zip(Capture(source).report()['candidates'],records):assert candidate['texture_inputs']==row['texture_inputs']
    first=records[0];ids=[t['id'] for t in first['texture_inputs']]
    for row in records:
        for t,s in zip(row['texture_inputs'],row['pixel_material']['samplers']):
            slot=ids.index(t['id']);assert t['origin']=='observed_private_managed'
            if case in ('valid','texreadonly'):assert t['revision']==s['texture']['levels']
            for level,(m,d) in enumerate(zip(t['mips'],s['texture']['descriptors'])):
                expected=b''.join(struct.pack('<I',0xff000000|((32+x*13+level*7)<<16)|((40+y*17+slot*31)<<8)|(60+level*19)) for y in range(d[1]) for x in range(d[0]))
                assert bytes.fromhex(m['bytes'])==expected
    if case!='valid':continue
    from replay_pixel_material import replay as replay_pixel,probe as pixel_probe,payload as pixel_payload
    pixel_report=replay_pixel(source,a.fixture)
    assert pixel_report['scope']=='isolated_draw' and not pixel_report['ready_for_frame_replay'] and len(pixel_report['draws'])==16
    assert all(d['status']=='matched' and d['max_normalized_error']<=2e-4 and d['nonzero_lanes']>100 for d in pixel_report['draws']),pixel_report
    (root/'pixel-comparison.json').write_text(json.dumps(pixel_report,indent=2))
    comparison_controls={'negative':{},'synthetic':[]}
    for control in ('fog','alpha','address','srgb','lod','filter','texel'):
        result=pixel_probe(first,a.fixture,control)
        assert result['status']=='different' and result['max_normalized_error']>2e-4,(control,result)
        comparison_controls['negative'][control]=result
    # Deliberately varied synthetic cases exercise admitted sampler paths and
    # color/fog values, while keeping both PS implementations' inputs identical.
    for variant in range(4):
        synthetic=copy.deepcopy(first)
        for s in synthetic['pixel_material']['samplers']:
            s['states'][0]=variant+1;s['states'][1]=4-variant
            s['states'][3]=0x80402010;s['states'][4]=1+variant%2;s['states'][5]=1+variant%2
            s['states'][6]=variant%3;s['states'][7]=struct.unpack('<I',struct.pack('<f',variant-2.0))[0]
            s['states'][8]=variant%2;s['states'][10]=variant%2
        pc=list(struct.unpack('<16f',bytes.fromhex(synthetic['pixel_material']['constants'])))
        pc[0]=variant*.3-.3;pc[2]=variant*.5-.2;pc[3]=1.5;pc[7]=.2+variant*.2;pc[12]=2.5
        synthetic['pixel_material']['constants']=struct.pack('<16f',*pc).hex()
        # High-frequency lightmap within the v13 bound makes the four-sample
        # filter distinguishable from a single bilinear sample.
        t=synthetic['pixel_material']['samplers'][1]['texture'];t['levels']=8;t['lod']=0;t['descriptors']=[]
        mipdata=synthetic['texture_inputs'][1]['mips']=[]
        for level in range(8):
            w=max(1,128>>level);h=max(1,64>>level);t['descriptors'].append([w,h,21,0,1,0,0])
            data=b''.join(struct.pack('<I',0xff000000|((240 if (x+y)%2 else 15)<<16)|((x*17+y*31+level*19)%256<<8)|((x*41+y*11)%256)) for y in range(h) for x in range(w))
            mipdata.append({'bytes':data.hex(),'sha256':hashlib.sha256(data).hexdigest()})
        result=pixel_probe(synthetic,a.fixture);assert result['status']=='matched',(variant,result)
        comparison_controls['synthetic'].append(dict(result,variant=variant))
        if variant==0:
            altered=pixel_probe(synthetic,a.fixture,'one_sample');assert altered['status']=='different',altered
            comparison_controls['negative']['one_sample']=altered
    (root/'pixel-comparison-controls.json').write_text(json.dumps(comparison_controls,indent=2))
    from qualify_compressed_pixel import qualify as qualify_compressed
    qualify_compressed(first,a.fixture,clean,root)
    native_payload=pixel_payload(first)
    for malformed in (native_payload+'x',native_payload.replace('RRT_PIXEL_REPLAY1','unknown',1),native_payload[:100],native_payload.replace('\n4\n4\n21\n','\n16385\n4\n21\n',1)):
        native=subprocess.run([str(a.fixture),'--pixel-replay'],input=malformed,env=clean,capture_output=True,text=True,timeout=30)
        assert native.returncode!=0,'malformed pixel input admitted'
    raw=[json.loads(line) for line in source.read_text().splitlines()]
    for mutation in ('missing','identity','revision','origin','bytes','digest','mips','format','legacy'):
        changed=copy.deepcopy(raw);row=next(r for r in changed if r.get('status')=='captured');t=row['texture_inputs'][0]
        if mutation=='missing':del row['texture_inputs']
        if mutation=='identity':t['id']+=100
        if mutation=='revision':t['revision']=False
        if mutation=='origin':t['origin']='inferred'
        if mutation=='bytes':t['mips'][0]['bytes']='00'+t['mips'][0]['bytes'][2:]
        if mutation=='digest':t['mips'][0]['sha256']='0'*64
        if mutation=='mips':t['mips'].pop()
        if mutation=='format':
            for d in row['pixel_material']['samplers'][0]['texture']['descriptors']:d[2]=23
        if mutation=='legacy':changed[0]['version']=12
        bad=root/f'bad-texture-{mutation}.jsonl';bad.write_text(''.join(json.dumps(r)+'\n' for r in changed))
        try:inspect(bad)
        except ValueError:pass
        else:raise AssertionError(('invalid texture inputs admitted',mutation))
source,_=run('texture-no-pixel',{'RRT_POSITION_TEXTURE_INPUTS':'1'});assert not source.exists()
# V14 keeps only content references in rows. Large initialized managed chains
# exceed v13's inline bound and deduplicate across the repeated captured draws.
from texture_assets import TextureAssets
asset_env=dict(texture_env,RRT_POSITION_TEXTURE_ASSETS='1')
for case in ('valid','texlarge'):
    source=root/f'assets-{case}.jsonl';asset_root=Path(str(source)+'.assets')
    env=dict(clean,**asset_env,RRT_FIXTURE_PROXY=str(a.proxy),RRT_POSITION_CAPTURE_FILE=str(source),RRT_MATERIAL_FIXTURE_CASE=case)
    native=subprocess.run([str(a.fixture),'--pixel-material'],input=code+'\n'+pixel_code+'\n',env=env,capture_output=True,text=True,timeout=60)
    assert native.returncode==0,(case,native.stdout,native.stderr,root)
    report=inspect(source,include_records=True);assert report['version']==14 and len(report['records'])==16 and report['completion']=='capture_limit',report
    references={m['sha256']:m['size'] for row in report['records'] for t in row['texture_inputs'] for m in t['mips']}
    assert {p.name for p in asset_root.iterdir()}=={d+'.bin' for d in references}
    assert sum(p.stat().st_size for p in asset_root.iterdir())==sum(references.values())
    assert len(references)<sum(len(t['mips']) for row in report['records'] for t in row['texture_inputs'])
    for slot,(t,s) in enumerate(zip(report['records'][0]['texture_inputs'],report['records'][0]['pixel_material']['samplers'])):
        for level,(m,d) in enumerate(zip(t['mips'],s['texture']['descriptors'])):
            expected=b''.join(struct.pack('<I',0xff000000|((32+x*13+level*7)<<16)|((40+y*17+slot*31)<<8)|(60+level*19)) for y in range(d[1]) for x in range(d[0]))
            assert (asset_root/(m['sha256']+'.bin')).read_bytes()==expected
    for candidate,row in zip(Capture(source).report()['candidates'],report['records']):assert candidate['texture_inputs']==row['texture_inputs']
    if case=='texlarge':assert max(references.values())>65536 and source.stat().st_size<1024*1024
    restored=replay_pixel(source,a.fixture,0);assert restored['draws'][0]['status']=='matched',restored
    (root/f'assets-{case}-comparison.json').write_text(json.dumps(restored,indent=2))
    digest,size=next(iter(references.items()));blob=asset_root/(digest+'.bin');original=blob.read_bytes()
    blob.write_bytes(bytes([original[0]^1])+original[1:])
    try:inspect(source)
    except ValueError:pass
    else:raise AssertionError('corrupt external mip admitted')
    blob.write_bytes(original);missing=asset_root/'held.bin';blob.rename(missing)
    try:inspect(source)
    except OSError:pass
    else:raise AssertionError('missing external mip admitted')
    missing.rename(blob)
    raw=source.read_bytes()
    from inspect_position_capture import inspect_bytes
    try:inspect_bytes(raw)
    except ValueError:pass
    else:raise AssertionError('v14 admitted without asset resolver')
    for mutation in ('path','size','inline','legacy','budget'):
        changed=[json.loads(line) for line in raw.splitlines()];m=next(r for r in changed if r.get('status')=='captured')['texture_inputs'][0]['mips'][0]
        if mutation=='path':m['sha256']='../outside'
        if mutation=='size':m['size']+=1
        if mutation=='inline':m['bytes']='00'
        if mutation=='legacy':changed[0]['version']=13
        if mutation=='budget':
            row=next(r for r in changed if r.get('status')=='captured')
            for i,d in enumerate(row['pixel_material']['samplers'][0]['texture']['descriptors']):d[:2]=[max(1,4096>>i),max(1,4096>>i)]
        try:inspect_bytes((''.join(json.dumps(r)+'\n' for r in changed)).encode(),assets=TextureAssets(source))
        except ValueError:pass
        else:raise AssertionError(('malformed asset reference admitted',mutation))
    # A cached resolver binds the bytes it already verified even if a file is
    # replaced later; a new inspection must verify the replacement afresh.
    resolver=TextureAssets(source);assert resolver.read(digest,size)==original
    blob.write_bytes(b'x');assert resolver.read(digest,size)==original;blob.write_bytes(original)
    resolver=TextureAssets(source);resolver.total=256*1024*1024
    try:resolver.read(digest,size)
    except ValueError:pass
    else:raise AssertionError('exhausted external asset budget admitted')
    if case=='valid':
        import shutil
        relocated=root/'relocated-assets.jsonl';relocated.write_bytes(raw)
        shutil.copytree(asset_root,Path(str(relocated)+'.assets'))
        assert Capture(relocated).digest==Capture(source).digest
source=root/'asset-collision.jsonl';asset_root=Path(str(source)+'.assets');asset_root.mkdir();(asset_root/'preserved').write_bytes(b'keep')
env=dict(clean,**asset_env,RRT_FIXTURE_PROXY=str(a.proxy),RRT_POSITION_CAPTURE_FILE=str(source))
native=subprocess.run([str(a.fixture),'--pixel-material'],input=code+'\n'+pixel_code+'\n',env=env,capture_output=True,text=True,timeout=60)
assert native.returncode==0 and inspect(source)['completion']=='io_error' and (asset_root/'preserved').read_bytes()==b'keep'
assert list(asset_root.iterdir())==[asset_root/'preserved']
source,_=run('assets-no-textures',{'RRT_POSITION_TEXTURE_ASSETS':'1'});assert not source.exists() and not Path(str(source)+'.assets').exists()
# Native v2 -> validated snapshot -> scene. Fixture labels are explicit test
# assertions, not evidence of inferred object tracking or temporal continuity.
for source in (capture,reused):
    imported=Capture(source);scene=Scene()
    assert all(c['correspondence']=='unresolved' for c in imported.report()['candidates'])
    assignments={c.ordinal:f'fixture-draw-{c.ordinal}' for c in imported.candidates}
    result=imported.apply(scene,0,0,imported.digest,assignments)
    assert result['scene_delta']['instances']==4
    original=inspect(source,include_records=True)['records']
    for candidate,row in zip(result['candidates'],original):
        assert candidate['resource_provenance']==row['provenance'] and candidate['device']==row['device']
        assert scene.snapshot()['instances'][assignments[row['ordinal']]].geometry.corners==bytes.fromhex(row['positions'])
    assert imported.apply(scene,0,1,imported.digest,assignments)['scene_delta']['new_assets']==0
    before=scene.snapshot()
    try:imported.apply(scene,0,2,imported.digest,{c.ordinal:'ambiguous' for c in imported.candidates})
    except ValueError:pass
    else:raise AssertionError('resource reuse incorrectly admitted as object correspondence')
    assert scene.snapshot()==before
first=next(json.loads(line) for line in capture.read_text().splitlines() if json.loads(line).get('status')=='captured')
assert struct.unpack('<3H',bytes.fromhex(first['indices']))==(0,1,2)
assert struct.unpack('<2f',bytes.fromhex(first['constants'])[:8])==(0,1)
assert first['base']==1 and first['offset']==8 and first['stride']==44 and first['start']==1
expected=(-.63,-.57,.3,.04,.68,.5,.71,-.46,.4)
assert all(abs(x-y)<1e-6 for x,y in zip(struct.unpack('<9f',bytes.fromhex(first['positions'])),expected))
file,_=run('large',{'RRT_POSITION_FIXTURE_CASE':'large'});assert all(x['vb_size']==256*1024 for x in inspect(file)['captures'])
for case in ('stateblock','refresh','failed'):
    file,_=run(case,{'RRT_POSITION_FIXTURE_CASE':case});r=inspect(file)
    if case=='stateblock':assert not r['captures'] and r['rejections'].get('unknown_constants')==24,r
    else:assert len(r['captures'])==4,r
    if case=='failed':assert r['rejections'].get('native_draw_failed')==1,r
marker=root/'ready.trigger'
file,_=run('waiting',{'RRT_POSITION_TRIGGER_FILE':marker});assert not file.exists()
marker.write_text('go')
file,_=run('triggered',{'RRT_POSITION_TRIGGER_FILE':marker});assert len(inspect(file)['captures'])==4
file,_=run('disabled',{'RRT_PROXY_DISABLE':'1'});assert not file.exists()
collision=root/'collision.jsonl';collision.write_bytes(b'preserved')
run('collision');assert collision.read_bytes()==b'preserved'
run('missing-dir',{'RRT_POSITION_CAPTURE_FILE':root/'absent'/'file.jsonl'})
rows=[json.loads(line) for line in capture.read_text().splitlines()]
good=next(x for x in rows if x.get('status')=='captured')
cases=[dict(good,constants='00'),dict(good,positions='00'),dict(good,base=-100),dict(good,primitives=4097),dict(good,evaluated='00'*96),dict(good,shader='00'*612)]
cases += [dict(good,provenance=None),dict(good,provenance=dict(good['provenance'],vb_id=0)),dict(good,provenance=dict(good['provenance'],vb_revision=-1))]
for i,bad in enumerate(cases):
    file=root/f'bad-{i}.jsonl';file.write_text(json.dumps(rows[0])+'\n'+json.dumps(bad)+'\n')
    try:inspect(file)
    except ValueError:pass
    else:raise AssertionError(('bad evidence admitted',i))
print(f'PASS combined position/inventory, unchanged GPU outputs, state-block refresh, native failure, trigger, collision and reader negatives: {root}')
