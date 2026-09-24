import struct
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from position_scene import Geometry,Instance,Scene

class Tests(unittest.TestCase):
    def setUp(self):
        self.g=Geometry(struct.pack('<9f',0,0,0,1,0,0,0,1,0));self.c=(0.0,)*32
    def test_reuse_motion_and_identity(self):
        s=Scene();r=s.apply(0,0,[Instance('a',self.g,self.c),Instance('b',Geometry(self.g.corners),self.c)])
        self.assertEqual((r['geometry_assets'],r['instances'],r['geometry_bytes']),(1,2,36))
        old=s.snapshot()['geometry'][self.g.key]
        r=s.apply(0,1,[Instance('a',self.g,(1.0,)+self.c[1:])])
        self.assertEqual(r['new_assets'],0);self.assertEqual(r['instances'],2)
        self.assertIs(s.snapshot()['geometry'][self.g.key],old)
        self.assertNotEqual(s.snapshot()['instances']['a'].constants,s.snapshot()['instances']['b'].constants)
    def test_replacement_and_removal(self):
        s=Scene();s.apply(0,0,[Instance('a',self.g,self.c)])
        g=Geometry(struct.pack('<9f',0,0,0,2,0,0,0,1,0));r=s.apply(0,1,[Instance('a',g,self.c)])
        self.assertEqual((r['new_assets'],r['released_assets']),(1,1))
        r=s.apply(0,2,removes=['a']);self.assertEqual(r['geometry_bytes'],0)
    def test_atomic_budget_and_conflict(self):
        s=Scene(max_instances=1,max_geometry_bytes=36);s.apply(0,0,[Instance('a',self.g,self.c)]);before=s.snapshot()
        for updates,removes in [([Instance('b',self.g,self.c)],()),([Instance('a',self.g,self.c)],['a']),([Instance('a',Geometry(self.g.corners*2),self.c)],())]:
            with self.assertRaises(ValueError):s.apply(0,1,updates,removes)
            self.assertEqual(s.snapshot(),before)
    def test_epoch_and_sequence(self):
        s=Scene();s.apply(0,1,[Instance('a',self.g,self.c)])
        with self.assertRaises(ValueError):s.apply(0,1)
        s.reset();self.assertFalse(s.snapshot()['instances'])
        with self.assertRaises(ValueError):s.apply(0,2,[Instance('a',self.g,self.c)])
        s.apply(1,0,[Instance('a',self.g,self.c)])
    def test_invalid_data(self):
        for data in (b'',b'x',struct.pack('<9f',float('nan'),*([0]*8))):
            with self.assertRaises(ValueError):Geometry(data)
        with self.assertRaises(ValueError):Instance('',self.g,self.c)
        with self.assertRaises(ValueError):Instance('a',self.g,(float('inf'),)*32)
    def test_snapshot_does_not_expose_mutable_maps(self):
        s=Scene();s.apply(0,0,[Instance('a',self.g,self.c)])
        external=s.snapshot();external['instances'].clear();external['geometry'].clear()
        self.assertEqual(len(s.snapshot()['instances']),1)
    def test_unseen_instances_retained(self):
        s=Scene();s.apply(0,0,[Instance('a',self.g,self.c)])
        self.assertEqual(s.apply(0,1)['instances'],1)
        self.assertEqual(s.apply(0,2,removes=['not-present'])['instances'],1)

if __name__=='__main__':unittest.main()
