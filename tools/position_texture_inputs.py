"""V13 bounded initialized texture snapshots, separate from descriptor evidence."""
import hashlib

def validate(row,assets=None,external=False,compressed=False,uploads=False,dirty=False,surfaces=False):
    def need(ok,message):
        if not ok:raise ValueError('texture inputs: '+message)
    textures=row.get('texture_inputs');need(type(textures) is list and len(textures)==2,'shape')
    shared={};sources={}
    bound_ids={s['texture']['id'] for s in row['pixel_material']['samplers']}
    for value,sampler in zip(textures,row['pixel_material']['samplers']):
        desc=sampler['texture']
        uploaded=uploads and desc['descriptors'][0][4]==0
        surface=surfaces and uploaded and type(value) is dict and value.get('origin')=='observed_private_default_surface'
        need(type(value) is dict and set(value)==({'id','revision','origin','mips','surface_transfers'} if surface else {'id','revision','origin','mips','transfer'} if uploaded else {'id','revision','origin','mips'}),'texture shape')
        need(type(value['id']) is int and value['id']==desc['id'],'binding identity')
        need(type(value['revision']) is int and 0<value['revision']<2**64 and value['origin']==('observed_private_default_surface' if surface else 'observed_private_default_update' if uploaded else 'observed_private_managed'),'provenance')
        if uploaded and not surface:
            transfer=value['transfer']
            need(type(transfer) is dict and set(transfer)==({'operation','scope','source','revision','dirty_proof'} if dirty else {'operation','scope','source','revision'}),'transfer shape')
            if dirty:need(transfer['dirty_proof'] in ('creation','top_lock','notification'),'dirty proof')
            need(transfer['operation']=='UpdateTexture' and transfer['scope']=='whole_chain','transfer scope')
            need(type(transfer['source']) is int and 0<transfer['source']<2**64 and transfer['source'] not in bound_ids and type(transfer['revision']) is int and 0<transfer['revision']<2**64,'transfer identity/revision')
        mips=value['mips'];need(type(mips) is list and len(mips)==desc['levels'],'mips')
        total=0
        base=desc['descriptors'][0]
        if compressed:
            need(external and desc['levels']<=max(base[:2]).bit_length(),'compressed version/mip count')
            if base[2] not in (21,22):need(base[0]%4==0 and base[1]%4==0,'compressed base alignment')
        for mip,d in zip(mips,desc['descriptors']):
            need(d[2] in ((21,22,0x31545844,0x33545844,0x35545844) if compressed else (21,22)) and d[3:]==[0,0 if uploaded else 1,0,0],'format/pool/usage')
            size=d[0]*d[1]*4 if d[2] in (21,22) else ((d[0]+3)//4)*((d[1]+3)//4)*(8 if d[2]==0x31545844 else 16)
            total+=size;need(total<=(16*1024*1024 if external else 65536),'byte budget')
            need(type(mip) is dict and set(mip)==({'sha256','size'} if external else {'sha256','bytes'}),'mip shape')
            if external:
                need(assets is not None and type(mip['size']) is int and mip['size']==size,'asset size/resolver')
                assets.read(mip['sha256'],size)
            else:
                data=mip['bytes'];need(type(data) is str and len(data)==size*2 and all(c in '0123456789abcdef' for c in data),'bytes')
                need(type(mip['sha256']) is str and hashlib.sha256(bytes.fromhex(data)).hexdigest()==mip['sha256'],'digest')
        if value['id'] in shared:need(value==shared[value['id']],'shared texture disagreement')
        shared[value['id']]=value
        if surface:
            from position_surface_transfers import validate as validate_surface_transfers
            validate_surface_transfers(value,desc['descriptors'],bound_ids)
        elif uploaded:
            key=(transfer['source'],transfer['revision']);snapshot=(desc['descriptors'],mips)
            if key in sources:need(snapshot==sources[key],'shared upload disagreement')
            sources[key]=snapshot
