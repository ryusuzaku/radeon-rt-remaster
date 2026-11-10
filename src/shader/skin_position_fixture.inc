// Included inside the fixture's anonymous namespace; not linked into the proxy.
// Native oracle for the third admitted vertex program, the skinned one (docs/HL2_SKINNED_POSITION_CONTRACT.md). As for the flex
// program: the bytes come from the user's own inventory on stdin, the unmodified program runs on a HAL device with hardware vertex
// processing and the title's exact declaration, a diagnostic pixel shader exports oT6.xyz (the blended model position), and a
// second draw passes the CPU evaluator's results through a trivial program. Every vertex reads three distinct bones from a full
// 53-bone palette with uneven weights; odd variants enable all four light branches, which must not disturb the position.
void SkinPositionFixture() {
    using namespace rrt::shader::position;
    std::string hex;char ch;while(std::cin.get(ch)&&ch!='\n'){Need(hex.size()<SkinProgramBytes*2,"program input bound");hex+=ch;}
    Need(hex.size()==SkinProgramBytes*2&&!std::cin.get(ch),"exact program input required");
    std::vector<DWORD> code(SkinProgramBytes/4);auto bytes=reinterpret_cast<unsigned char*>(code.data());
    auto digit=[](char c){Need((c>='0'&&c<='9')||(c>='a'&&c<='f'),"invalid hex");return c<='9'?c-'0':c-'a'+10;};
    for(unsigned i=0;i<SkinProgramBytes;++i)bytes[i]=static_cast<unsigned char>(digit(hex[i*2])*16+digit(hex[i*2+1]));
    AdmitSkin({bytes,SkinProgramBytes});auto changed=code;changed[1]^=1;
    Reject([&]{AdmitSkin({reinterpret_cast<const std::uint8_t*>(changed.data()),SkinProgramBytes});});
    // Bone selection: bytes (B,G,R) of the D3DCOLOR give a0 = (G,B,R)*3; byte 53 is past cModel[52].
    Need(SkinBones(0x00341234u)==std::array<unsigned,3>{0x12*3,0x34*3,0x34*3},"bone byte order");Reject([&]{SkinBones(0x00000035u);});
    Device source(true);auto d=source.device.Get();
    ComPtr<IDirect3DVertexShader9> native,pass;ComPtr<IDirect3DPixelShader9> pixel;Check(d->CreateVertexShader(code.data(),&native));
    auto compile=[](const char* text,const char* profile){ComPtr<ID3DBlob> blob,error;Check(D3DCompile(text,strlen(text),nullptr,nullptr,nullptr,"main",profile,D3DCOMPILE_OPTIMIZATION_LEVEL3,0,&blob,&error));return blob;};
    auto vs=compile("struct O{float4 p:POSITION;float4 m:TEXCOORD6;}; O main(float4 p:POSITION,float4 m:TEXCOORD6){O o;o.p=p;o.m=m;return o;}","vs_2_0");
    auto ps=compile("float4 main(float4 m:TEXCOORD6):COLOR{return float4(m.xyz,1);}","ps_2_0");
    Check(d->CreateVertexShader(static_cast<const DWORD*>(vs->GetBufferPointer()),&pass));Check(d->CreatePixelShader(static_cast<const DWORD*>(ps->GetBufferPointer()),&pixel));
    // The title's declaration, element for element (shader inventory, every draw of this program).
    D3DVERTEXELEMENT9 nl[]={{0,0,D3DDECLTYPE_FLOAT3,0,D3DDECLUSAGE_POSITION,0},{0,12,D3DDECLTYPE_SHORT2,0,D3DDECLUSAGE_BLENDWEIGHT,0},{0,16,D3DDECLTYPE_D3DCOLOR,0,D3DDECLUSAGE_BLENDINDICES,0},
        {0,20,D3DDECLTYPE_UBYTE4,0,D3DDECLUSAGE_NORMAL,0},{0,24,D3DDECLTYPE_FLOAT2,0,D3DDECLUSAGE_TEXCOORD,0},{0,20,D3DDECLTYPE_UBYTE4,0,D3DDECLUSAGE_TANGENT,0},
        {2,0,D3DDECLTYPE_FLOAT4,0,D3DDECLUSAGE_POSITION,1},{2,16,D3DDECLTYPE_FLOAT3,0,D3DDECLUSAGE_NORMAL,1},D3DDECL_END()};
    D3DVERTEXELEMENT9 cl[]={{0,0,D3DDECLTYPE_FLOAT4,0,D3DDECLUSAGE_POSITION,0},{0,16,D3DDECLTYPE_FLOAT4,0,D3DDECLUSAGE_TEXCOORD,6},D3DDECL_END()};
    ComPtr<IDirect3DVertexDeclaration9> nd,cd;Check(d->CreateVertexDeclaration(nl,&nd));Check(d->CreateVertexDeclaration(cl,&cd));
    ComPtr<IDirect3DSurface9> target,read;Check(d->CreateRenderTarget(128,96,D3DFMT_A32B32G32R32F,D3DMULTISAMPLE_NONE,0,FALSE,&target,nullptr));
    Check(d->CreateOffscreenPlainSurface(128,96,D3DFMT_A32B32G32R32F,D3DPOOL_SYSTEMMEM,&read,nullptr));
    Check(d->SetRenderTarget(0,target.Get()));Check(d->SetDepthStencilSurface(nullptr));Configure(d);Check(d->SetPixelShader(pixel.Get()));
    struct Vertex {float p[3];std::int16_t w[2];std::uint32_t bones;std::uint8_t normal[4];float uv[2];};static_assert(sizeof(Vertex)==32);
    struct Flex {float p[4],n[3];};static_assert(sizeof(Flex)==28);
    // Bytes are (B,G,R,A): three distinct bones per vertex, bone 52 (the last) among them, and weights well away from 1/3 each.
    const std::vector<Vertex> points={{{-.63f,-.57f,.3f},{12000,-9000},0x00341105u,{128,64,200,255},{0,0}},
        {{.04f,.68f,.5f},{-20000,15000},0x00022a07u,{20,240,128,0},{1,0}},{{.71f,-.46f,.4f},{3000,22000},0x00301a0bu,{255,0,64,128},{1,1}}};
    const UINT pointCount=static_cast<UINT>(points.size());double worst=0;unsigned covered=0;
    for(unsigned variant=0;variant<24;++variant){
        const bool perVertex=variant%2,lights=(variant/2)%2;float t=static_cast<float>(variant)/23;
        SkinConstants c{};c.known.fill(true);c.paletteKnown.fill(true);
        c.rows={Vec{0,1.f-.1f*t,2,.5f},Vec{.4f*t,0,0,0},                                                            // c0, c3 (cFlexScale)
            Vec{.81f,.08f*t,0,-.1f*t},Vec{-.05f*t,.79f,0,.06f*t},Vec{.9f,.1f*t,.05f,.02f*t},Vec{.12f*t,0,.09f,1}};  // c8..c11; z row cuts the triangle
        for(unsigned bone=0;bone<53;++bone){float a=.05f*float(bone)+t,s=std::sin(a),k=std::cos(a),u=float(bone%7)*.03f;
            c.palette[bone*3]={k*(1+u),-s,.1f*u,.02f*float(bone%5)-.04f};c.palette[bone*3+1]={s,k,-.05f,.03f*float(bone%3)};c.palette[bone*3+2]={.05f*u,.1f,1-u,.01f*float(bone%4)};}
        std::vector<Flex> flexes(perVertex?pointCount:1);
        for(std::size_t i=0;i<flexes.size();++i)flexes[i]={{.21f-.1f*float(i),-.13f+.07f*float(i)*t,.17f*t,9.f},{.3f,.4f,.5f}};
        auto input=[&](unsigned i){const auto& v=points[i];const auto& f=flexes[perVertex?i:0];return SkinInput{{v.p[0],v.p[1],v.p[2]},{f.p[0],f.p[1],f.p[2]},{v.w[0],v.w[1]},v.bones};};
        for(unsigned missing=0;missing<6;++missing){auto bad=c;bad.known[missing]=false;Reject([&]{EvaluateSkin(input(0),bad);});}
        {auto bad=c;bad.paletteKnown[0x34*3+2]=false;Reject([&]{EvaluateSkin(input(0),bad);});auto ok=c;ok.paletteKnown[40*3]=false;EvaluateSkin(input(0),ok);} // only referenced bones matter
        {auto bad=c;bad.palette[0x11*3][1]=std::numeric_limits<float>::infinity();Reject([&]{EvaluateSkin(input(0),bad);});}
        {auto bad=input(0);bad.flex[0]=std::numeric_limits<float>::quiet_NaN();Reject([&]{EvaluateSkin(bad,c);});bad=input(0);bad.indices=0x00000035u;Reject([&]{EvaluateSkin(bad,c);});}
        std::vector<Result> evaluated(pointCount);for(unsigned i=0;i<pointCount;++i)evaluated[i]=EvaluateSkin(input(i),c);
        // The bones move the vertices, so place the clip-z plane from their blended model x (which c10 does not affect): z changes
        // sign mid-triangle and the near plane cuts it, which is what makes coverage sensitive to clip z.
        {float lo=evaluated[0].model[0],hi=lo;for(const auto& e:evaluated){lo=std::min(lo,e.model[0]);hi=std::max(hi,e.model[0]);}
            c.rows[4]={1,.1f*t,0,-(lo+hi)/2};for(unsigned i=0;i<pointCount;++i)evaluated[i]=EvaluateSkin(input(i),c);}
        auto upload=[&](){for(unsigned i=0;i<6;++i)Check(d->SetVertexShaderConstantF(SkinRegisters[i],c.rows[i].data(),1));Check(d->SetVertexShaderConstantF(PaletteStart,c.palette[0].data(),PaletteRows));};upload();
        // Inputs outside the position path: finite, otherwise arbitrary; the light constants c27..c46 and the four light booleans.
        const float other[4]={.25f,.5f,.75f,1};for(UINT r:{2u,13u,16u,48u,49u,52u,53u})Check(d->SetVertexShaderConstantF(r,other,1));
        for(UINT r=27;r<47;++r)Check(d->SetVertexShaderConstantF(r,other,1));
        const BOOL enabled[4]={lights,lights,lights,lights};Check(d->SetVertexShaderConstantB(0,enabled,4));
        auto render=[&](bool cpu){
            Check(d->Clear(0,nullptr,D3DCLEAR_TARGET,0,1,0));Check(d->SetVertexShader(cpu?pass.Get():native.Get()));Check(d->SetVertexDeclaration(cpu?cd.Get():nd.Get()));
            const UINT stride=cpu?sizeof(Result):sizeof(Vertex);const UINT offset=variant%4<2?8:16;const UINT base=variant%3?2:1;
            std::vector<std::uint8_t> storage(offset+(base+pointCount)*stride);memcpy(storage.data()+offset+base*stride,cpu?static_cast<const void*>(evaluated.data()):static_cast<const void*>(points.data()),pointCount*stride);
            ComPtr<IDirect3DVertexBuffer9> vb,fb;Check(d->CreateVertexBuffer(static_cast<UINT>(storage.size()),0,0,D3DPOOL_MANAGED,&vb,nullptr));
            void* ptr{};Check(vb->Lock(0,0,&ptr,0));memcpy(ptr,storage.data(),storage.size());Check(vb->Unlock());
            const UINT flexOffset=perVertex?4:12,flexStride=perVertex?UINT(sizeof(Flex)):0;
            std::vector<std::uint8_t> flexStorage(flexOffset+(perVertex?(base+pointCount)*sizeof(Flex):sizeof(Flex)),0xcd);
            if(perVertex)memcpy(flexStorage.data()+flexOffset+base*sizeof(Flex),flexes.data(),pointCount*sizeof(Flex));else memcpy(flexStorage.data()+flexOffset,flexes.data(),sizeof(Flex));
            Check(d->CreateVertexBuffer(static_cast<UINT>(flexStorage.size()),0,0,D3DPOOL_MANAGED,&fb,nullptr));Check(fb->Lock(0,0,&ptr,0));memcpy(ptr,flexStorage.data(),flexStorage.size());Check(fb->Unlock());
            std::vector<std::uint16_t> indices(pointCount+1);indices[0]=2;for(UINT i=0;i<pointCount;++i)indices[i+1]=static_cast<std::uint16_t>(i);
            ComPtr<IDirect3DIndexBuffer9> ib;Check(d->CreateIndexBuffer(static_cast<UINT>(indices.size()*2),0,D3DFMT_INDEX16,D3DPOOL_MANAGED,&ib,nullptr));Check(ib->Lock(0,0,&ptr,0));memcpy(ptr,indices.data(),indices.size()*2);Check(ib->Unlock());
            Check(d->SetStreamSource(0,vb.Get(),offset,stride));Check(d->SetIndices(ib.Get()));
            if(!cpu){Check(d->SetStreamSource(2,fb.Get(),flexOffset,flexStride));
                std::vector<std::uint8_t> mask(storage.size(),1),imask(indices.size()*2,1),fmask(flexStorage.size(),1);std::array<bool,256> known;known.fill(true);
                Evidence ve{vb.Get(),storage,mask},ie{ib.Get(),{reinterpret_cast<const std::uint8_t*>(indices.data()),indices.size()*2},imask},fe{fb.Get(),flexStorage,fmask};
                Draw draw{static_cast<INT>(base),0,pointCount,1,pointCount/3};
                auto record=position::Capture(d,draw,ve,ie,known,false,&fe);
                Need(record.find("\"bones\":{\"offsets\":[6,15,21,33,51,78,126,144,156]")!=std::string::npos&&record.find("\"constant_rows\":[0,3,8,9,10,11]")!=std::string::npos&&record.find("\"blend\":{\"weights_offset\":12,\"indices_offset\":16")!=std::string::npos,"standalone skinned capture");
                Reject([&]{position::Capture(d,draw,ve,ie,known,false,nullptr);});
                Reject([&]{position::Capture(d,draw,ve,ie,known,true,&fe);});
                for(UINT r:{3u,10u,PaletteStart+0x34*3+2,PaletteStart+0x0b*3}){auto missing=known;missing[r]=false;Reject([&]{position::Capture(d,draw,ve,ie,missing,false,&fe);});}
                {auto unused=known;unused[PaletteStart+40*3]=false;position::Capture(d,draw,ve,ie,unused,false,&fe);}  // an unreferenced bone may be unknown
                for(std::size_t hole:{std::size_t(12),std::size_t(17)}){auto at=offset+(base+1)*stride+hole;mask[at]=0;Reject([&]{position::Capture(d,draw,ve,ie,known,false,&fe);});mask[at]=1;}}
            else Check(d->SetStreamSource(2,nullptr,0,0));
            Check(d->BeginScene());Check(d->DrawIndexedPrimitive(D3DPT_TRIANGLELIST,base,0,pointCount,1,pointCount/3));Check(d->EndScene());
            Check(d->GetRenderTargetData(target.Get(),read.Get()));D3DLOCKED_RECT lock{};Check(read->LockRect(&lock,nullptr,D3DLOCK_READONLY));std::vector<float> output(128*96*4);
            for(unsigned y=0;y<96;++y)memcpy(output.data()+y*128*4,static_cast<const char*>(lock.pBits)+y*lock.Pitch,128*16);Check(read->UnlockRect());return output;
        };
        auto actual=render(false),expected=render(true);unsigned count=0;
        for(unsigned i=0;i<actual.size();i+=4){Need(actual[i+3]==expected[i+3],"clip coverage mismatch");if(actual[i+3]!=0)++count;
            for(unsigned j=0;j<4;++j){Need(std::isfinite(actual[i+j])&&std::isfinite(expected[i+j]),"nonfinite GPU output");double error=std::abs(double(actual[i+j])-expected[i+j])/(1+std::abs(double(expected[i+j])));worst=std::max(worst,error);Need(error<=2e-4,"position interpolation mismatch");}}
        Need(count>100,"empty position oracle");covered+=count;
        unsigned unclipped=0;{auto saved=c.rows[4];c.rows[4]={0,0,0,.5f};upload();for(unsigned i=0;i<pointCount;++i)evaluated[i]=EvaluateSkin(input(i),c);
            auto full=render(false);for(unsigned i=3;i<full.size();i+=4)unclipped+=full[i]!=0;c.rows[4]=saved;}
        Need(unclipped>count+50,"near plane did not cut the oracle triangle");
    }
    std::cout<<"PASS exact HL2 skinned VS hardware raster oracle: variants=24 covered="<<covered<<" max_normalized_error="<<worst<<" tolerance=0.0002; three-bone blend, stride-0 and per-vertex flex, light branches, unknown/nonfinite/bone-range/program/evidence negatives passed\n";
}
