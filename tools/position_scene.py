"""Bounded position-only scene state. Caller-supplied instance IDs are never inferred."""
from dataclasses import dataclass
import hashlib
import math
import struct

@dataclass(frozen=True)
class Geometry:
    corners: bytes
    def __post_init__(self):
        if type(self.corners) is not bytes or not self.corners or len(self.corners)>4096*3*12 or len(self.corners)%36:
            raise ValueError('invalid bounded triangle positions')
        if not all(math.isfinite(x[0]) for x in struct.iter_unpack('<f',self.corners)):
            raise ValueError('nonfinite triangle position')
    @property
    def key(self):
        # Domain separation prevents using this as a full mesh/material identity.
        return hashlib.sha256(b'rrt-position-only-v1\0'+self.corners).hexdigest()

@dataclass(frozen=True)
class Instance:
    identity: str
    geometry: Geometry
    constants: tuple
    def __post_init__(self):
        if not isinstance(self.identity,str) or not 1<=len(self.identity)<=128:
            raise ValueError('explicit bounded instance identity required')
        if not isinstance(self.geometry,Geometry):raise ValueError('geometry required')
        if type(self.constants) is not tuple or len(self.constants)!=32 or not all(type(v) in (int,float) and math.isfinite(v) and abs(v)<=3.402823466e38 for v in self.constants):
            raise ValueError('finite float32 position constants required')

class Scene:
    """Atomic deltas; unseen instances remain until explicit removal or reset."""
    def __init__(self,max_instances=128,max_geometry_bytes=16*1024*1024):
        if type(max_instances) is not int or not 1<=max_instances<=4096:raise ValueError('instance budget')
        if type(max_geometry_bytes) is not int or not 1<=max_geometry_bytes<=64*1024*1024:raise ValueError('geometry budget')
        self.max_instances=max_instances;self.max_geometry_bytes=max_geometry_bytes
        self.epoch=0;self.sequence=-1;self._instances={};self._geometry={}
    def reset(self):
        self.epoch+=1;self.sequence=-1;self._instances={};self._geometry={}
        return self.epoch
    def apply(self,epoch,sequence,updates=(),removes=()):
        if type(epoch) is not int or epoch!=self.epoch or type(sequence) is not int or sequence<=self.sequence:
            raise ValueError('stale epoch/sequence')
        if not isinstance(updates,(list,tuple)) or not isinstance(removes,(list,tuple)) or len(updates)+len(removes)>4096:
            raise ValueError('delta bound')
        identities=set();deletes=set()
        for update in updates:
            if not isinstance(update,Instance) or update.identity in identities:raise ValueError('duplicate/invalid instance')
            identities.add(update.identity)
        for identity in removes:
            if not isinstance(identity,str) or not 1<=len(identity)<=128 or identity in deletes or identity in identities:raise ValueError('conflicting removal')
            deletes.add(identity)
        candidate=dict(self._instances)
        for identity in deletes:candidate.pop(identity,None)
        for update in updates:candidate[update.identity]=update
        if len(candidate)>self.max_instances:raise ValueError('instance budget exhausted')
        geometry={};canonical={};charged=0
        for identity,instance in candidate.items():
            key=instance.geometry.key
            if key in geometry and geometry[key].corners!=instance.geometry.corners:raise ValueError('content hash collision')
            if key not in geometry:
                retained=self._geometry.get(key,instance.geometry)
                if retained.corners!=instance.geometry.corners:raise ValueError('retained hash collision')
                geometry[key]=retained;charged+=len(retained.corners)
            if charged>self.max_geometry_bytes:raise ValueError('geometry budget exhausted')
            canonical[identity]=Instance(identity,geometry[key],instance.constants)
        old_keys=set(self._geometry);new_keys=set(geometry)
        result={'instances':len(canonical),'geometry_assets':len(geometry),'geometry_bytes':charged,
                'new_assets':len(new_keys-old_keys),'reused_assets':len(new_keys&old_keys),'released_assets':len(old_keys-new_keys)}
        self._instances=canonical;self._geometry=geometry;self.sequence=sequence
        return result
    def snapshot(self):
        return {'epoch':self.epoch,'sequence':self.sequence,'instances':dict(self._instances),'geometry':dict(self._geometry)}
