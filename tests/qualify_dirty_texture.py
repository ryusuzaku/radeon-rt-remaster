"""V17 explicit dirty proofs and system-memory NO_DIRTY_UPDATE qualification."""
import copy
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from capture_position_scene import Capture
from inspect_position_capture import inspect, inspect_bytes
from texture_assets import TextureAssets
from replay_pixel_material import replay
from qualify_compressed_pixel import blocks

def qualify(fixture, proxy, root, clean, asset_env, code, pixel_code):
    flags=dict(asset_env,RRT_POSITION_COMPRESSED_TEXTURES='1',RRT_POSITION_TEXTURE_UPLOADS='1',RRT_POSITION_DIRTY_TEXTURES='1')
    summary={'version':17,'accepted':[],'rejected':[],'legacy':[]}
    def run(case,suffix='',override=None,proxied=True):
        path=root/('dirty-'+case.replace(':','-')+suffix+'.jsonl')
        env=dict(clean,RRT_MATERIAL_FIXTURE_CASE=case[8:] if case.startswith('managed:') else 'upload-'+case)
        if proxied:
            env.update(flags if override is None else override)
            env.update(RRT_FIXTURE_PROXY=str(proxy),RRT_POSITION_CAPTURE_FILE=str(path))
        native=subprocess.run([str(fixture),'--pixel-material'],input=code+'\n'+pixel_code+'\n',env=env,capture_output=True,text=True,timeout=60)
        assert native.returncode==0,(case,native.returncode,native.stdout,native.stderr)
        return path,json.loads(native.stdout)
    for name in ('rgba','dxt1','dxt3','dxt5'):
        for action in ('dirtycreation','dirtyfull','dirtyrect','dirtytop','dirtykeep','dirtynone','dirtypartial','dirtyunknown','dirtyfailed'):
            case=name+'-'+action
            path,native=run(case);_,baseline=run(case,'-baseline',proxied=False)
            assert native==baseline,(case,native,baseline)
            report=inspect(path,include_records=True);assert report['version']==17
            if action in ('dirtynone','dirtypartial','dirtyunknown','dirtyfailed'):
                assert not report['records'] and report['rejections'],(case,report)
                summary['rejected'].append(case);continue
            rows=report['records'];assert len(rows)==16 and report['completion']=='capture_limit'
            ids=[t['id'] for t in rows[0]['texture_inputs']]
            proof='creation' if action=='dirtycreation' else 'top_lock' if action=='dirtytop' else 'notification'
            generation=0 if action=='dirtycreation' else 1
            for row in rows:
                for t,s in zip(row['texture_inputs'],row['pixel_material']['samplers']):
                    assert t['transfer']['dirty_proof']==proof and t['origin']=='observed_private_default_update'
                    slot=ids.index(t['id'])
                    for level,(m,d) in enumerate(zip(t['mips'],s['texture']['descriptors'])):
                        data=(b''.join(struct.pack('<I',0xff000000|((32+x*13+(level+generation)*7)<<16)|((40+y*17+slot*31)<<8)|(60+(level+generation)*19))
                                      for y in range(d[1]) for x in range(d[0])) if name=='rgba' else blocks(name.upper(),*d[:2],level+generation,slot))
                        assert m=={'sha256':hashlib.sha256(data).hexdigest(),'size':len(data)}
                        assert (Path(str(path)+'.assets')/(m['sha256']+'.bin')).read_bytes()==data
            assert Capture(path).report()['candidates'][0]['texture_inputs']==rows[0]['texture_inputs']
            result=replay(path,fixture,0);assert result['draws'][0]['status']=='matched',(case,result)
            summary['accepted'].append(dict(case=case,proof=proof,native_sha256=native['native_sha256'],replay=result))
            if action!='dirtyfull':continue
            old_flags=dict(flags);old_flags.pop('RRT_POSITION_DIRTY_TEXTURES')
            old,old_native=run(case,'-legacy',old_flags)
            assert inspect(old)['version']==16 and not inspect(old)['captures'] and old_native==native
            summary['legacy'].append(case)
            original=[json.loads(line) for line in path.read_bytes().splitlines()]
            for mutation in ('missing','unknown','type','legacy'):
                changed=copy.deepcopy(original)
                t=next(r for r in changed if r.get('status')=='captured')['texture_inputs'][0]['transfer']
                if mutation=='missing':del t['dirty_proof']
                elif mutation=='unknown':t['dirty_proof']='partial_notification'
                elif mutation=='type':t['dirty_proof']=True
                else:changed[0]['version']=16
                try:inspect_bytes((''.join(json.dumps(r)+'\n' for r in changed)).encode(),assets=TextureAssets(path))
                except ValueError:pass
                else:raise AssertionError((case,mutation))
                summary['rejected'].append(case+':'+mutation)
    path,_=run('managed:valid');report=inspect(path,include_records=True)
    assert report['version']==17 and len(report['records'])==16
    assert all('transfer' not in t for t in report['records'][0]['texture_inputs'])
    path,_=run('managed:dxt1-flags');assert not inspect(path)['captures'],'managed NO_DIRTY_UPDATE admitted'
    for i,invalid in enumerate(({'RRT_POSITION_DIRTY_TEXTURES':'1'},dict(flags,RRT_POSITION_DIRTY_TEXTURES='2'),dict(asset_env,RRT_POSITION_DIRTY_TEXTURES='1'))):
        path,_=run('rgba-dirtyfull','-invalid'+str(i),invalid)
        assert not path.exists() and not Path(str(path)+'.assets').exists()
    (root/'dirty-texture-comparison.json').write_text(json.dumps(summary,indent=2))

if __name__=='__main__':
    import argparse
    import os
    import tempfile
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('capture','fixture','proxy'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();row=inspect(args.capture,include_records=True)['records'][0]
    suffixes=('FRAME_SAMPLING','MULTI_DRAW','RENDER_STATE','CLEAR_EVIDENCE','WRITE_EVIDENCE','SURFACE_SCOPE','COLOR_REPLAY','MATERIAL_INPUTS','PIXEL_MATERIAL','TEXTURE_INPUTS','TEXTURE_ASSETS')
    flags={'RRT_POSITION_'+s:'1' for s in suffixes};flags['RRT_POSITION_SELECTION']='128x96:1'
    root=Path(tempfile.mkdtemp(prefix='dirty-textures-',dir=args.fixture.resolve().parent))
    clean={k:v for k,v in os.environ.items() if not k.upper().startswith('RRT_')}
    qualify(args.fixture.resolve(),args.proxy.resolve(),root,clean,flags,row['shader'],row['color_replay']['pixel_shader'])
    print('PASS dirty textures: '+str(root))

