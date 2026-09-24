"""Bounded, hash-addressed sibling mip store. Ledger data never supplies paths."""
import hashlib
from pathlib import Path
import stat

class TextureAssets:
    def __init__(self,ledger):
        self.root=Path(str(ledger)+'.assets')
        self.cache={}
        self.total=0
    def read(self,digest,size):
        def need(ok,message):
            if not ok:raise ValueError('texture asset: '+message)
        need(type(digest) is str and len(digest)==64 and all(c in '0123456789abcdef' for c in digest),'digest')
        need(type(size) is int and 0<size<=16*1024*1024,'size')
        if digest in self.cache:
            data=self.cache[digest];need(len(data)==size,'conflicting size');return data
        need(len(self.cache)<512 and self.total+size<=256*1024*1024,'session budget')
        root=self.root.stat(follow_symlinks=False)
        need(stat.S_ISDIR(root.st_mode) and not getattr(root,'st_file_attributes',0)&0x400,'asset directory')
        path=self.root/(digest+'.bin');before=path.stat(follow_symlinks=False)
        need(stat.S_ISREG(before.st_mode) and not getattr(before,'st_file_attributes',0)&0x400 and before.st_size==size,'regular file/size')
        with path.open('rb') as stream:data=stream.read(size+1)
        need(len(data)==size and hashlib.sha256(data).hexdigest()==digest,'content hash')
        self.cache[digest]=data;self.total+=size;return data
