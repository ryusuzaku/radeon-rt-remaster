"""Game-sized isolated comparison, explicit normalization and parser boundaries."""
import copy
import json
import struct
import subprocess
from inspect_position_capture import inspect
from texture_assets import TextureAssets
from replay_pixel_material import payload,probe

def qualify(fixture,proxy,root,clean,flags,code,pixel):
    path=root/'material.jsonl'
    env=dict(clean,**flags,RRT_FIXTURE_PROXY=str(proxy),RRT_POSITION_CAPTURE_FILE=str(path),RRT_MATERIAL_FIXTURE_CASE='valid')
    run=subprocess.run([str(fixture),'--pixel-material'],input=code+'\n'+pixel+'\n',env=env,text=True,capture_output=True,timeout=60)
    assert run.returncode==0,(run.stdout,run.stderr)
    row=inspect(path,include_records=True)['records'][0]
    assets=TextureAssets(path)
    for texture in row['texture_inputs']:
        for mip in texture['mips']:mip['bytes']=assets.read(mip['sha256'],mip['size']).hex()
    baseline=probe(row,fixture)
    normalized=probe(row,fixture,normalized=True)
    assert baseline['native_sha256']==normalized['native_sha256']
    assert baseline['reconstructed_sha256']==normalized['reconstructed_sha256']
    results=[]
    for width,height,vp in [(5120,1440,(0,0,5120,1440,0,1)),(320,240,(17,23,271,191,.2,.8))]:
        candidate=copy.deepcopy(row);candidate['target']=[width,height,21,0 if width==5120 else 4]
        candidate['viewport']=struct.pack('<4I2f',*vp).hex()
        candidate['render_state']['states'].update(z_enable=1,blend_enable=1,cull=3,srgb_write=1)
        try:payload(candidate)
        except ValueError:pass
        else:raise AssertionError('strict mode accepted normalized scope')
        result=probe(candidate,fixture,normalized=True)
        assert result['status']=='matched',result
        assert result['diagnostic_scope']['composition_preserved'] is False
        control=probe(candidate,fixture,'texel',normalized=True)
        assert control['status']=='different',control
        results.append(result)
    # Independently exercise native protocol validation before shader/device creation.
    for changes in [{1:'0'},{1:'8193'},{2:'0'},{1:'8192',2:'1024'},{3:'4294967295'},{5:'0'},{7:'2143289344'},{8:'1065353217'}]:
        lines=payload(row,True).splitlines()
        for index,value in changes.items():lines[index]=value
        rejected=subprocess.run([str(fixture),'--pixel-replay'],input='\n'.join(lines)+'\n',env=clean,text=True,capture_output=True,timeout=60)
        assert rejected.returncode!=0,(index,value)
    for target,vp in [([0,96,21,0],(0,0,128,96,0,1)),([8192,8192,21,0],(0,0,128,96,0,1)),([128,96,21,0],(1,0,128,96,0,1)),([128,96,21,0],(0,0,128,96,1,0))]:
        bad=copy.deepcopy(row);bad['target']=target;bad['viewport']=struct.pack('<4I2f',*vp).hex()
        try:payload(bad,True)
        except ValueError:pass
        else:raise AssertionError('invalid Python scope accepted')
    (root/'scope-comparison.json').write_text(json.dumps(results,indent=2))

