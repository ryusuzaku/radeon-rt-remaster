// Exact pinned VS, real audited input layout, independently evaluated passthrough.
#include "compressed_fixture.inc"
#include "surface_fixture.inc"
void MaterialFixture(bool paired=false){
    using namespace rrt::shader::position;
    std::string hex,pixelHex;std::getline(std::cin,hex);Need(hex.size()==1224,"material shader input");if(paired){std::getline(std::cin,pixelHex);Need(pixelHex.size()==3584,"paired pixel input");}char trailing;Need(!std::cin.get(trailing),"material trailing input");
    std::array<DWORD,153> code{};auto bytes=reinterpret_cast<unsigned char*>(code.data());
    auto digit=[](char c){Need((c>='0'&&c<='9')||(c>='a'&&c<='f'),"material hex");return c<='9'?c-'0':c-'a'+10;};
    for(unsigned i=0;i<612;++i)bytes[i]=static_cast<unsigned char>(digit(hex[i*2])*16+digit(hex[i*2+1]));Admit({bytes,612});
    Device source(true);auto d=source.device.Get();ComPtr<IDirect3DVertexShader9> native,pass;
    Check(d->CreateVertexShader(code.data(),&native));
    std::array<DWORD,448> pixelCode{};ComPtr<IDirect3DPixelShader9> pairedPixel;
    if(paired){auto raw=reinterpret_cast<unsigned char*>(pixelCode.data());for(unsigned i=0;i<1792;++i)raw[i]=static_cast<unsigned char>(digit(pixelHex[i*2])*16+digit(pixelHex[i*2+1]));Check(d->CreatePixelShader(pixelCode.data(),&pairedPixel));}
    auto compile=[](const char* text,const char* profile){ComPtr<ID3DBlob> blob,error;Check(D3DCompile(text,strlen(text),nullptr,nullptr,nullptr,"main",profile,D3DCOMPILE_OPTIMIZATION_LEVEL3,0,&blob,&error));return blob;};
    auto vs=compile("struct V{float4 p:POSITION;float4 uv:TEXCOORD0;float4 col:COLOR0;float4 m:TEXCOORD4;float4 fog:COLOR1;};struct O{float4 p:POSITION;float2 u:TEXCOORD0;float2 v:TEXCOORD2;float4 col:COLOR0;float4 m:TEXCOORD4;float4 fog:COLOR1;};O main(V v){O o;o.p=v.p;o.u=v.uv.xy;o.v=v.uv.zw;o.col=v.col;o.m=v.m;o.fog=v.fog;return o;}","vs_2_0");
    Check(d->CreateVertexShader(static_cast<const DWORD*>(vs->GetBufferPointer()),&pass));
    const char* probes[]={"float4 main(float2 u:TEXCOORD0,float2 v:TEXCOORD2):COLOR{return float4(u,v);}","float4 main(float4 c:COLOR0):COLOR{return c;}","float4 main(float4 m:TEXCOORD4,float4 f:COLOR1):COLOR{return float4(m.w,f.xy,1);}"};
    struct Input{float p[3],normal[3];DWORD color;float uv[4],padding;};static_assert(sizeof(Input)==48);
    struct Cpu{Vec clip,uv,color,model,fog;};
    const std::array<Input,3> points={{{{-.8f,-.7f,.2f},{0,0,1},0x204080c0,{-1,.2f,.1f,1.5f},0},{{0,.8f,.4f},{0,1,0},0x8060c020,{.6f,2,.8f,-.2f},0},{{.8f,-.65f,.7f},{1,0,0},0xe0f03090,{1.3f,-.5f,2,.6f},0}}};
    D3DVERTEXELEMENT9 nl[]={{0,0,D3DDECLTYPE_FLOAT3,0,D3DDECLUSAGE_POSITION,0},{0,12,D3DDECLTYPE_FLOAT3,0,D3DDECLUSAGE_NORMAL,0},{0,24,D3DDECLTYPE_D3DCOLOR,0,D3DDECLUSAGE_COLOR,0},{0,28,D3DDECLTYPE_FLOAT2,0,D3DDECLUSAGE_TEXCOORD,0},{0,36,D3DDECLTYPE_FLOAT2,0,D3DDECLUSAGE_TEXCOORD,1},D3DDECL_END()};
    D3DVERTEXELEMENT9 cl[]={{0,0,D3DDECLTYPE_FLOAT4,0,D3DDECLUSAGE_POSITION,0},{0,16,D3DDECLTYPE_FLOAT4,0,D3DDECLUSAGE_TEXCOORD,0},{0,32,D3DDECLTYPE_FLOAT4,0,D3DDECLUSAGE_COLOR,0},{0,48,D3DDECLTYPE_FLOAT4,0,D3DDECLUSAGE_TEXCOORD,4},{0,64,D3DDECLTYPE_FLOAT4,0,D3DDECLUSAGE_COLOR,1},D3DDECL_END()};
    ComPtr<IDirect3DVertexDeclaration9> nd,cd;Check(d->CreateVertexDeclaration(nl,&nd));Check(d->CreateVertexDeclaration(cl,&cd));
    ComPtr<IDirect3DVertexBuffer9> vb;ComPtr<IDirect3DIndexBuffer9> ib;Check(d->CreateVertexBuffer(sizeof(points),0,0,D3DPOOL_MANAGED,&vb,nullptr));Check(d->CreateIndexBuffer(6,0,D3DFMT_INDEX16,D3DPOOL_MANAGED,&ib,nullptr));
    void* pointer{};Check(vb->Lock(0,0,&pointer,0));memcpy(pointer,points.data(),sizeof(points));Check(vb->Unlock());std::array<std::uint16_t,3> indices={0,1,2};Check(ib->Lock(0,0,&pointer,0));memcpy(pointer,indices.data(),6);Check(ib->Unlock());
    ComPtr<IDirect3DSurface9> target,read;Check(d->CreateRenderTarget(128,96,D3DFMT_A32B32G32R32F,D3DMULTISAMPLE_NONE,0,FALSE,&target,nullptr));Check(d->CreateOffscreenPlainSurface(128,96,D3DFMT_A32B32G32R32F,D3DPOOL_SYSTEMMEM,&read,nullptr));Check(d->SetRenderTarget(0,target.Get()));Check(d->SetDepthStencilSurface(nullptr));Configure(d);
    wchar_t mode[64]{};GetEnvironmentVariableW(L"RRT_MATERIAL_FIXTURE_CASE",mode,64);double worst=0;unsigned covered=0;
    if(std::wstring(mode)==L"unsupportedvs"){std::vector<DWORD> changed(code.begin(),code.end());changed.insert(changed.end()-1,D3DSIO_NOP);native.Reset();Check(d->CreateVertexShader(changed.data(),&native));}
    std::wstring modeName(mode);bool uploading=modeName.rfind(L"upload-",0)==0;if(uploading)modeName=modeName.substr(7);bool compressed=modeName.rfind(L"dxt",0)==0;std::vector<float> nativeEvidence;
    std::array<ComPtr<IDirect3DTexture9>,2> textures;std::vector<ComPtr<IDirect3DTexture9>> budgetTextures;
    auto fillTexture=[&](unsigned slot,bool partial,UINT generation=0,DWORD flags=0){for(UINT level=0;level<textures[slot]->GetLevelCount();++level){D3DSURFACE_DESC desc{};Check(textures[slot]->GetLevelDesc(level,&desc));
        unsigned parts=partial&&desc.Width>1?2:1;for(unsigned part=0;part<parts;++part){RECT rect{LONG(desc.Width*part/parts),0,LONG(desc.Width*(part+1)/parts),LONG(desc.Height)};D3DLOCKED_RECT lock{};Check(textures[slot]->LockRect(level,&lock,&rect,flags));
            for(LONG y=rect.top;y<rect.bottom;++y)for(LONG x=rect.left;x<rect.right;++x){DWORD value=0xff000000|((32+x*13+(level+generation)*7)<<16)|((40+y*17+slot*31)<<8)|(60+(level+generation)*19);memcpy(static_cast<char*>(lock.pBits)+(y-rect.top)*lock.Pitch+(x-rect.left)*4,&value,4);}Check(textures[slot]->UnlockRect(level));}}};
    // In-place dynamic textures: DEFAULT pool, DYNAMIC usage, staged through DISCARD/NOOVERWRITE
    // locks with no UpdateTexture. Mirrors the floating-point sampler input observed in-game.
    auto fillDynamic=[&](unsigned slot){bool floating=modeName==L"dynamicfloat";
        Check(d->CreateTexture(16,8,0,D3DUSAGE_DYNAMIC,floating?D3DFMT_A16B16G16R16:D3DFMT_A8R8G8B8,D3DPOOL_DEFAULT,&textures[slot],nullptr));
        if(modeName==L"dynamicreadonly"){D3DLOCKED_RECT lock{};Check(textures[slot]->LockRect(0,&lock,nullptr,D3DLOCK_READONLY));Check(textures[slot]->UnlockRect(0));return;}
        // This driver rejects D3DLOCK_NOOVERWRITE on textures outright, and DISCARD must cover the whole
        // level, so the streamed level discards and the tail is written with plain locks that still
        // count as observed in-place writes.
        for(UINT level=0;level<textures[slot]->GetLevelCount();++level){D3DSURFACE_DESC desc{};Check(textures[slot]->GetLevelDesc(level,&desc));
            bool partial=modeName==L"dynamicpartial"&&level==0;
            RECT rect{0,0,partial?4:LONG(desc.Width),LONG(desc.Height)};
            DWORD flags=level||partial?DWORD(0):D3DLOCK_DISCARD;
            D3DLOCKED_RECT lock{};Check(textures[slot]->LockRect(level,&lock,partial?&rect:nullptr,flags));
            for(LONG y=rect.top;y<rect.bottom;++y)for(LONG x=rect.left;x<rect.right;++x){
                if(floating){for(unsigned b=0;b<8;++b){unsigned char v=static_cast<unsigned char>((slot*67+x*8+y*131+level*37+b*17)&0xff);memcpy(static_cast<char*>(lock.pBits)+(y-rect.top)*lock.Pitch+(x-rect.left)*8+b,&v,1);}}
                else{DWORD value=0xff000000|((32+x*13+level*7)<<16)|((40+y*17+slot*31)<<8)|(60+level*19);memcpy(static_cast<char*>(lock.pBits)+(y-rect.top)*lock.Pitch+(x-rect.left)*4,&value,4);}}
            Check(textures[slot]->UnlockRect(level));}};
    if(paired){for(unsigned slot=0;slot<2;++slot){if(modeName.rfind(L"dynamic",0)==0){fillDynamic(slot);continue;}bool large=std::wstring(mode)==L"texlarge",dynamic=std::wstring(mode)==L"texdynamic";auto format=compressed?D3DFORMAT(MAKEFOURCC('D','X','T',char(modeName[3]))):D3DFMT_A8R8G8B8;
            Check(d->CreateTexture(compressed||uploading?(slot?32:16):(large?256:(slot?8:4)),compressed||uploading?(slot?16:8):(large?128:4),0,dynamic?D3DUSAGE_DYNAMIC:0,format,uploading?D3DPOOL_SYSTEMMEM:dynamic?D3DPOOL_DEFAULT:D3DPOOL_MANAGED,&textures[slot],nullptr));
            DWORD flags=uploading&&modeName.find(L"dirtycreation")!=std::wstring::npos?D3DLOCK_NO_DIRTY_UPDATE:0;
            if(compressed)FillCompressed(textures[slot].Get(),slot,modeName.find(L"partialinit")!=std::wstring::npos||(!uploading&&modeName.find(L"partial")!=std::wstring::npos),0,flags);else fillTexture(slot,std::wstring(mode)==L"texpartial"||modeName.find(L"partialinit")!=std::wstring::npos,0,flags);}
        if(uploading){
            auto action=modeName.substr(5);std::array<ComPtr<IDirect3DTexture9>,2> destinations;
            for(UINT slot=0;slot<2;++slot){auto sourceTexture=textures[slot].Get();D3DSURFACE_DESC desc{};Check(sourceTexture->GetLevelDesc(0,&desc));
                bool smaller=action==L"mismatch"||action==L"surfacemip";
                Check(d->CreateTexture(smaller?desc.Width/2:desc.Width,smaller?desc.Height/2:desc.Height,0,0,desc.Format,D3DPOOL_DEFAULT,&destinations[slot],nullptr));
                auto fill=[&](UINT generation,DWORD flags=0){if(compressed)FillCompressed(sourceTexture,slot,false,generation,flags);else fillTexture(slot,false,generation,flags);};
                if(action.rfind(L"surface",0)==0){SurfaceFixtureUploads(d,sourceTexture,destinations[slot].Get(),action,fill);continue;}
                if(action==L"unknown"||action==L"incomplete"){Check(sourceTexture->AddDirtyRect(nullptr));if(action==L"incomplete"){D3DLOCKED_RECT locked{};Check(sourceTexture->LockRect(0,&locked,nullptr,0));Check(sourceTexture->UnlockRect(0));}}
                if(action==L"sourcealias"||action==L"recover"){ComPtr<IDirect3DSurface9> surface;Check(sourceTexture->GetSurfaceLevel(0,&surface));D3DLOCKED_RECT locked{};Check(surface->LockRect(&locked,nullptr,0));Check(surface->UnlockRect());if(action==L"recover")fill(1);}
                if(action==L"failed"){ComPtr<IDirect3DTexture9> invalidDestination;Check(d->CreateTexture(desc.Width,desc.Height,0,0,desc.Format,D3DPOOL_MANAGED,&invalidDestination,nullptr));Need(FAILED(d->UpdateTexture(sourceTexture,invalidDestination.Get())),"invalid upload succeeded");}
                Check(d->UpdateTexture(sourceTexture,destinations[slot].Get()));
                if(action.rfind(L"dirty",0)==0&&action!=L"dirtycreation"){
                    fill(1,D3DLOCK_NO_DIRTY_UPDATE);
                    if(action==L"dirtyunknown"){ComPtr<IDirect3DSurface9> surface;Check(sourceTexture->GetSurfaceLevel(0,&surface));D3DLOCKED_RECT locked{};Check(surface->LockRect(&locked,nullptr,0));Check(surface->UnlockRect());}
                    if(action==L"dirtyfailed"){RECT invalid{-1,0,LONG(desc.Width),LONG(desc.Height)};sourceTexture->AddDirtyRect(&invalid);}
                    RECT full{0,0,LONG(desc.Width),LONG(desc.Height)},part{0,0,4,4};
                    if(action==L"dirtyfull"||action==L"dirtyunknown"||action==L"dirtyfailed"||action==L"dirtykeep")Check(sourceTexture->AddDirtyRect(nullptr));
                    if(action==L"dirtyrect")Check(sourceTexture->AddDirtyRect(&full));
                    if(action==L"dirtypartial"||action==L"dirtykeep")Check(sourceTexture->AddDirtyRect(&part));
                    if(action==L"dirtytop"){D3DLOCKED_RECT locked{};Check(sourceTexture->LockRect(0,&locked,nullptr,0));Check(sourceTexture->UnlockRect(0));}
                    Check(d->UpdateTexture(sourceTexture,destinations[slot].Get()));
                }
                // Surface-alias dirty declarations. The mip bytes are rewritten without a dirty
                // declaration first, so only the alias lock can supply the upload proof.
                if(action.rfind(L"alias",0)==0&&action!=L"sourcealias"){
                    fill(1,D3DLOCK_NO_DIRTY_UPDATE);
                    ComPtr<IDirect3DSurface9> surface;Check(sourceTexture->GetSurfaceLevel(action==L"aliasmip"?1:0,&surface));D3DLOCKED_RECT locked{};
                    RECT part{0,0,4,4};
                    if(action==L"aliasfull"){Check(surface->LockRect(&locked,nullptr,0));Check(surface->UnlockRect());}
                    if(action==L"aliaspartial"){Check(surface->LockRect(&locked,&part,0));Check(surface->UnlockRect());}
                    if(action==L"aliasmip"){Check(surface->LockRect(&locked,nullptr,0));Check(surface->UnlockRect());}
                    if(action==L"aliasreadonly"){Check(surface->LockRect(&locked,nullptr,D3DLOCK_READONLY));Check(surface->UnlockRect());}
                    Check(d->UpdateTexture(sourceTexture,destinations[slot].Get()));
                }
                if(action==L"refresh"){fill(1);Check(d->UpdateTexture(sourceTexture,destinations[slot].Get()));}
                if(action==L"sourcechanged")fill(1);
                if(action==L"consumed")Check(d->UpdateTexture(sourceTexture,destinations[slot].Get()));
                if(action==L"lowermip"){D3DLOCKED_RECT locked{};Check(sourceTexture->LockRect(1,&locked,nullptr,0));Check(sourceTexture->UnlockRect(1));Check(d->UpdateTexture(sourceTexture,destinations[slot].Get()));}
                if(action==L"partial"){RECT rect{0,0,4,4};D3DLOCKED_RECT locked{};Check(sourceTexture->LockRect(0,&locked,&rect,0));Check(sourceTexture->UnlockRect(0));Check(d->UpdateTexture(sourceTexture,destinations[slot].Get()));}
                if(action==L"destalias"){ComPtr<IDirect3DSurface9> surface;Check(destinations[slot]->GetSurfaceLevel(0,&surface));D3DLOCKED_RECT locked{};if(SUCCEEDED(surface->LockRect(&locked,nullptr,0)))Check(surface->UnlockRect());}
            }
            textures=destinations;
        }
        if(compressed&&!uploading){auto action=modeName.substr(5);D3DLOCKED_RECT lock{};
            if(action==L"readonly"){Check(textures[0]->LockRect(0,&lock,nullptr,D3DLOCK_READONLY));Check(textures[0]->UnlockRect(0));}
            if(action==L"failed")Need(FAILED(textures[0]->LockRect(99,&lock,nullptr,0)),"compressed invalid level");
            if(action==L"alias"||action==L"refresh"){ComPtr<IDirect3DSurface9> surface;Check(textures[0]->GetSurfaceLevel(0,&surface));Check(surface->LockRect(&lock,nullptr,0));Check(surface->UnlockRect());if(action==L"refresh")FillCompressed(textures[0].Get(),0,true);}
            if(action==L"dirty"||action==L"incomplete"){Check(textures[0]->AddDirtyRect(nullptr));if(action==L"incomplete"){RECT rect{0,0,4,4};Check(textures[0]->LockRect(0,&lock,&rect,0));auto block=CompressedBlock(D3DFORMAT(MAKEFOURCC('D','X','T',char(mode[3]))),0,0,0,0);memcpy(lock.pBits,block.data(),block.size());Check(textures[0]->UnlockRect(0));}}
            if(action==L"flags"){Check(textures[0]->LockRect(0,&lock,nullptr,D3DLOCK_NO_DIRTY_UPDATE));Check(textures[0]->UnlockRect(0));}
            if(action==L"unaligned"){RECT rect{1,0,5,4};auto hr=textures[0]->LockRect(0,&lock,&rect,0);if(SUCCEEDED(hr))Check(textures[0]->UnlockRect(0));}
        }
        if(modeName==L"maskbudget"||modeName==L"maskexhaust"||modeName==L"maskrelease"){
            auto allocate=[&](){ComPtr<IDirect3DTexture9> t;Check(d->CreateTexture(1024,1024,0,0,D3DFMT_DXT5,D3DPOOL_MANAGED,&t,nullptr));budgetTextures.push_back(std::move(t));};
            for(unsigned i=0;i<(modeName==L"maskbudget"?64u:96u);++i)allocate();
            if(modeName==L"maskrelease"){budgetTextures.clear();allocate();}
            textures[0]=budgetTextures.back();FillCompressed(textures[0].Get(),0,false);
        }
        // DEFAULT-pool destinations additionally pay a fixed 128-entry surface-history charge and
        // cannot be filled directly, so the proof comes from a SYSTEMMEM source upload.
        if(modeName==L"defbudget"||modeName==L"defexhaust"||modeName==L"defrelease"){
            auto allocate=[&](){ComPtr<IDirect3DTexture9> t;Check(d->CreateTexture(512,512,0,0,D3DFMT_DXT5,D3DPOOL_DEFAULT,&t,nullptr));budgetTextures.push_back(std::move(t));};
            for(unsigned i=0;i<(modeName==L"defbudget"?300u:370u);++i)allocate();
            if(modeName==L"defrelease"){budgetTextures.clear();allocate();}
            ComPtr<IDirect3DTexture9> source;Check(d->CreateTexture(512,512,0,0,D3DFMT_DXT5,D3DPOOL_SYSTEMMEM,&source,nullptr));FillCompressed(source.Get(),0,false);
            Check(d->UpdateTexture(source.Get(),budgetTextures.back().Get()));textures[0]=budgetTextures.back();
        }
        if(std::wstring(mode)==L"texalias"||std::wstring(mode)==L"texrefresh"){ComPtr<IDirect3DSurface9> surface;Check(textures[0]->GetSurfaceLevel(0,&surface));D3DLOCKED_RECT lock{};Check(surface->LockRect(&lock,nullptr,0));DWORD value=0xff557799;memcpy(lock.pBits,&value,4);Check(surface->UnlockRect());if(std::wstring(mode)==L"texrefresh")fillTexture(0,true);}
        if(std::wstring(mode)==L"texfailedlock"){D3DLOCKED_RECT lock{};Need(FAILED(textures[0]->LockRect(99,&lock,nullptr,0)),"invalid mip lock succeeded");}
        if(std::wstring(mode)==L"texcopy")Need(FAILED(d->UpdateTexture(textures[0].Get(),textures[1].Get())),"managed destination copy succeeded");
        if(std::wstring(mode)==L"texgenerated")textures[0]->GenerateMipSubLevels();
        if(std::wstring(mode)==L"texreadonly"){D3DLOCKED_RECT lock{};Check(textures[0]->LockRect(0,&lock,nullptr,D3DLOCK_READONLY));Check(textures[0]->UnlockRect(0));}
        if(std::wstring(mode)==L"texincomplete"){Check(textures[0]->AddDirtyRect(nullptr));RECT rect{0,0,1,1};D3DLOCKED_RECT lock{};Check(textures[0]->LockRect(0,&lock,&rect,0));DWORD value=0xff557799;memcpy(lock.pBits,&value,4);Check(textures[0]->UnlockRect(0));}
    }
    for(unsigned variant=0;variant<8;++variant){
        Constants constants{};constants.known.fill(true);constants.rows={Vec{.13f,.8f,0,0},Vec{1,0,0,0},Vec{0,1,0,0},Vec{0,0,1,0},Vec{.25f,0,.3f,1},Vec{1,0,0,0},Vec{0,1,0,0},Vec{0,0,1,0}};
        std::array<Vec,2> extra={Vec{.2f,-.3f,.7f,.4f},Vec{.9f-.03f*variant,0,variant==7?.8f:.1f,.6f}};
        constexpr UINT regs[]={0,4,5,6,7,58,59,60};for(unsigned i=0;i<8;++i)Check(d->SetVertexShaderConstantF(regs[i],constants.rows[i].data(),1));Check(d->SetVertexShaderConstantF(12,extra[0].data(),1));Check(d->SetVertexShaderConstantF(16,extra[1].data(),1));
        if(std::wstring(mode)==L"stateblock"){ComPtr<IDirect3DStateBlock9> block;Check(d->CreateStateBlock(D3DSBT_ALL,&block));Check(block->Apply());}
        if(paired){
            constexpr UINT registers[]={11,12,29,30};std::array<Vec,4> pc={Vec{.1f,.2f,.3f,.4f},Vec{.6f+.02f*variant,.8f,.7f,.9f},Vec{.2f,.3f,.4f,.5f},Vec{1,0,0,0}};
            for(unsigned i=0;i<4;++i)if(!(i==3&&(std::wstring(mode)==L"missingps"||std::wstring(mode)==L"failedps")))Check(d->SetPixelShaderConstantF(registers[i],pc[i].data(),1));
            if(std::wstring(mode)==L"failedps"){std::array<Vec,1024> invalid{};Need(FAILED(d->SetPixelShaderConstantF(30,invalid[0].data(),1024)),"invalid PS constant write succeeded");}
            if(std::wstring(mode)==L"psstateblock"||std::wstring(mode)==L"psrefresh"){ComPtr<IDirect3DStateBlock9> block;Check(d->CreateStateBlock(D3DSBT_ALL,&block));Check(block->Apply());
                for(unsigned i=0;i<8;++i)Check(d->SetVertexShaderConstantF(regs[i],constants.rows[i].data(),1));Check(d->SetVertexShaderConstantF(12,extra[0].data(),1));Check(d->SetVertexShaderConstantF(16,extra[1].data(),1));
                if(std::wstring(mode)==L"psrefresh")for(unsigned i=0;i<4;++i)Check(d->SetPixelShaderConstantF(registers[i],pc[i].data(),1));}
            textures[0]->SetLOD(variant%2);
            for(UINT slot=0;slot<2;++slot){Check(d->SetTexture(slot,textures[(slot+variant)%2].Get()));Check(d->SetSamplerState(slot,D3DSAMP_ADDRESSU,variant%2?D3DTADDRESS_CLAMP:D3DTADDRESS_WRAP));Check(d->SetSamplerState(slot,D3DSAMP_ADDRESSV,D3DTADDRESS_CLAMP));Check(d->SetSamplerState(slot,D3DSAMP_MINFILTER,D3DTEXF_LINEAR));Check(d->SetSamplerState(slot,D3DSAMP_MAGFILTER,D3DTEXF_LINEAR));Check(d->SetSamplerState(slot,D3DSAMP_MIPFILTER,D3DTEXF_POINT));Check(d->SetSamplerState(slot,D3DSAMP_SRGBTEXTURE,variant%2));}
            if(std::wstring(mode)==L"nulltexture")Check(d->SetTexture(1,nullptr));
        }
        std::array<Cpu,3> cpu{};
        for(unsigned i=0;i<3;++i){auto p=points[i];auto position=Evaluate({p.p[0],p.p[1],p.p[2]},constants);auto m=EvaluateMaterial({p.p[0],p.p[1],p.p[2]},{p.uv[0],p.uv[1],p.uv[2],p.uv[3]},p.color,constants,extra);
            cpu[i].clip=position.clip;std::copy_n(m.begin(),4,cpu[i].uv.begin());std::copy_n(m.begin()+4,4,cpu[i].color.begin());cpu[i].model=position.model;cpu[i].model[3]=m[8];cpu[i].fog.fill(m[9]);}
        Need(cpu[0].clip[3]!=cpu[2].clip[3],"perspective variation missing");
        if(std::wstring(mode)==L"wrongcpu")cpu[0].uv[0]+=.2f;
        auto badExtra=extra;badExtra[0][0]=std::numeric_limits<float>::infinity();Reject([&]{EvaluateMaterial({0,0,0},{0,0,0,0},0,constants,badExtra);});
        Reject([&]{EvaluateMaterial({0,0,0},{std::numeric_limits<float>::quiet_NaN(),0,0,0},0,constants,extra);});
        auto overflow=extra;overflow[0].fill(std::numeric_limits<float>::max());Reject([&]{EvaluateMaterial({1,1,1},{0,0,0,0},0,constants,overflow);});
        for(const char* probe:probes){ComPtr<IDirect3DPixelShader9> pixel=pairedPixel;if(!paired||std::wstring(mode)==L"wrongshader"){auto ps=compile(probe,"ps_2_0");Check(d->CreatePixelShader(static_cast<const DWORD*>(ps->GetBufferPointer()),&pixel));}Check(d->SetPixelShader(pixel.Get()));
            auto render=[&](bool evaluated){Check(d->Clear(0,nullptr,D3DCLEAR_TARGET,0,1,0));Check(d->SetVertexShader(evaluated?pass.Get():native.Get()));Check(d->SetVertexDeclaration(evaluated?cd.Get():nd.Get()));
                if(!evaluated){Check(d->SetStreamSource(0,vb.Get(),0,48));Check(d->SetIndices(ib.Get()));
                    std::vector<std::uint8_t> vbytes(sizeof(points)),vknown(sizeof(points),1),ibytes(6),iknown(6,1);memcpy(vbytes.data(),points.data(),sizeof(points));memcpy(ibytes.data(),indices.data(),6);std::array<bool,61> known;known.fill(true);
                    Evidence ve{vb.Get(),vbytes,vknown},ie{ib.Get(),ibytes,iknown};Draw draw{0,0,3,0,1};if(std::wstring(mode)==L"unsupportedvs")Reject([&]{position::Capture(d,draw,ve,ie,known,true);});else Need(!position::Capture(d,draw,ve,ie,known,true).empty(),"material capture");
                    for(unsigned missing:{24u,28u,36u,43u}){vknown[missing]=0;Reject([&]{position::Capture(d,draw,ve,ie,known,true);});vknown[missing]=1;}
                    for(unsigned missing:{12u,16u}){known[missing]=false;Reject([&]{position::Capture(d,draw,ve,ie,known,true);});known[missing]=true;}
                    auto oversized=draw;oversized.primitives=1025;Reject([&]{position::Capture(d,oversized,ve,ie,known,true);});}
                Check(d->BeginScene());if(evaluated)Check(d->DrawPrimitiveUP(D3DPT_TRIANGLELIST,1,cpu.data(),sizeof(Cpu)));else {wchar_t stress[2]{};UINT repeats=GetEnvironmentVariableW(L"RRT_MATERIAL_SELECTION_STRESS",stress,2)==1&&stress[0]==L'1'?200:1;for(UINT repeat=0;repeat<repeats;++repeat)Check(d->DrawIndexedPrimitive(D3DPT_TRIANGLELIST,0,0,3,0,1));}Check(d->EndScene());
                Check(d->GetRenderTargetData(target.Get(),read.Get()));D3DLOCKED_RECT locked{};Check(read->LockRect(&locked,nullptr,D3DLOCK_READONLY));std::vector<float> pixels(128*96*4);for(unsigned y=0;y<96;++y)memcpy(pixels.data()+y*128*4,static_cast<const char*>(locked.pBits)+y*locked.Pitch,128*16);Check(read->UnlockRect());return pixels;};
            auto actual=render(false),expected=render(true);nativeEvidence.insert(nativeEvidence.end(),actual.begin(),actual.end());for(unsigned i=0;i<actual.size();++i){Need(std::isfinite(actual[i])&&std::isfinite(expected[i]),"material GPU nonfinite");double error=std::abs(double(actual[i])-expected[i])/(1+std::abs(double(expected[i])));worst=std::max(worst,error);Need(error<=2e-4,"material interpolation mismatch");if(actual[i]!=0)++covered;}}
        Present(d);
    }
    auto digest=rrt::scene::Digest(nativeEvidence.data(),nativeEvidence.size()*sizeof(float));std::string hash;const char* alphabet="0123456789abcdef";for(auto b:digest){hash+=alphabet[b>>4];hash+=alphabet[b&15];}
    Need(covered>100,"empty material probes");std::cout<<"{\"status\":\"matched\",\"probes\":24,\"nonzero_lanes\":"<<covered<<",\"max_normalized_error\":"<<worst<<",\"native_sha256\":\""<<hash<<"\"}\n";
}
