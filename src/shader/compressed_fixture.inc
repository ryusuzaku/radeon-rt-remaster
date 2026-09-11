// Known compressed blocks, independently checked by the Python fixture.
std::vector<std::uint8_t> CompressedBlock(D3DFORMAT format,UINT x,UINT y,UINT level,UINT slot){
    std::vector<std::uint8_t> out;auto append=[&](std::uint64_t value,unsigned count){for(unsigned i=0;i<count;++i)out.push_back(std::uint8_t(value>>(i*8)));};
    UINT seed=x+y*7+level*3+slot*5;DWORD selectors=0;for(UINT i=0;i<16;++i)selectors|=((i+seed)%4)<<(i*2);
    if(format==D3DFMT_DXT1){append(0x07e0,2);append(0xf800,2);}
    else{
        if(format==D3DFMT_DXT3||format==D3DFMT_DXT2){std::uint64_t alpha=0;for(UINT i=0;i<16;++i)alpha|=std::uint64_t((i+seed+8)%16)<<(i*4);append(alpha,8);}
        else{append(seed%2?224:32,1);append(seed%2?32:224,1);std::uint64_t alpha=0;for(UINT i=0;i<16;++i)alpha|=std::uint64_t((i+seed)%8)<<(i*3);append(alpha,6);}
        append(0xf800-(seed%8)*0x800,2);append(0x07e0,2);
    }
    append(selectors,4);return out;
}
void FillCompressed(IDirect3DTexture9* texture,UINT slot,bool partial,UINT generation=0,DWORD flags=0){
    for(UINT level=0;level<texture->GetLevelCount();++level){D3DSURFACE_DESC d{};Check(texture->GetLevelDesc(level,&d));
        UINT columns=(d.Width+3)/4,rows=(d.Height+3)/4,unitBytes=d.Format==D3DFMT_DXT1?8:16;
        // Four quadrants exercise both horizontal and vertical offsets; tiny
        // tails use whole-level locks (nullptr) rather than partial rectangles.
        UINT nx=partial&&d.Width>=8?2:1,ny=partial&&d.Height>=8?2:1;
        for(UINT py=0;py<ny;++py)for(UINT px=0;px<nx;++px){
            UINT left=columns*px/nx,right=columns*(px+1)/nx,top=rows*py/ny,bottom=rows*(py+1)/ny;
            RECT rect{LONG(left*4),LONG(top*4),LONG(right*4),LONG(bottom*4)};D3DLOCKED_RECT lock{};
            Check(texture->LockRect(level,&lock,nx==1&&ny==1?nullptr:&rect,flags));Need(lock.Pitch>0&&UINT(lock.Pitch)>=(right-left)*unitBytes,"compressed fixture pitch");
            for(UINT y=top;y<bottom;++y)for(UINT x=left;x<right;++x){auto block=CompressedBlock(d.Format,x,y,level+generation,slot);memcpy(static_cast<char*>(lock.pBits)+(y-top)*lock.Pitch+(x-left)*unitBytes,block.data(),block.size());}
            Check(texture->UnlockRect(level));
        }
    }
}
