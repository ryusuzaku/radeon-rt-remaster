// Included inside the fixture's anonymous namespace; not linked into the proxy.
void PositionFixture(bool recorded=false) {
    using namespace rrt::shader::position;
    std::string hex;char ch;while(std::cin.get(ch)&&ch!='\n'){Need(hex.size()<1224,"program input bound");hex+=ch;}
    Need(hex.size()==1224,"exact program input required");
    std::vector<DWORD> code(153);auto bytes=reinterpret_cast<unsigned char*>(code.data());
    auto digit=[](char c){Need((c>='0'&&c<='9')||(c>='a'&&c<='f'),"invalid hex");return c<='9'?c-'0':c-'a'+10;};
    for(unsigned i=0;i<612;++i)bytes[i]=static_cast<unsigned char>(digit(hex[i*2])*16+digit(hex[i*2+1]));
    Admit({bytes,612});auto changed=code;changed[1]^=1;
    Reject([&]{Admit({reinterpret_cast<const std::uint8_t*>(changed.data()),612});});
    Constants recordedConstants{};std::vector<std::array<float,3>> recordedPositions;
    if(recorded){
        auto readHex=[&](std::size_t maximum){std::string text;while(std::cin.get(ch)&&ch!='\n'){Need(text.size()<maximum*2,"recorded input bound");text+=ch;}Need(text.size()%2==0,"recorded hex alignment");std::vector<std::uint8_t> result(text.size()/2);for(std::size_t i=0;i<result.size();++i)result[i]=static_cast<std::uint8_t>(digit(text[i*2])*16+digit(text[i*2+1]));return result;};
        auto constants=readHex(128),positions=readHex(4096*3*12);
        Need(constants.size()==128&&!positions.empty()&&positions.size()%36==0,"recorded input shape");
        memcpy(recordedConstants.rows.data(),constants.data(),128);recordedConstants.known.fill(true);
        recordedPositions.resize(positions.size()/12);memcpy(recordedPositions.data(),positions.data(),positions.size());
        for(auto p:recordedPositions)Evaluate(p,recordedConstants); // Reject invalid values before GPU creation.
    }
    Need(!std::cin.get(ch),"trailing position input");
    Device source(true);auto d=source.device.Get();
    ComPtr<IDirect3DVertexShader9> native,pass;ComPtr<IDirect3DPixelShader9> pixel;
    Check(d->CreateVertexShader(code.data(),&native));
    // Same native instructions with a comment: deliberately outside exact-hash admission.
    auto commented=code;commented.insert(commented.end()-1,{0x0001fffe,0});
    ComPtr<IDirect3DVertexShader9> unselected;Check(d->CreateVertexShader(commented.data(),&unselected));
    auto compile=[](const char* text,const char* profile){ComPtr<ID3DBlob> blob,error;Check(D3DCompile(text,strlen(text),nullptr,nullptr,nullptr,"main",profile,D3DCOMPILE_OPTIMIZATION_LEVEL3,0,&blob,&error));return blob;};
    auto vs=compile("struct O{float4 p:POSITION;float4 m:TEXCOORD4;}; O main(float4 p:POSITION,float4 m:TEXCOORD4){O o;o.p=p;o.m=m;return o;}","vs_2_0");
    auto ps=compile("float4 main(float4 m:TEXCOORD4):COLOR{return float4(m.xyz,1);}","ps_2_0");
    Check(d->CreateVertexShader(static_cast<const DWORD*>(vs->GetBufferPointer()),&pass));Check(d->CreatePixelShader(static_cast<const DWORD*>(ps->GetBufferPointer()),&pixel));
    D3DVERTEXELEMENT9 nl[]={{0,0,D3DDECLTYPE_FLOAT3,0,D3DDECLUSAGE_POSITION,0},{0,12,D3DDECLTYPE_FLOAT2,0,D3DDECLUSAGE_TEXCOORD,0},{0,20,D3DDECLTYPE_FLOAT2,0,D3DDECLUSAGE_TEXCOORD,1},{0,28,D3DDECLTYPE_FLOAT4,0,D3DDECLUSAGE_COLOR,0},D3DDECL_END()};
    D3DVERTEXELEMENT9 cl[]={{0,0,D3DDECLTYPE_FLOAT4,0,D3DDECLUSAGE_POSITION,0},{0,16,D3DDECLTYPE_FLOAT4,0,D3DDECLUSAGE_TEXCOORD,4},D3DDECL_END()};
    ComPtr<IDirect3DVertexDeclaration9> nd,cd;Check(d->CreateVertexDeclaration(nl,&nd));Check(d->CreateVertexDeclaration(cl,&cd));
    wchar_t scopeCase[64]{};GetEnvironmentVariableW(L"RRT_POSITION_FIXTURE_CASE",scopeCase,64);std::wstring scopeMode=scopeCase;
    ComPtr<IDirect3DSurface9> target,read;Check(d->CreateRenderTarget(128,96,D3DFMT_A32B32G32R32F,D3DMULTISAMPLE_NONE,0,scopeMode==L"scopelockable",&target,nullptr));
    ComPtr<IDirect3DTexture9> scopeTexture;
    if(scopeMode==L"scopetexture"){Check(d->CreateTexture(128,96,1,D3DUSAGE_RENDERTARGET,D3DFMT_A32B32G32R32F,D3DPOOL_DEFAULT,&scopeTexture,nullptr));target.Reset();Check(scopeTexture->GetSurfaceLevel(0,&target));}
    Check(d->CreateOffscreenPlainSurface(128,96,D3DFMT_A32B32G32R32F,D3DPOOL_SYSTEMMEM,&read,nullptr));
    Check(d->SetRenderTarget(0,target.Get()));Check(d->SetDepthStencilSurface(nullptr));Configure(d);Check(d->SetPixelShader(pixel.Get()));
    if(scopeMode.rfind(L"color",0)==0){pixel.Reset();Check(d->CreatePixelShader(ColorProgram.data(),&pixel));Check(d->SetPixelShader(pixel.Get()));for(auto [state,value]:ColorExtraStates)Check(d->SetRenderState(state,value));}
    ComPtr<IDirect3DSurface9> scopeMrt;
    if(scopeMode==L"scopemrt"){Check(d->CreateRenderTarget(128,96,D3DFMT_A32B32G32R32F,D3DMULTISAMPLE_NONE,0,FALSE,&scopeMrt,nullptr));Check(d->SetRenderTarget(1,scopeMrt.Get()));}
    ComPtr<IDirect3DSurface9> evidenceDepth;wchar_t stateCase[64]{};GetEnvironmentVariableW(L"RRT_POSITION_FIXTURE_CASE",stateCase,64);
    if(std::wstring(stateCase)==L"depthstate"||std::wstring(stateCase)==L"cleardepth"){
        Check(d->CreateDepthStencilSurface(128,96,D3DFMT_D24S8,D3DMULTISAMPLE_NONE,0,TRUE,&evidenceDepth,nullptr));
        Check(d->SetDepthStencilSurface(evidenceDepth.Get()));Check(d->SetRenderState(D3DRS_ALPHABLENDENABLE,TRUE));
        Check(d->SetRenderState(D3DRS_SRCBLEND,D3DBLEND_ONE));Check(d->SetRenderState(D3DRS_DESTBLEND,D3DBLEND_ZERO));}
    struct Input {float p[3],uv[2],uv1[2],color[4];};
    std::vector<Input> points={{{-.63f,-.57f,.3f},{0,0},{0,0},{1,1,1,1}},{{.04f,.68f,.5f},{1,0},{0,1},{1,1,1,1}},{{.71f,-.46f,.4f},{1,1},{1,0},{1,1,1,1}}};
    if(recorded){points.resize(recordedPositions.size());for(std::size_t i=0;i<points.size();++i)memcpy(points[i].p,recordedPositions[i].data(),12);}
    const UINT pointCount=static_cast<UINT>(points.size());
    double worst=0;unsigned covered=0;
    ComPtr<IDirect3DVertexBuffer9> retainedVB;ComPtr<IDirect3DIndexBuffer9> retainedIB;
    for(unsigned variant=0;variant<(recorded?1u:24u);++variant){
        Constants c{};c.known.fill(true);float t=static_cast<float>(variant)/23;
        c.rows={Vec{.07f*t,1.f-.2f*t,0,0},Vec{.81f,.08f*t,0,-.1f*t},Vec{-.05f*t,.79f,0,.06f*t},Vec{0,0,.6f,.1f},Vec{.12f*t,0,.09f,1},Vec{1.1f,.3f,-.2f,2*t},Vec{-.4f,1.2f,.15f,-t},Vec{.1f,-.3f,.9f,.2f}};
        if(recorded)c=recordedConstants;
        for(unsigned missing=0;missing<8;++missing){auto bad=c;bad.known[missing]=false;Reject([&]{Evaluate({0,0,0},bad);});}
        auto bad=c;bad.rows[0][0]=std::numeric_limits<float>::infinity();Reject([&]{Evaluate({0,0,0},bad);});
        Reject([&]{Evaluate({std::numeric_limits<float>::quiet_NaN(),0,0},c);});
        auto huge=c;huge.rows[0][1]=std::numeric_limits<float>::max();Reject([&]{Evaluate({2,2,2},huge);});
        std::vector<Result> evaluated(pointCount);for(unsigned i=0;i<pointCount;++i)evaluated[i]=Evaluate({points[i].p[0],points[i].p[1],points[i].p[2]},c);
        for(unsigned i=0;i<8;++i){constexpr UINT registers[]={0,4,5,6,7,58,59,60};Check(d->SetVertexShaderConstantF(registers[i],c.rows[i].data(),1));}
        float extra[4]={0,0,0,1};Check(d->SetVertexShaderConstantF(12,extra,1));Check(d->SetVertexShaderConstantF(16,extra,1));
        auto render=[&](bool cpu){
            wchar_t captureCase[64]{};GetEnvironmentVariableW(L"RRT_POSITION_FIXTURE_CASE",captureCase,64);std::wstring mode=captureCase;
            if(mode==L"scopeaccess"||mode==L"scopeclosedaccess"){
                D3DLOCKED_RECT access{};Check(read->LockRect(&access,nullptr,0));
                if(mode==L"scopeclosedaccess")Check(read->UnlockRect());}
            if(mode==L"scopefailedaccess")Need(FAILED(read->UnlockRect()),"unlock without lock unexpectedly succeeded");
            if(mode==L"scopeaccessoverflow"){
                std::array<ComPtr<IDirect3DSurface9>,65> surfaces;
                for(auto& surface:surfaces){Check(d->CreateOffscreenPlainSurface(1,1,D3DFMT_A8R8G8B8,D3DPOOL_SYSTEMMEM,&surface,nullptr));D3DLOCKED_RECT access{};Check(surface->LockRect(&access,nullptr,0));}
                for(auto& surface:surfaces)Check(surface->UnlockRect());}
            if(mode==L"composition")Check(d->SetRenderState(D3DRS_ALPHAREF,0));
            Check(d->Clear(0,nullptr,D3DCLEAR_TARGET,0,1,0));Check(d->SetVertexShader(cpu?pass.Get():native.Get()));Check(d->SetVertexDeclaration(cpu?cd.Get():nd.Get()));
            if(mode.rfind(L"color",0)==0){Check(d->Clear(0,nullptr,D3DCLEAR_TARGET,0x40204060,1,0));float rgba[4]={.75f,.25f,.5f,.5f};Check(d->SetPixelShaderConstantF(0,rgba,1));
                Check(d->SetRenderState(D3DRS_ALPHABLENDENABLE,mode==L"colorblend"));Check(d->SetRenderState(D3DRS_SRCBLEND,D3DBLEND_SRCALPHA));Check(d->SetRenderState(D3DRS_DESTBLEND,D3DBLEND_INVSRCALPHA));Check(d->SetRenderState(D3DRS_BLENDOP,D3DBLENDOP_ADD));
                if(mode==L"colorfog")Check(d->SetRenderState(D3DRS_FOGENABLE,TRUE));}
            if(mode==L"clearpartial"){D3DRECT r{0,0,8,8};Check(d->Clear(1,&r,D3DCLEAR_TARGET,0,.25f,3));}
            if(mode==L"clearoversized"){D3DRECT rects[17]{};for(auto& r:rects)r={0,0,8,8};Check(d->Clear(17,rects,D3DCLEAR_TARGET,0,1,0));}
            if(mode==L"clearfailed")Need(FAILED(d->Clear(0,nullptr,D3DCLEAR_ZBUFFER,0,1,0)),"clear without depth unexpectedly succeeded");
            if(mode==L"cleardepth")Check(d->Clear(0,nullptr,D3DCLEAR_TARGET|D3DCLEAR_ZBUFFER|D3DCLEAR_STENCIL,0,.375f,7));
            const UINT stride=cpu?sizeof(Result):sizeof(Input);const UINT offset=variant%2?16:8;const UINT base=variant%2?2:1;
            std::vector<std::uint8_t> storage(offset+(base+pointCount)*stride);memcpy(storage.data()+offset+base*stride,cpu?static_cast<const void*>(evaluated.data()):static_cast<const void*>(points.data()),pointCount*stride);
            if(mode==L"large")storage.resize(256*1024);
            if(mode==L"reuse")storage.resize(4096);
            ComPtr<IDirect3DVertexBuffer9> vb=mode==L"reuse"?retainedVB:nullptr;ComPtr<IDirect3DIndexBuffer9> ib=mode==L"reuse"?retainedIB:nullptr;
            if(!vb)Check(d->CreateVertexBuffer(static_cast<UINT>(storage.size()),0,0,D3DPOOL_MANAGED,&vb,nullptr));
            void* ptr{};Check(vb->Lock(0,0,&ptr,0));memcpy(ptr,storage.data(),storage.size());Check(vb->Unlock());
            std::vector<std::uint16_t> indices(pointCount+1);indices[0]=2;for(UINT i=0;i<pointCount;++i)indices[i+1]=static_cast<std::uint16_t>(i);
            if(!ib)Check(d->CreateIndexBuffer(mode==L"reuse"?4096:static_cast<UINT>(indices.size()*2),0,D3DFMT_INDEX16,D3DPOOL_MANAGED,&ib,nullptr));Check(ib->Lock(0,static_cast<UINT>(indices.size()*2),&ptr,0));memcpy(ptr,indices.data(),indices.size()*2);Check(ib->Unlock());
            if(mode==L"reuse"){retainedVB=vb;retainedIB=ib;}
            Check(d->SetStreamSource(0,vb.Get(),offset,stride));Check(d->SetIndices(ib.Get()));
            if(!cpu){std::vector<std::uint8_t> mask(storage.size(),1),imask(indices.size()*2,1);std::array<bool,61> known;known.fill(true);
                Evidence ve{vb.Get(),storage,mask},ie{ib.Get(),{reinterpret_cast<const std::uint8_t*>(indices.data()),indices.size()*2},imask};Draw draw{static_cast<INT>(base),0,pointCount,1,pointCount/3};
                Need(!position::Capture(d,draw,ve,ie,known).empty(),"standalone position capture");
                mask[offset+base*stride]=0;Reject([&]{position::Capture(d,draw,ve,ie,known);});mask[offset+base*stride]=1;
                imask[2]=0;Reject([&]{position::Capture(d,draw,ve,ie,known);});imask[2]=1;
                auto bad=ve;bad.resource=nullptr;Reject([&]{position::Capture(d,draw,bad,ie,known);});
                auto invalid=draw;invalid.base=-10;Reject([&]{position::Capture(d,invalid,ve,ie,known);});invalid=draw;invalid.start=pointCount+2;Reject([&]{position::Capture(d,invalid,ve,ie,known);});
            }
            if(mode==L"stateblock"||mode==L"refresh"){ComPtr<IDirect3DStateBlock9> block;Check(d->CreateStateBlock(D3DSBT_ALL,&block));Check(block->Apply());
                if(mode==L"refresh")for(unsigned i=0;i<8;++i){constexpr UINT registers[]={0,4,5,6,7,58,59,60};Check(d->SetVertexShaderConstantF(registers[i],c.rows[i].data(),1));}}
            Check(d->BeginScene());if(mode==L"failed"&&!cpu&&variant==0)Need(FAILED(d->DrawIndexedPrimitive(static_cast<D3DPRIMITIVETYPE>(0),base,0,3,1,1)),"invalid draw succeeded");
            if(mode==L"writenonindexed")Check(d->DrawPrimitive(D3DPT_TRIANGLELIST,base,pointCount/3));
            if(mode==L"writeup"){
                Check(d->DrawPrimitiveUP(D3DPT_TRIANGLELIST,pointCount/3,cpu?static_cast<const void*>(evaluated.data()):static_cast<const void*>(points.data()),stride));
                Check(d->SetStreamSource(0,vb.Get(),offset,stride));}
            if(mode==L"writeindexedup"){
                Check(d->DrawIndexedPrimitiveUP(D3DPT_TRIANGLELIST,0,pointCount,pointCount/3,indices.data()+1,D3DFMT_INDEX16,cpu?static_cast<const void*>(evaluated.data()):static_cast<const void*>(points.data()),stride));
                Check(d->SetStreamSource(0,vb.Get(),offset,stride));Check(d->SetIndices(ib.Get()));}
            if(mode==L"writerejected"&&!cpu){Check(d->SetVertexShader(unselected.Get()));Check(d->DrawIndexedPrimitive(D3DPT_TRIANGLELIST,base,0,pointCount,1,pointCount/3));Check(d->SetVertexShader(native.Get()));}
            if(mode==L"writefill"||mode==L"writeoverflow")for(unsigned i=0;i<(mode==L"writeoverflow"?70u:1u);++i)Check(d->ColorFill(target.Get(),nullptr,0));
            if(mode==L"writefailed")Need(FAILED(d->ColorFill(nullptr,nullptr,0)),"invalid fill succeeded");
            if(mode==L"writelock"){
                D3DLOCKED_RECT locked{};Check(read->LockRect(&locked,nullptr,0));Check(read->UnlockRect());}
            if(mode==L"writecopy")Check(d->GetRenderTargetData(target.Get(),read.Get()));
            if(mode==L"writebinding")Check(d->SetRenderTarget(0,target.Get()));
            if(mode==L"selectedframes"&&!cpu){
                ComPtr<IDirect3DSurface9> rejectedTarget;D3DVIEWPORT9 saved{};Check(d->GetViewport(&saved));
                Check(d->CreateRenderTarget(8,8,D3DFMT_A32B32G32R32F,D3DMULTISAMPLE_NONE,0,FALSE,&rejectedTarget,nullptr));
                Check(d->SetRenderTarget(0,rejectedTarget.Get()));Check(d->DrawIndexedPrimitive(D3DPT_TRIANGLELIST,base,0,pointCount,1,pointCount/3));
                Check(d->SetRenderTarget(0,target.Get()));Check(d->SetViewport(&saved));}
            Check(d->DrawIndexedPrimitive(D3DPT_TRIANGLELIST,base,0,pointCount,1,pointCount/3));Check(d->EndScene());
            if(mode==L"colorblend"){
                Check(d->BeginScene());float rgba[4]={.25f,.75f,.125f,.25f};Check(d->SetPixelShaderConstantF(0,rgba,1));
                Check(d->DrawIndexedPrimitive(D3DPT_TRIANGLELIST,base,0,pointCount,1,pointCount/3));Check(d->EndScene());}
            if((mode==L"multiframes"||mode==L"multinopresent"||mode==L"multipresentlimit"||mode==L"composition")&&!cpu){
                // Repeated submissions test quota enforcement, not distinct object identity.
                Check(d->BeginScene());
                Need(FAILED(d->DrawIndexedPrimitive(static_cast<D3DPRIMITIVETYPE>(0),base,0,pointCount,1,pointCount/3)),"invalid draw succeeded");
                for(unsigned repeat=0;repeat<5;++repeat){
                    ComPtr<IDirect3DSurface9> alternate;
                    if(mode==L"composition"){
                        Check(d->CreateRenderTarget(128,96,D3DFMT_A32B32G32R32F,D3DMULTISAMPLE_NONE,0,FALSE,&alternate,nullptr));
                        Check(d->SetRenderTarget(0,alternate.Get()));Check(d->Clear(0,nullptr,D3DCLEAR_TARGET,0,1,0));Check(d->SetRenderState(D3DRS_ALPHAREF,repeat+1));}
                    Check(d->DrawIndexedPrimitive(D3DPT_TRIANGLELIST,base,0,pointCount,1,pointCount/3));
                    if(mode==L"composition")Check(d->SetRenderTarget(0,target.Get()));}
                Check(d->EndScene());}
            if(mode==L"scopeaccess")Check(read->UnlockRect());
            Check(d->GetRenderTargetData(target.Get(),read.Get()));D3DLOCKED_RECT lock{};Check(read->LockRect(&lock,nullptr,D3DLOCK_READONLY));std::vector<float> output(128*96*4);
            for(unsigned y=0;y<96;++y)memcpy(output.data()+y*128*4,static_cast<const char*>(lock.pBits)+y*lock.Pitch,128*16);Check(read->UnlockRect());return output;
        };
        auto actual=render(false),expected=render(true);unsigned count=0;
        for(unsigned i=0;i<actual.size();i+=4){Need(actual[i+3]==expected[i+3],"clip coverage mismatch");if(actual[i+3]!=0)++count;
            for(unsigned j=0;j<4;++j){Need(std::isfinite(actual[i+j])&&std::isfinite(expected[i+j]),"nonfinite GPU output");double error=std::abs(double(actual[i+j])-expected[i+j])/(1+std::abs(double(expected[i+j])));worst=std::max(worst,error);Need(error<=2e-4,"position interpolation mismatch");}}
        if(!recorded)Need(count>100,"empty position oracle");covered+=count;
        wchar_t intervalCase[64]{};GetEnvironmentVariableW(L"RRT_POSITION_FIXTURE_CASE",intervalCase,64);std::wstring intervalMode=intervalCase;
        if(intervalMode==L"frames"||intervalMode==L"selectedframes")Present(d);
        if(intervalMode==L"multiframes"||intervalMode==L"composition"||intervalMode==L"depthstate")Present(d);
        if(intervalMode==L"clearpartial"||intervalMode==L"clearoversized"||intervalMode==L"clearfailed"||intervalMode==L"cleardepth")Present(d);
        if(intervalMode.rfind(L"write",0)==0)Present(d);
        if(intervalMode.rfind(L"scope",0)==0)Present(d);
        if(intervalMode.rfind(L"color",0)==0)Present(d);
        if(intervalMode==L"multipresentlimit"&&variant==0)for(unsigned i=0;i<120;++i)Present(d);
        if(intervalMode==L"resetframes"){
            if(variant==1){
                Check(d->SetStreamSource(0,nullptr,0,0));Check(d->SetIndices(nullptr));
                ComPtr<IDirect3DSurface9> back;Check(d->GetBackBuffer(0,0,D3DBACKBUFFER_TYPE_MONO,&back));Check(d->SetRenderTarget(0,back.Get()));back.Reset();target.Reset();read.Reset();
                D3DPRESENT_PARAMETERS reset{};reset.Windowed=TRUE;reset.SwapEffect=D3DSWAPEFFECT_DISCARD;reset.hDeviceWindow=source.window;reset.BackBufferWidth=128;reset.BackBufferHeight=96;reset.BackBufferFormat=D3DFMT_X8R8G8B8;
                Check(d->Reset(&reset));
                Check(d->CreateRenderTarget(128,96,D3DFMT_A32B32G32R32F,D3DMULTISAMPLE_NONE,0,FALSE,&target,nullptr));
                Check(d->CreateOffscreenPlainSurface(128,96,D3DFMT_A32B32G32R32F,D3DPOOL_SYSTEMMEM,&read,nullptr));
                Check(d->SetRenderTarget(0,target.Get()));Check(d->SetDepthStencilSurface(nullptr));Configure(d);Check(d->SetPixelShader(pixel.Get()));
            }else Present(d);
        }
        if(intervalMode==L"swapframes"){ComPtr<IDirect3DSwapChain9> chain;Check(d->GetSwapChain(0,&chain));Present(chain.Get());}
        if(intervalMode==L"presentlimit"&&variant==0)for(unsigned i=0;i<120;++i)Present(d);
    }
    if(recorded)std::cout<<"{\"status\":\""<<(covered?"matched":"empty")<<"\",\"covered\":"<<covered<<",\"max_normalized_error\":"<<worst<<",\"tolerance\":0.0002,\"width\":128,\"height\":96}\n";
    else std::cout<<"PASS exact HL2 VS hardware raster oracle: variants=24 covered="<<covered<<" max_normalized_error="<<worst<<" tolerance=0.0002; unknown/nonfinite/overflow/program negatives passed\n";
}
