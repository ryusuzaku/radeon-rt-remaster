"""Native UpdateSurface mip coverage, byte preservation and rejection controls."""
import copy
import hashlib
import json
from pathlib import Path
import struct
import subprocess
from capture_position_scene import Capture
from inspect_position_capture import inspect,inspect_bytes
from texture_assets import TextureAssets
from replay_pixel_material import replay
from qualify_compressed_pixel import blocks

def rgba(w,h,level,slot,x0=0,y0=0):
    return b''.join(struct.pack('<I',0xff000000|((32+x*13+level*7)<<16)|((40+y*17+slot*31)<<8)|(60+level*19))
                    for y in range(y0,y0+h) for x in range(x0,x0+w))

def qualify(fixture,proxy,root,clean,asset_env,code,pixel_code):
    flags=dict(asset_env,RRT_POSITION_COMPRESSED_TEXTURES='1',RRT_POSITION_TEXTURE_UPLOADS='1',
               RRT_POSITION_DIRTY_TEXTURES='1',RRT_POSITION_SURFACE_UPLOADS='1')
    summary={'version':18,'accepted':[],'rejected':[],'legacy':[]}
    def run(case,suffix='',override=None,proxied=True):
        path=root/('surface-'+case+suffix+'.jsonl')
        env=dict(clean,RRT_MATERIAL_FIXTURE_CASE='valid' if case=='managed' else 'upload-'+case)
        if proxied:
            env.update(flags if override is None else override)
            env.update(RRT_FIXTURE_PROXY=str(proxy),RRT_POSITION_CAPTURE_FILE=str(path))
        r=subprocess.run([str(fixture),'--pixel-material'],input=code+'\n'+pixel_code+'\n',env=env,capture_output=True,text=True,timeout=60)
        assert r.returncode==0,(case,r.returncode,r.stdout,r.stderr)
        return path,json.loads(r.stdout)
    for name in ('rgba','dxt1','dxt3','dxt5'):
        actions=['surfacefull','surfacepartial','surfaceoffset','surfacerefresh','surfacestaged','surfacemip',
                 'surfaceincomplete','surfaceunknown','surfacefailed','surfacehistory','surfacerecover','surfaceafter']
        if name!='rgba':actions.append('surfaceunaligned')
        for action in actions:
            case=name+'-'+action;path,native=run(case);_,baseline=run(case,'-baseline',proxied=False)
            assert native==baseline,(case,native,baseline)
            report=inspect(path,include_records=True);assert report['version']==18
            if action in ('surfaceincomplete','surfaceunknown','surfacefailed','surfacehistory','surfaceunaligned'):
                assert not report['records'] and report['rejections'],(case,report)
                summary['rejected'].append(case);continue
            rows=report['records'];assert len(rows)==16 and report['completion']=='capture_limit',(case,report)
            ids=[t['id'] for t in rows[0]['texture_inputs']]
            generation=1 if action in ('surfacerefresh','surfacerecover','surfacemip','surfaceafter') else 0
            for row in rows:
                for t,s in zip(row['texture_inputs'],row['pixel_material']['samplers']):
                    assert t['origin']==('observed_private_default_update' if action=='surfaceafter' else 'observed_private_default_surface')
                    if action!='surfaceafter':assert 1<=len(t['surface_transfers'])<=128
                    slot=ids.index(t['id'])
                    for level,(m,d) in enumerate(zip(t['mips'],s['texture']['descriptors'])):
                        w,h=d[:2];data=bytearray(rgba(w,h,level+generation,slot) if name=='rgba' else blocks(name.upper(),w,h,level+generation,slot))
                        if action=='surfaceoffset' and level==0:
                            if name=='rgba':
                                patch=rgba(4,4,1,slot,4,4)
                                for y in range(4):data[y*w*4:y*w*4+16]=patch[y*16:y*16+16]
                            else:
                                size=8 if name=='dxt1' else 16
                                patch=blocks(name.upper(),w,h,1,slot);start=((w+3)//4+1)*size
                                data[:size]=patch[start:start+size]
                        assert m=={'sha256':hashlib.sha256(data).hexdigest(),'size':len(data)},(case,slot,level,m)
                        assert (Path(str(path)+'.assets')/(m['sha256']+'.bin')).read_bytes()==data
            assert Capture(path).report()['candidates'][0]['texture_inputs']==rows[0]['texture_inputs']
            result=replay(path,fixture,0);assert result['draws'][0]['status']=='matched',(case,result)
            summary['accepted'].append(dict(case=case,native_sha256=native['native_sha256'],replay=result))
            if action!='surfacefull':continue
            oldflags=dict(flags);oldflags.pop('RRT_POSITION_SURFACE_UPLOADS')
            old,old_native=run(case,'-legacy',oldflags)
            assert inspect(old)['version']==17 and not inspect(old)['captures'] and old_native==native
            summary['legacy'].append(case)
            original=[json.loads(line) for line in path.read_bytes().splitlines()]
            for mutation in ('legacy','coverage','duplicate','source','revision','source_bounds','destination_bounds','level','budget','origin','alignment','extent_conflict'):
                changed=copy.deepcopy(original);t=next(r for r in changed if r.get('status')=='captured')['texture_inputs'][0];events=t['surface_transfers'];e=events[0]
                if mutation=='legacy':changed[0]['version']=17
                elif mutation=='coverage':events.pop()
                elif mutation=='duplicate':events[-1]=copy.deepcopy(e)
                elif mutation=='source':e['source']=t['id']
                elif mutation=='revision':e['revision']=False
                elif mutation=='source_bounds':e['source_rect'][2]=e['source_extent'][0]+1
                elif mutation=='destination_bounds':e['destination'][0]=16384
                elif mutation=='level':e['destination_level']=16
                elif mutation=='budget':t['surface_transfers']=[copy.deepcopy(e) for _ in range(129)]
                elif mutation=='alignment':e['source_rect'][0]=1
                elif mutation=='extent_conflict':
                    extra=copy.deepcopy(e);extra['source_extent'][0]+=4;events.append(extra)
                else:t['origin']='observed_private_default_update'
                try:inspect_bytes((''.join(json.dumps(r)+'\n' for r in changed)).encode(),assets=TextureAssets(path))
                except ValueError:pass
                else:raise AssertionError((case,mutation))
                summary['rejected'].append(case+':'+mutation)
    path,_=run('managed');r=inspect(path,include_records=True)
    assert r['version']==18 and len(r['records'])==16 and all(t['origin']=='observed_private_managed' for t in r['records'][0]['texture_inputs'])
    for i,bad in enumerate(({'RRT_POSITION_SURFACE_UPLOADS':'1'},dict(flags,RRT_POSITION_SURFACE_UPLOADS='2'))):
        path,_=run('rgba-surfacefull','-invalid'+str(i),bad);assert not path.exists()
    (root/'surface-upload-comparison.json').write_text(json.dumps(summary,indent=2))
