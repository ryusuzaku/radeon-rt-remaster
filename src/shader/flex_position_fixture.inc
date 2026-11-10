// Included inside the fixture's anonymous namespace; not linked into the proxy.
// Native oracle for the second admitted vertex program (docs/HL2_FLEX_POSITION_CONTRACT.md). The program bytes come from the
// user's own inventory on stdin; nothing from the title is embedded here. The unmodified program runs on a HAL device with
// hardware vertex processing and the title's exact three-stream declaration; a diagnostic pixel shader exports oT7.xyz (the
// model-space position) to an RGBA32F target. A second draw passes the CPU evaluator's clip/model results through a trivial
// vertex shader. Coverage must match exactly and every component within the position tolerance. Even variants bind stream 2
// with stride 0, as the title does; odd variants give every vertex its own flex value.
void FlexPositionFixture() {
    using namespace rrt::shader::position;
    std::string hex;char ch;while(std::cin.get(ch)&&ch!='\n'){Need(hex.size()<FlexProgramBytes*2,"program input bound");hex+=ch;}
    Need(hex.size()==FlexProgramBytes*2&&!std::cin.get(ch),"exact program input required");
    std::vector<DWORD> code(FlexProgramBytes/4);auto bytes=reinterpret_cast<unsigned char*>(code.data());
    auto digit=[](char c){Need((c>='0'&&c<='9')||(c>='a'&&c<='f'),"invalid hex");return c<='9'?c-'0':c-'a'+10;};
    for(unsigned i=0;i<FlexProgramBytes;++i)bytes[i]=static_cast<unsigned char>(digit(hex[i*2])*16+digit(hex[i*2+1]));
    AdmitFlex({bytes,FlexProgramBytes});auto changed=code;changed[1]^=1;
    Reject([&]{AdmitFlex({reinterpret_cast<const std::uint8_t*>(changed.data()),FlexProgramBytes});});
    Device source(true);auto d=source.device.Get();
    ComPtr<IDirect3DVertexShader9> native,pass;ComPtr<IDirect3DPixelShader9> pixel;Check(d->CreateVertexShader(code.data(),&native));
    auto compile=[](const char* text,const char* profile){ComPtr<ID3DBlob> blob,error;Check(D3DCompile(text,strlen(text),nullptr,nullptr,nullptr,"main",profile,D3DCOMPILE_OPTIMIZATION_LEVEL3,0,&blob,&error));return blob;};
    auto vs=compile("struct O{float4 p:POSITION;float4 m:TEXCOORD7;}; O main(float4 p:POSITION,float4 m:TEXCOORD7){O o;o.p=p;o.m=m;return o;}","vs_2_0");
    auto ps=compile("float4 main(float4 m:TEXCOORD7):COLOR{return float4(m.xyz,1);}","ps_2_0");
    Check(d->CreateVertexShader(static_cast<const DWORD*>(vs->GetBufferPointer()),&pass));Check(d->CreatePixelShader(static_cast<const DWORD*>(ps->GetBufferPointer()),&pixel));
    // The title's declaration, element for element (shader inventory, 783 of 783 draws of this program).
    D3DVERTEXELEMENT9 nl[]={{0,0,D3DDECLTYPE_FLOAT3,0,D3DDECLUSAGE_POSITION,0},{0,12,D3DDECLTYPE_UBYTE4,0,D3DDECLUSAGE_NORMAL,0},{0,16,D3DDECLTYPE_FLOAT2,0,D3DDECLUSAGE_TEXCOORD,0},
        {0,12,D3DDECLTYPE_UBYTE4,0,D3DDECLUSAGE_TANGENT,0},{1,0,D3DDECLTYPE_D3DCOLOR,0,D3DDECLUSAGE_COLOR,1},{2,0,D3DDECLTYPE_FLOAT4,0,D3DDECLUSAGE_POSITION,1},{2,16,D3DDECLTYPE_FLOAT3,0,D3DDECLUSAGE_NORMAL,1},D3DDECL_END()};
    D3DVERTEXELEMENT9 cl[]={{0,0,D3DDECLTYPE_FLOAT4,0,D3DDECLUSAGE_POSITION,0},{0,16,D3DDECLTYPE_FLOAT4,0,D3DDECLUSAGE_TEXCOORD,7},D3DDECL_END()};
    ComPtr<IDirect3DVertexDeclaration9> nd,cd;Check(d->CreateVertexDeclaration(nl,&nd));Check(d->CreateVertexDeclaration(cl,&cd));
    ComPtr<IDirect3DSurface9> target,read;Check(d->CreateRenderTarget(128,96,D3DFMT_A32B32G32R32F,D3DMULTISAMPLE_NONE,0,FALSE,&target,nullptr));
    Check(d->CreateOffscreenPlainSurface(128,96,D3DFMT_A32B32G32R32F,D3DPOOL_SYSTEMMEM,&read,nullptr));
    Check(d->SetRenderTarget(0,target.Get()));Check(d->SetDepthStencilSurface(nullptr));Configure(d);Check(d->SetPixelShader(pixel.Get()));
    struct Vertex {float p[3];std::uint8_t normal[4];float uv[2];float pad[2];};static_assert(sizeof(Vertex)==32);
    struct Flex {float p[4],n[3];};static_assert(sizeof(Flex)==28);
    const std::vector<Vertex> points={{{-.63f,-.57f,.3f},{128,64,200,255},{0,0},{}},{{.04f,.68f,.5f},{20,240,128,0},{1,0},{}},{{.71f,-.46f,.4f},{255,0,64,128},{1,1},{}}};
    const UINT pointCount=static_cast<UINT>(points.size());double worst=0;unsigned covered=0;
    for(unsigned variant=0;variant<24;++variant){
        const bool perVertex=variant%2;float t=static_cast<float>(variant)/23;
        FlexConstants c{};c.known.fill(true);
        c.rows={Vec{.05f*t,1.f-.15f*t,0,0},Vec{.5f*t,0,0,0},                                           // c0 (c0.y is the model w), c3 (cFlexScale)
            // c8..c11 (cViewProj). The z row changes sign across the triangle, so the near plane cuts it and the clipped edge
            // depends on clip z: coverage is otherwise blind to z, since only x, y and w place a pixel.
            Vec{.81f,.08f*t,0,-.1f*t},Vec{-.05f*t,.79f,0,.06f*t},Vec{.9f,.1f*t,.05f,.02f*t},Vec{.12f*t,0,.09f,1},
            Vec{1.1f,.3f*t,-.2f,.2f*t},Vec{-.4f*t,1.2f,.15f,-.1f*t},Vec{.1f,-.3f,.9f,.2f}};                   // c58..c60 (cModel[0])
        std::vector<Flex> flexes(perVertex?pointCount:1);
        for(std::size_t i=0;i<flexes.size();++i)flexes[i]={{.21f-.1f*float(i),-.13f+.07f*float(i)*t,.17f*t,9.f},{.3f,.4f,.5f}};
        for(unsigned missing=0;missing<9;++missing){auto bad=c;bad.known[missing]=false;Reject([&]{EvaluateFlex({0,0,0},{0,0,0},bad);});}
        auto bad=c;bad.rows[1][0]=std::numeric_limits<float>::infinity();Reject([&]{EvaluateFlex({0,0,0},{0,0,0},bad);});
        Reject([&]{EvaluateFlex({0,0,0},{std::numeric_limits<float>::quiet_NaN(),0,0},c);});
        auto huge=c;huge.rows[1][0]=std::numeric_limits<float>::max();Reject([&]{EvaluateFlex({0,0,0},{4,0,0},huge);});
        std::vector<Result> evaluated(pointCount);
        for(unsigned i=0;i<pointCount;++i){const auto& f=flexes[perVertex?i:0];evaluated[i]=EvaluateFlex({points[i].p[0],points[i].p[1],points[i].p[2]},{f.p[0],f.p[1],f.p[2]},c);}
        for(unsigned i=0;i<9;++i)Check(d->SetVertexShaderConstantF(FlexRegisters[i],c.rows[i].data(),1));
        // Inputs the program reads outside the position path: finite, otherwise arbitrary.
        const float other[4]={.25f,.5f,.75f,1};for(UINT r:{2u,13u,16u,48u,49u,52u,53u})Check(d->SetVertexShaderConstantF(r,other,1));
        auto render=[&](bool cpu){
            Check(d->Clear(0,nullptr,D3DCLEAR_TARGET,0,1,0));Check(d->SetVertexShader(cpu?pass.Get():native.Get()));Check(d->SetVertexDeclaration(cpu?cd.Get():nd.Get()));
            const UINT stride=cpu?sizeof(Result):sizeof(Vertex);const UINT offset=variant%4<2?8:16;const UINT base=variant%3?2:1;
            auto upload=[&](const void* data,UINT size,UINT length,ComPtr<IDirect3DVertexBuffer9>& vb){Check(d->CreateVertexBuffer(length,0,0,D3DPOOL_MANAGED,&vb,nullptr));
                void* ptr{};Check(vb->Lock(0,0,&ptr,0));memset(ptr,0,length);memcpy(static_cast<std::uint8_t*>(ptr)+(length-size),data,size);Check(vb->Unlock());};
            std::vector<std::uint8_t> storage(offset+(base+pointCount)*stride);memcpy(storage.data()+offset+base*stride,cpu?static_cast<const void*>(evaluated.data()):static_cast<const void*>(points.data()),pointCount*stride);
            ComPtr<IDirect3DVertexBuffer9> vb,colors,fb;Check(d->CreateVertexBuffer(static_cast<UINT>(storage.size()),0,0,D3DPOOL_MANAGED,&vb,nullptr));
            void* ptr{};Check(vb->Lock(0,0,&ptr,0));memcpy(ptr,storage.data(),storage.size());Check(vb->Unlock());
            const UINT flexOffset=perVertex?4:12,flexStride=perVertex?UINT(sizeof(Flex)):0;
            std::vector<std::uint8_t> flexStorage(flexOffset+(perVertex?(base+pointCount)*sizeof(Flex):sizeof(Flex)),0xcd);
            if(perVertex)memcpy(flexStorage.data()+flexOffset+base*sizeof(Flex),flexes.data(),pointCount*sizeof(Flex));else memcpy(flexStorage.data()+flexOffset,flexes.data(),sizeof(Flex));
            const std::uint32_t colorValues[8]={0xff808080,0xff204060,0xff406020,0xff602040,0xff808080,0xff204060,0xff406020,0xff602040};
            upload(colorValues,sizeof(colorValues),sizeof(colorValues),colors);
            Check(d->CreateVertexBuffer(static_cast<UINT>(flexStorage.size()),0,0,D3DPOOL_MANAGED,&fb,nullptr));Check(fb->Lock(0,0,&ptr,0));memcpy(ptr,flexStorage.data(),flexStorage.size());Check(fb->Unlock());
            std::vector<std::uint16_t> indices(pointCount+1);indices[0]=2;for(UINT i=0;i<pointCount;++i)indices[i+1]=static_cast<std::uint16_t>(i);
            ComPtr<IDirect3DIndexBuffer9> ib;Check(d->CreateIndexBuffer(static_cast<UINT>(indices.size()*2),0,D3DFMT_INDEX16,D3DPOOL_MANAGED,&ib,nullptr));Check(ib->Lock(0,0,&ptr,0));memcpy(ptr,indices.data(),indices.size()*2);Check(ib->Unlock());
            Check(d->SetStreamSource(0,vb.Get(),offset,stride));Check(d->SetIndices(ib.Get()));
            if(!cpu){Check(d->SetStreamSource(1,colors.Get(),0,4));Check(d->SetStreamSource(2,fb.Get(),flexOffset,flexStride));
                std::vector<std::uint8_t> mask(storage.size(),1),imask(indices.size()*2,1),fmask(flexStorage.size(),1);std::array<bool,61> known;known.fill(true);
                Evidence ve{vb.Get(),storage,mask},ie{ib.Get(),{reinterpret_cast<const std::uint8_t*>(indices.data()),indices.size()*2},imask},fe{fb.Get(),flexStorage,fmask};
                Draw draw{static_cast<INT>(base),0,pointCount,1,pointCount/3};
                auto record=position::Capture(d,draw,ve,ie,known,false,&fe);Need(record.find("\"flex\":{")!=std::string::npos&&record.find("\"constant_rows\":[0,3,8,9,10,11,58,59,60]")!=std::string::npos,"standalone flex capture");
                Reject([&]{position::Capture(d,draw,ve,ie,known,false,nullptr);});                      // no stream-2 evidence
                Reject([&]{position::Capture(d,draw,ve,ie,known,true,&fe);});                            // material capture refuses the program
                auto wrong=fe;wrong.resource=vb.Get();Reject([&]{position::Capture(d,draw,ve,ie,known,false,&wrong);});
                fmask[flexOffset+(perVertex?(base+1)*sizeof(Flex):0)+3]=0;Reject([&]{position::Capture(d,draw,ve,ie,known,false,&fe);});fmask.assign(fmask.size(),1);
                for(UINT r:{3u,8u,11u,58u}){auto missing=known;missing[r]=false;Reject([&]{position::Capture(d,draw,ve,ie,missing,false,&fe);});}
                Check(d->SetStreamSource(2,nullptr,0,0));Reject([&]{position::Capture(d,draw,ve,ie,known,false,&fe);});Check(d->SetStreamSource(2,fb.Get(),flexOffset,flexStride));}
            else{Check(d->SetStreamSource(1,nullptr,0,0));Check(d->SetStreamSource(2,nullptr,0,0));}
            Check(d->BeginScene());Check(d->DrawIndexedPrimitive(D3DPT_TRIANGLELIST,base,0,pointCount,1,pointCount/3));Check(d->EndScene());
            Check(d->GetRenderTargetData(target.Get(),read.Get()));D3DLOCKED_RECT lock{};Check(read->LockRect(&lock,nullptr,D3DLOCK_READONLY));std::vector<float> output(128*96*4);
            for(unsigned y=0;y<96;++y)memcpy(output.data()+y*128*4,static_cast<const char*>(lock.pBits)+y*lock.Pitch,128*16);Check(read->UnlockRect());return output;
        };
        auto actual=render(false),expected=render(true);unsigned count=0;
        for(unsigned i=0;i<actual.size();i+=4){Need(actual[i+3]==expected[i+3],"clip coverage mismatch");if(actual[i+3]!=0)++count;
            for(unsigned j=0;j<4;++j){Need(std::isfinite(actual[i+j])&&std::isfinite(expected[i+j]),"nonfinite GPU output");double error=std::abs(double(actual[i+j])-expected[i+j])/(1+std::abs(double(expected[i+j])));worst=std::max(worst,error);Need(error<=2e-4,"position interpolation mismatch");}}
        Need(count>100,"empty position oracle");covered+=count;
        // The near plane must have removed part of the triangle, or the case above would not be testing clip z.
        unsigned unclipped=0;{auto saved=c.rows[4];c.rows[4]={0,0,0,.5f};for(unsigned i=0;i<9;++i)Check(d->SetVertexShaderConstantF(FlexRegisters[i],c.rows[i].data(),1));
            auto full=render(false);for(unsigned i=3;i<full.size();i+=4)unclipped+=full[i]!=0;c.rows[4]=saved;}
        Need(unclipped>count+50,"near plane did not cut the oracle triangle");
    }
    std::cout<<"PASS exact HL2 flex VS hardware raster oracle: variants=24 covered="<<covered<<" max_normalized_error="<<worst<<" tolerance=0.0002; stride-0 and per-vertex flex, unknown/nonfinite/overflow/program/evidence negatives passed\n";
}
