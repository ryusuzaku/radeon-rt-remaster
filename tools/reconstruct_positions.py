"""Export validated per-draw geometry; model-output space is not assumed world space."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
from inspect_position_capture import inspect,need

def bounded_hash(path):
    with Path(path).open('rb') as stream:data=stream.read(16*1024*1024+1)
    need(len(data)<=16*1024*1024,'source byte budget')
    return hashlib.sha256(data).hexdigest()

def inverse(matrix):
    work=[list(row)+[float(i==j) for j in range(4)] for i,row in enumerate(matrix)]
    for column in range(4):
        pivot=max(range(column,4),key=lambda i:abs(work[i][column]))
        if abs(work[pivot][column])<1e-10:return None
        work[pivot],work[column]=work[column],work[pivot]
        scale=work[column][column];work[column]=[x/scale for x in work[column]]
        for i in range(4):
            if i!=column:
                scale=work[i][column];work[i]=[x-scale*y for x,y in zip(work[i],work[column])]
    return [row[4:] for row in work]

def bounds(points):
    return {'min':[min(p[i] for p in points) for i in range(3)],'max':[max(p[i] for p in points) for i in range(3)]}

def reconstruct(source,out):
    source=Path(source).resolve();digest=bounded_hash(source);report=inspect(source,include_records=True)
    need(digest==bounded_hash(source),'source changed during validation')
    need(report['completion'] in ('capture_limit','attempt_limit','byte_limit','present_limit') and report['records'],'no completed accepted geometry')
    meshes=[];outputs={}
    for row in report.pop('records'):
        n=row['primitives']*3
        indices=struct.unpack('<'+'H'*n,bytes.fromhex(row['indices']))
        positions=list(struct.iter_unpack('<3f',bytes.fromhex(row['positions'])))
        evaluated=list(struct.iter_unpack('<8f',bytes.fromhex(row['evaluated'])))
        c=list(struct.iter_unpack('<4f',bytes.fromhex(row['constants'])))
        unique={};raw=[];model=[];faces=[]
        for index,p,result in zip(indices,positions,evaluated):
            if index in unique:
                at=unique[index];need(raw[at]==p and model[at]==result[4:7],'inconsistent repeated vertex')
            else:
                unique[index]=len(raw);raw.append(p);model.append(result[4:7])
            faces.append(unique[index]+1)
        for space,vertices in [('input',raw),('model-output',model)]:
            name=f'draw-{row["ordinal"]}-{space}.obj'
            lines=[f'# Position-only capture; {space}; no world-space/material guarantee',f'o draw_{row["ordinal"]}']
            lines += ['v '+' '.join(format(x,'.9g') for x in p) for p in vertices]
            lines += ['f '+' '.join(str(x) for x in faces[i:i+3]) for i in range(0,n,3)]
            outputs[name]='\n'.join(lines)+'\n'
        model_matrix=[list(x) for x in c[5:8]]+[[0,0,0,1]]
        inv=inverse(model_matrix)
        # This affine extension is appropriate only when the captured q.w is one.
        affine=c[0][0]==0 and c[0][1]==1
        derived=None
        if affine and inv is not None:
            derived=[[sum(c[i+1][k]*inv[k][j] for k in range(4)) for j in range(4)] for i in range(4)]
        degenerate=0
        for i in range(0,n,3):
            a,b,d=(model[faces[i+j]-1] for j in range(3));u=[b[k]-a[k] for k in range(3)];v=[d[k]-a[k] for k in range(3)]
            cross=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
            degenerate+=sum(x*x for x in cross)<=1e-16
        meshes.append({'ordinal':row['ordinal'],'device':row.get('device'),'resource_provenance':row.get('provenance'),'timing':row.get('timing'),'render_state':row.get('render_state'),'triangles':row['primitives'],'vertices':len(raw),'input_bounds':bounds(raw),'model_output_bounds':bounds(model),
                       'c0':c[0],'model_rows':c[5:8],'clip_rows':c[1:5],'affine_input':affine,'derived_model_to_clip':derived,
                       'positive_clip_w_corners':sum(p[3]>0 for p in evaluated),'degenerate_model_triangles':degenerate,
                       'viewport':struct.unpack('<4I2f',bytes.fromhex(row['viewport'])),'target':row['target']})
    matrices=[m['derived_model_to_clip'] for m in meshes]
    groups={}
    for mesh in meshes:
        timing=mesh['timing']
        interval=[mesh['device'],timing['reset_epoch'],timing['present_interval']] if timing is not None else None
        key=json.dumps([interval,mesh['target'],mesh['viewport'],mesh['clip_rows'],mesh['render_state']],separators=(',',':'),sort_keys=True)
        groups.setdefault(key,[]).append(mesh['ordinal'])
    deviation=None
    if all(m is not None for m in matrices):
        deviation=max(abs(m[i][j]-matrices[0][i][j]) for m in matrices for i in range(4) for j in range(4))
    manifest={'schema':'rrt-position-reconstruction','version':1,'source':str(source),'source_sha256':digest,'capture':report,'draws':meshes,'render_groups':list(groups.values()),
              'max_derived_model_to_clip_difference':deviation,'coordinate_status':'model-output only; world-space interpretation unverified',
              'scope':'per-draw positions/triangles; no cross-draw deduplication, normals, materials or complete scene'}
    outputs['manifest.json']=json.dumps(manifest,indent=2,allow_nan=False)+'\n'
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    for name,text in outputs.items():
        with (out/name).open('x',encoding='utf-8') as stream:stream.write(text)
    return manifest

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    try:
        r=reconstruct(a.source,a.out)
        print(json.dumps({'draws':len(r['draws']),'triangles':sum(d['triangles'] for d in r['draws']),'derived_transform_difference':r['max_derived_model_to_clip_difference'],'output':str(a.out.resolve())}))
    except (OSError,ValueError,KeyError,TypeError) as e:p.exit(2,f'reconstruction rejected: {e}\n')
