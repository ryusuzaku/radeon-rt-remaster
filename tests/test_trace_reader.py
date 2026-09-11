import io
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from inspect_trace import inspect_stream, TraceError

def records():
    return [
        {'type':'header','schema':'rrt-observation','version':1,'start_frame':0,'frame_count':100,'pointer_bits':32},
        {'type':'event','seq':0,'frame':0,'thread_id':1,'object':1,'method':'ObjectCreated','hr':0,'args':{'interface':'IDirect3DDevice9'}},
        {'type':'event','seq':1,'frame':0,'thread_id':1,'object':1,'method':'Present','hr':0,'args':{}},
        {'type':'footer','reason':'finished','events':2,'present_count':1},
    ]
def stream(rows):
    return io.StringIO(''.join(json.dumps(r)+'\n' for r in rows))

class ReaderTests(unittest.TestCase):
    def test_shader_profile(self):
        rows=records()[:2]
        args=[{'vertex_shader_bound':v,'pixel_shader_bound':p} for v,p in ((0,0),(1,0),(0,1),(1,1))]+[{}]
        for fields in args:
            rows.append({'type':'event','seq':len(rows)-1,'frame':0,'thread_id':1,'object':1,'method':'DrawPrimitive','hr':0,'args':fields})
        for payload in ('00'*16,'00','zz'*16):
            rows.append({'type':'event','seq':len(rows)-1,'frame':0,'thread_id':1,'object':1,'method':'SetVertexShaderConstantF','hr':0,'args':{'Vector4fCount':1,'constants':payload}})
        rows.append({'type':'event','seq':len(rows)-1,'frame':0,'thread_id':1,'object':1,'method':'DrawPrimitive','hr':-1,'args':args[3]})
        rows.append({'type':'footer','reason':'finished','events':len(rows)-1,'present_count':0})
        profile=inspect_stream(stream(rows))['shader_profile']
        self.assertEqual(profile['draw_bindings'],dict(fixed=1,vertex_only=1,pixel_only=1,vertex_and_pixel=1,unknown=1))
        self.assertEqual(profile['float_constant_payloads'],dict(complete=1,missing_or_truncated=2))
        self.assertEqual(profile['draw_methods'],{'DrawPrimitive':5})
    def test_valid(self):
        result=inspect_stream(stream(records()),frame=0)
        self.assertEqual(result['presents'],1)
        self.assertEqual(len(result['timeline']),2)
    def test_missing_footer(self):
        with self.assertRaises(TraceError): inspect_stream(stream(records()[:-1]))
        self.assertEqual(inspect_stream(stream(records()[:-1]),allow_incomplete=True)['completion'],'incomplete')
    def test_mutations_rejected(self):
        mutations=[(0,'version',2),(0,'version',True),(1,'seq',3),(2,'frame',4),
                   (2,'object',2),(2,'hr','bad'),(3,'events',40),(3,'present_count',50)]
        for index,key,value in mutations:
            with self.subTest(key=key,value=value):
                rows=records(); rows[index][key]=value
                with self.assertRaises(TraceError): inspect_stream(stream(rows))
    def test_truncation_and_junk(self):
        for text in ('','{}','{broken}\n','x'*65537+'\n','[]\n','{"type":1,"type":2}\n','['*2000+'0'+']'*2000+'\n'):
            with self.subTest(text=text[:10]):
                with self.assertRaises(TraceError): inspect_stream(io.StringIO(text))
    def test_data_after_footer(self):
        with self.assertRaises(TraceError): inspect_stream(stream(records()+[records()[1]]))
    def test_selected_frame_external_object(self):
        rows=records(); rows[0]['start_frame']=10
        rows.pop(1); rows[1].update(seq=0,frame=10); rows[2].update(events=1,present_count=11)
        self.assertEqual(inspect_stream(stream(rows))['presents'],1)
    def test_destroyed_identity(self):
        rows=records(); rows[1]['method']='ObjectDestroyed'
        with self.assertRaises(TraceError): inspect_stream(stream(rows))

if __name__ == '__main__': unittest.main()
