// Included inside the fixture's anonymous namespace; not linked into the proxy. Oracles for the vs_2_0 position interpreter
// (docs/VS_INTERPRETER.md). Program bytes and declarations come from the user's own inventory on stdin; nothing is embedded.
// Needs vs_interpreter.h, <map> and <algorithm>, included at the top of fixture.cpp.

struct Random {std::uint32_t state;float Next(float lo,float hi){state=state*1664525u+1013904223u;return lo+(hi-lo)*float(state>>8)/16777216.f;}
    std::uint32_t Bits(){state=state*1664525u+1013904223u;return state;}};
std::vector<std::uint32_t> ReadHexLine(std::size_t maximum){
    std::string hex;char ch;while(std::cin.get(ch)&&ch!='\n'){Need(hex.size()<maximum*2,"input bound");hex+=ch;}
    Need(!hex.empty()&&hex.size()%8==0,"hex input must be whole tokens");std::vector<std::uint32_t> tokens(hex.size()/8);auto bytes=reinterpret_cast<unsigned char*>(tokens.data());
    auto digit=[](char c){Need((c>='0'&&c<='9')||(c>='a'&&c<='f'),"invalid hex");return c<='9'?c-'0':c-'a'+10;};
    for(std::size_t i=0;i<hex.size()/2;++i)bytes[i]=static_cast<unsigned char>(digit(hex[i*2])*16+digit(hex[i*2+1]));return tokens;
}

// The interpreter must equal the three hand-written evaluators exactly: they follow the same programs' float32 operation order.
void InterpreterSelfTest(){
    using namespace rrt::shader::position;
    auto pinned=ReadHexLine(612),flex=ReadHexLine(FlexProgramBytes),skin=ReadHexLine(SkinProgramBytes);
    Need(std::cin.peek()==EOF,"trailing input");
    Admit({reinterpret_cast<const std::uint8_t*>(pinned.data()),612});AdmitFlex({reinterpret_cast<const std::uint8_t*>(flex.data()),FlexProgramBytes});AdmitSkin({reinterpret_cast<const std::uint8_t*>(skin.data()),SkinProgramBytes});
    const auto p0=vsi::Analyse(pinned),p1=vsi::Analyse(flex),p2=vsi::Analyse(skin);
    Need(p0.ok&&p1.ok&&p2.ok,("analysis refused an admitted program: "+p0.reason+p1.reason+p2.reason).c_str());
    Need(p1.camera.viewProjection==8u&&p1.camera.model==58u&&p2.camera.viewProjection==8u&&p0.camera.modelViewProjection==4u&&p0.camera.model==58u,"constant-table cameras");
    Need(p2.relativeBases.size()==9,"skinned program reads nine relative rows");
    Random rng{12345};std::size_t compared=0;
    for(unsigned trial=0;trial<4000;++trial){
        std::array<vsi::Vec,256> regs;for(auto& r:regs)for(auto& v:r)v=rng.Next(-2,2);
        regs[0]={rng.Next(-.1f,.1f),rng.Next(.8f,1.2f),2,.5f};
        auto lookup=[&](unsigned r)->const vsi::Vec*{return &regs[r];};
        std::array<float,3> p{rng.Next(-500,500),rng.Next(-500,500),rng.Next(-500,500)},f{rng.Next(-3,3),rng.Next(-3,3),rng.Next(-3,3)};
        std::array<std::int16_t,2> w{std::int16_t(rng.Bits()&0x7fff),std::int16_t(-std::int16_t(rng.Bits()&0x3fff))};
        std::uint32_t bones=(rng.Bits()%53)|((rng.Bits()%53)<<8)|((rng.Bits()%53)<<16)|(0x80u<<24);
        auto inputsFor=[&](const vsi::Program& prog){std::array<vsi::Vec,16> in{};for(auto& v:in)v={0,0,0,1};
            for(unsigned r=0;r<16;++r){if(!prog.inputDeclared[r])continue;const auto u=prog.inputUsage[r],k=prog.inputUsageIndex[r];
                if(u==0&&k==0)in[r]={p[0],p[1],p[2],1};else if(u==0&&k==1)in[r]={f[0],f[1],f[2],1};
                else if(u==1){std::uint8_t b[4];memcpy(b,w.data(),4);in[r]=vsi::ConvertInput(6,b);}
                else if(u==2){std::uint8_t b[4];memcpy(b,&bones,4);in[r]=vsi::ConvertInput(4,b);}}
            return in;};
        auto same=[&](const vsi::Vec& a,const std::array<float,4>& b,const char* what){for(unsigned c=0;c<4;++c)Need(std::memcmp(&a[c],&b[c],4)==0,what);++compared;};
        {Constants c{};c.known.fill(true);constexpr unsigned r[]={0,4,5,6,7,58,59,60};for(unsigned i=0;i<8;++i)c.rows[i]=regs[r[i]];
            same(vsi::Evaluate(p0,inputsFor(p0),lookup),Evaluate(p,c).clip,"interpreter differs from the first program's evaluator");}
        {FlexConstants c{};c.known.fill(true);for(unsigned i=0;i<9;++i)c.rows[i]=regs[FlexRegisters[i]];
            same(vsi::Evaluate(p1,inputsFor(p1),lookup),EvaluateFlex(p,f,c).clip,"interpreter differs from the flex evaluator");}
        {SkinConstants c{};c.known.fill(true);c.paletteKnown.fill(true);for(unsigned i=0;i<6;++i)c.rows[i]=regs[SkinRegisters[i]];for(unsigned i=0;i<PaletteRows;++i)c.palette[i]=regs[PaletteStart+i];
            same(vsi::Evaluate(p2,inputsFor(p2),lookup),EvaluateSkin({p,f,w,bones},c).clip,"interpreter differs from the skinned evaluator");
            auto reads=vsi::RelativeReads(p2,inputsFor(p2),lookup);Need(reads.size()==9,"nine relative reads per skinned vertex");
            for(auto base:SkinBones(bones))for(unsigned k=0;k<3;++k)Need(std::find(reads.begin(),reads.end(),PaletteStart+base+k)!=reads.end(),"relative reads name the bone rows");}
    }
    // Refusals: an unknown constant, a changed opcode in the slice, a predicated or truncated program.
    {std::array<vsi::Vec,16> in{};for(auto& v:in)v={0,0,0,1};Reject([&]{vsi::Evaluate(p1,in,[](unsigned r)->const vsi::Vec*{static vsi::Vec one{1,1,1,1};return r==9?nullptr:&one;});});}
    {auto bad=flex;bool changed=false;for(const auto& in:p1.code)if(in.slice&&in.opcode==9){bad[in.token]=(bad[in.token]&~0xffffu)|19u;changed=true;break;} // dp4 -> frc
        Need(changed,"no slice dp4 to mutate");auto q=vsi::Analyse(bad);Need(!q.ok&&q.reason=="unsupported_slice_opcode",("mutated slice opcode: "+q.reason).c_str());}
    {auto bad=pinned;bad.resize(bad.size()/2);Need(!vsi::Analyse(bad).ok,"truncated program accepted");}
    {auto bad=pinned;bad[0]=0xfffe0300;Need(vsi::Analyse(bad).reason=="unsupported_shader_model","vs_3_0 accepted");}
    std::cout<<"PASS interpreter equals the three hand-written evaluators bit for bit: comparisons="<<compared<<"; refusals passed\n";
}

// GPU oracle for any program: the instrumented program writes its own oPos to oT7 and draws each vertex as a one-pixel point at
// a fixed screen position, so each pixel of an RGBA32F target holds the hardware's full clip vector for one vertex.
// `lo`..`hi` is the range of float inputs other than POSITION0 (which spans +-300).
std::pair<std::size_t,double> PointOracle(const std::vector<std::uint32_t>& tokens,const std::vector<std::uint32_t>& declarationTokens,float lo=-2,float hi=2){
    const auto program=vsi::Analyse(tokens);Need(program.ok,("analysis refused the program: "+program.reason).c_str());
    std::vector<D3DVERTEXELEMENT9> elements(declarationTokens.size()/2);memcpy(elements.data(),declarationTokens.data(),elements.size()*8);
    Need(!elements.empty()&&elements.back().Stream==0xff,"declaration terminator");elements.pop_back();
    std::uint32_t pointInput{};auto instrumented=vsi::Instrument(tokens,program,pointInput);
    Device source(true);auto d=source.device.Get();
    // The runtime validates both: the program as given (so a malformed program is named as such) and the instrumented one.
    {ComPtr<IDirect3DVertexShader9> original;Need(SUCCEEDED(d->CreateVertexShader(reinterpret_cast<const DWORD*>(tokens.data()),&original)),"the runtime refused the program itself");}
    ComPtr<IDirect3DVertexShader9> vs;Need(SUCCEEDED(d->CreateVertexShader(reinterpret_cast<const DWORD*>(instrumented.data()),&vs)),"the runtime refused the instrumented program");
    auto compile=[](const char* text,const char* profile){ComPtr<ID3DBlob> blob,error;Check(D3DCompile(text,strlen(text),nullptr,nullptr,nullptr,"main",profile,D3DCOMPILE_OPTIMIZATION_LEVEL3,0,&blob,&error));return blob;};
    auto ps=compile("float4 main(float4 c:TEXCOORD7):COLOR{return c;}","ps_2_0");ComPtr<IDirect3DPixelShader9> pixel;Check(d->CreatePixelShader(static_cast<const DWORD*>(ps->GetBufferPointer()),&pixel));
    // Each stream the declaration uses gets its own buffer; the point positions go to a stream the title does not use.
    WORD pointStream=0;for(const auto& e:elements)pointStream=std::max<WORD>(pointStream,WORD(e.Stream+1));Need(pointStream<16,"no free stream");
    std::vector<D3DVERTEXELEMENT9> withPoint=elements;withPoint.push_back({pointStream,0,D3DDECLTYPE_FLOAT4,0,D3DDECLUSAGE_TEXCOORD,15});withPoint.push_back(D3DDECL_END());
    ComPtr<IDirect3DVertexDeclaration9> declaration;Check(d->CreateVertexDeclaration(withPoint.data(),&declaration));
    constexpr UINT W=64,H=64,Count=512;
    ComPtr<IDirect3DSurface9> target,read;Check(d->CreateRenderTarget(W,H,D3DFMT_A32B32G32R32F,D3DMULTISAMPLE_NONE,0,FALSE,&target,nullptr));
    Check(d->CreateOffscreenPlainSurface(W,H,D3DFMT_A32B32G32R32F,D3DPOOL_SYSTEMMEM,&read,nullptr));
    Check(d->SetRenderTarget(0,target.Get()));Check(d->SetDepthStencilSurface(nullptr));Configure(d);Check(d->SetPixelShader(pixel.Get()));
    Check(d->SetRenderState(D3DRS_CULLMODE,D3DCULL_NONE));Check(d->SetRenderState(D3DRS_ZENABLE,FALSE));Check(d->SetRenderState(D3DRS_POINTSPRITEENABLE,FALSE));Check(d->SetRenderState(D3DRS_POINTSCALEENABLE,FALSE));
    float one=1;DWORD bits;memcpy(&bits,&one,4);Check(d->SetRenderState(D3DRS_POINTSIZE,bits));Check(d->SetRenderState(D3DRS_FOGENABLE,FALSE));Check(d->SetRenderState(D3DRS_CLIPPING,FALSE));
    D3DVIEWPORT9 viewport{0,0,W,H,0,1};Check(d->SetViewport(&viewport));
    double worst=0;std::size_t compared=0;
    for(unsigned variant=0;variant<4;++variant){
        Random rng{0x9e3779b9u+variant*7919u};
        // Every float register finite and moderate; c0 in the title's (0, 1, 2, 0.5) shape, which the programs' constant decodes expect.
        std::array<vsi::Vec,256> regs;for(auto& r:regs)for(auto& v:r)v=rng.Next(-2,2);regs[0]={0,1,2,.5f};
        for(unsigned r=0;r<256;++r)if(program.defs[r])regs[r]=*program.defs[r];
        Check(d->SetVertexShaderConstantF(0,regs[0].data(),256));
        BOOL bools[16];for(auto& b:bools)b=variant%2;Check(d->SetVertexShaderConstantB(0,bools,16));
        int ints[16*4]{};for(unsigned i=0;i<16;++i){ints[i*4]=1;ints[i*4+1]=0;ints[i*4+2]=1;}Check(d->SetVertexShaderConstantI(0,ints,16));
        // Per-stream vertex data: every element filled by its type; blend indices stay inside the 53-bone palette.
        std::map<WORD,UINT> strides;for(const auto& e:elements)strides[e.Stream]=std::max<UINT>(strides[e.Stream],UINT(e.Offset+vsi::InputSize(e.Type)));
        std::map<WORD,std::vector<std::uint8_t>> streams;for(auto& [s,stride]:strides){stride=(stride+3)&~3u;streams[s].resize(std::size_t(stride)*Count);}
        for(UINT v=0;v<Count;++v)for(const auto& e:elements){auto* at=streams[e.Stream].data()+std::size_t(strides[e.Stream])*v+e.Offset;
            if(e.Type<=3){for(unsigned k=0;k<=e.Type;++k){float x=e.Usage==D3DDECLUSAGE_POSITION&&e.UsageIndex==0?rng.Next(-300,300):rng.Next(lo,hi);memcpy(at+4*k,&x,4);}}
            else if(e.Usage==D3DDECLUSAGE_BLENDINDICES){for(unsigned k=0;k<4;++k)at[k]=std::uint8_t(rng.Bits()%53);}
            else{for(unsigned k=0;k<vsi::InputSize(e.Type);++k)at[k]=std::uint8_t(rng.Bits());}}
        std::vector<vsi::Vec> points(Count);for(UINT v=0;v<Count;++v){const UINT px=(v%32)*2,py=(v/32)*2;points[v]={2.f*float(px)/W-1,1-2.f*float(py)/H,.5f,1};}
        std::vector<ComPtr<IDirect3DVertexBuffer9>> buffers;
        for(auto& [s,bytes]:streams){ComPtr<IDirect3DVertexBuffer9> vb;Check(d->CreateVertexBuffer(UINT(bytes.size()),0,0,D3DPOOL_MANAGED,&vb,nullptr));void* p{};Check(vb->Lock(0,0,&p,0));memcpy(p,bytes.data(),bytes.size());Check(vb->Unlock());
            Check(d->SetStreamSource(s,vb.Get(),0,strides[s]));buffers.push_back(vb);}
        {ComPtr<IDirect3DVertexBuffer9> vb;Check(d->CreateVertexBuffer(Count*16,0,0,D3DPOOL_MANAGED,&vb,nullptr));void* p{};Check(vb->Lock(0,0,&p,0));memcpy(p,points.data(),Count*16);Check(vb->Unlock());
            Check(d->SetStreamSource(pointStream,vb.Get(),0,16));buffers.push_back(vb);}
        Check(d->SetVertexShader(vs.Get()));Check(d->SetVertexDeclaration(declaration.Get()));
        Check(d->Clear(0,nullptr,D3DCLEAR_TARGET,0,1,0));Check(d->BeginScene());Check(d->DrawPrimitive(D3DPT_POINTLIST,0,Count));Check(d->EndScene());
        Check(d->GetRenderTargetData(target.Get(),read.Get()));D3DLOCKED_RECT lock{};Check(read->LockRect(&lock,nullptr,D3DLOCK_READONLY));
        std::vector<float> pixels(W*H*4);for(UINT y=0;y<H;++y)memcpy(pixels.data()+y*W*4,static_cast<const char*>(lock.pBits)+y*lock.Pitch,W*16);Check(read->UnlockRect());
        auto lookup=[&](unsigned r)->const vsi::Vec*{return &regs[r];};
        for(UINT v=0;v<Count;++v){std::array<vsi::Vec,16> in{};for(auto& x:in)x={0,0,0,1};
            for(unsigned r=0;r<16;++r){if(!program.inputDeclared[r])continue;
                for(const auto& e:elements)if(e.Usage==program.inputUsage[r]&&e.UsageIndex==program.inputUsageIndex[r]){in[r]=vsi::ConvertInput(e.Type,streams[e.Stream].data()+std::size_t(strides[e.Stream])*v+e.Offset);break;}}
            const auto cpu=vsi::Evaluate(program,in,lookup);const UINT px=(v%32)*2,py=(v/32)*2;const float* gpu=&pixels[(py*W+px)*4];
            for(unsigned c=0;c<4;++c){Need(std::isfinite(gpu[c]),"nonfinite GPU output");const double e=std::abs(double(gpu[c])-cpu[c])/(1+std::abs(double(cpu[c])));worst=std::max(worst,e);
                if(e>2e-4){std::cerr<<"vertex "<<v<<" component "<<c<<": gpu "<<gpu[c]<<" cpu "<<cpu[c]<<"\n";Need(false,"position mismatch");}}
            Need(pixels[((py)*W+px+1)*4+3]==0||px+1>=W,"a point covered more than one pixel");++compared;}
    }
    return {compared,worst};
}
void InterpreterOracle(){
    auto tokens=ReadHexLine(16384);auto declarationTokens=ReadHexLine(65*2);Need(std::cin.peek()==EOF,"trailing input");
    const auto program=vsi::Analyse(tokens);auto [compared,worst]=PointOracle(tokens,declarationTokens);
    std::cout<<"PASS interpreter GPU point oracle: vertices="<<compared<<" max_normalized_error="<<worst<<" tolerance=0.0002 slice="<<std::count_if(program.code.begin(),program.code.end(),[](const vsi::Instruction& i){return i.slice;})<<"\n";
}

// Synthetic programs, assembled token by token, for the interpreter rules the title's programs never exercise: mova rounding of
// fractional and negative values, the negate modifier, and min, max, abs and dp3 with swizzles and write masks.
namespace synthetic {
constexpr std::uint32_t Temp=0,In=1,Const=2,Addr=3,RastOut=4;
std::uint32_t Dst(std::uint32_t type,std::uint32_t reg,std::uint32_t mask=15){return 0x80000000u|((type&7)<<28)|(((type>>3)&3)<<11)|(mask<<16)|reg;}
std::uint32_t Src(std::uint32_t type,std::uint32_t reg,std::uint32_t swizzle=0xE4,std::uint32_t modifier=0,bool relative=false){
    return 0x80000000u|((type&7)<<28)|(((type>>3)&3)<<11)|(swizzle<<16)|(modifier<<24)|(relative?1u<<13:0)|reg;}
std::uint32_t Address(unsigned component){return 0x80000000u|((Addr&7)<<28)|(component*0x55u<<16);} // a0, replicated component
std::uint32_t Op(std::uint32_t opcode,std::uint32_t length){return opcode|(length<<24);}
std::uint32_t Swz(unsigned x,unsigned y,unsigned z,unsigned w){return x|(y<<2)|(z<<4)|(w<<6);}
std::vector<std::uint32_t> Declare(std::uint32_t reg,std::uint32_t usage,std::uint32_t index){return {Op(31,2),0x80000000u|usage|(index<<16),Dst(In,reg)};}
}
void InterpreterSynthetic(){
    using namespace synthetic;Need(std::cin.peek()==EOF,"no input expected");
    // Both programs read POSITION0 (v0, FLOAT3) and TEXCOORD0 (v1, FLOAT4) from stream 0.
    D3DVERTEXELEMENT9 layout[]={{0,0,D3DDECLTYPE_FLOAT3,0,D3DDECLUSAGE_POSITION,0},{0,12,D3DDECLTYPE_FLOAT4,0,D3DDECLUSAGE_TEXCOORD,0},D3DDECL_END()};
    std::vector<std::uint32_t> declaration(sizeof(layout)/4);memcpy(declaration.data(),layout,sizeof(layout));
    auto program=[](std::vector<std::uint32_t> body){std::vector<std::uint32_t> t={0xfffe0200u};auto d0=Declare(0,0,0),d1=Declare(1,5,0);
        t.insert(t.end(),d0.begin(),d0.end());t.insert(t.end(),d1.begin(),d1.end());t.insert(t.end(),body.begin(),body.end());t.push_back(0x0000ffffu);return t;};
    // 1. mova: a0.xy from fractional inputs in [-0.95, 20.95], then relative reads around c100 and c150.
    auto mova=program({Op(46,2),Dst(Addr,0,3),Src(In,1),
                       Op(1,3),Dst(Temp,1),Src(Const,100,0xE4,0,true),Address(0),                                // one constant per instruction
                       Op(2,4),Dst(Temp,0),Src(Temp,1),Src(Const,150,0xE4,0,true),Address(1),
                       Op(1,2),Dst(RastOut,0),Src(Temp,0)});
    // 2. Negate (the only vs_2_0 source modifier), swizzles, partial write masks, and min, max, abs, dp3 and mad.
    // vs_2_0 lets one instruction read at most one input register and one constant register, so inputs are staged in temporaries.
    auto ops=program({Op(1,2),Dst(Temp,0),Src(In,0,Swz(0,1,2,0)),                                                // mov r0, v0.xyzx
                      Op(2,3),Dst(Temp,0),Src(Temp,0),Src(Const,1,0xE4,1),                                        // add r0, r0, -c1
                      Op(1,2),Dst(Temp,4),Src(In,1),                                                              // mov r4, v1
                      Op(10,3),Dst(Temp,1,0x3),Src(Temp,0,Swz(2,0,1,3)),Src(Temp,4,Swz(3,2,1,0)),                 // min r1.xy, r0.zxyw, r4.wzyx
                      Op(11,3),Dst(Temp,1,0xC),Src(Temp,0,0xE4,1),Src(Const,2,Swz(1,1,0,0)),                      // max r1.zw, -r0, c2.yyxx
                      Op(35,2),Dst(Temp,2),Src(In,1,0xE4,1),                                                      // abs r2, -v1
                      Op(8,3),Dst(Temp,3,0x1),Src(Temp,1),Src(Temp,2,Swz(3,1,0,2)),                               // dp3 r3.x, r1, r2.wyxz
                      Op(4,4),Dst(Temp,3,0xE),Src(Temp,1,Swz(1,2,3,0)),Src(Const,3,Swz(3,3,3,3),1),Src(Temp,2),   // mad r3.yzw, r1.yzwx, -c3.w, r2
                      Op(1,2),Dst(RastOut,0),Src(Temp,3)});
    std::size_t total=0;double worst=0;
    struct Case {const char* name;std::vector<std::uint32_t> tokens;float lo,hi;};
    for(const Case& c:std::vector<Case>{{"mova",mova,-.95f,20.95f},{"modifiers",ops,-3.f,3.f}}){
        auto analysis=vsi::Analyse(c.tokens);Need(analysis.ok,(std::string(c.name)+" refused: "+analysis.reason).c_str());
        std::pair<std::size_t,double> r;try{r=PointOracle(c.tokens,declaration,c.lo,c.hi);}catch(const std::exception& e){throw std::runtime_error(std::string(c.name)+": "+e.what());}
        total+=r.first;worst=std::max(worst,r.second);}
    std::cout<<"PASS interpreter synthetic GPU oracle: programs=2 vertices="<<total<<" max_normalized_error="<<worst<<" tolerance=0.0002\n";
}

// Draws an unmodified program as indexed triangle lists with random constants and inputs, so the proxy's position capture sees
// it the way it sees a title's draws (run under RRT_FIXTURE_PROXY with RRT_POSITION_CAPTURE_FILE). Nothing is compared here:
// tests/verify_vs_interpreter.py validates the ledger with the reader's independent interpreter.
void InterpreterCapture(){
    auto tokens=ReadHexLine(16384);auto declarationTokens=ReadHexLine(65*2);Need(std::cin.peek()==EOF,"trailing input");
    const auto program=vsi::Analyse(tokens);Need(program.ok,("analysis refused the program: "+program.reason).c_str());
    std::vector<D3DVERTEXELEMENT9> elements(declarationTokens.size()/2);memcpy(elements.data(),declarationTokens.data(),elements.size()*8);
    Need(!elements.empty()&&elements.back().Stream==0xff,"declaration terminator");
    Device source(true);auto d=source.device.Get();
    ComPtr<IDirect3DVertexShader9> vs;Need(SUCCEEDED(d->CreateVertexShader(reinterpret_cast<const DWORD*>(tokens.data()),&vs)),"the runtime refused the program itself");
    auto ps=[]{ComPtr<ID3DBlob> blob,error;const char* text="float4 main():COLOR{return float4(1,1,1,1);}";Check(D3DCompile(text,strlen(text),nullptr,nullptr,nullptr,"main","ps_2_0",0,0,&blob,&error));return blob;}();
    ComPtr<IDirect3DPixelShader9> pixel;Check(d->CreatePixelShader(static_cast<const DWORD*>(ps->GetBufferPointer()),&pixel));
    ComPtr<IDirect3DVertexDeclaration9> declaration;Check(d->CreateVertexDeclaration(elements.data(),&declaration));elements.pop_back();
    Configure(d);Check(d->SetPixelShader(pixel.Get()));Check(d->SetVertexShader(vs.Get()));Check(d->SetVertexDeclaration(declaration.Get()));
    Check(d->SetRenderState(D3DRS_CULLMODE,D3DCULL_NONE));
    constexpr UINT Vertices=48,Triangles=32;
    std::map<WORD,UINT> strides;for(const auto& e:elements)strides[e.Stream]=std::max<UINT>(strides[e.Stream],UINT(e.Offset+vsi::InputSize(e.Type)));
    for(unsigned draw=0;draw<4;++draw){
        Random rng{0x51ed2701u+draw*104729u};
        std::array<vsi::Vec,256> regs;for(auto& r:regs)for(auto& v:r)v=rng.Next(-2,2);regs[0]={0,1,2,.5f};
        Check(d->SetVertexShaderConstantF(0,regs[0].data(),256));
        std::vector<ComPtr<IDirect3DVertexBuffer9>> buffers;
        for(auto& [s,raw]:strides){const UINT stride=(raw+3)&~3u;std::vector<std::uint8_t> bytes(std::size_t(stride)*Vertices);
            for(UINT v=0;v<Vertices;++v)for(const auto& e:elements){if(e.Stream!=s)continue;auto* at=bytes.data()+std::size_t(stride)*v+e.Offset;
                if(e.Type<=3){for(unsigned k=0;k<=e.Type;++k){float x=e.Usage==D3DDECLUSAGE_POSITION&&e.UsageIndex==0?rng.Next(-300,300):rng.Next(-2,2);memcpy(at+4*k,&x,4);}}
                else if(e.Usage==D3DDECLUSAGE_BLENDINDICES){for(unsigned k=0;k<4;++k)at[k]=std::uint8_t(rng.Bits()%53);}
                else{for(unsigned k=0;k<vsi::InputSize(e.Type);++k)at[k]=std::uint8_t(rng.Bits());}}
            ComPtr<IDirect3DVertexBuffer9> vb;Check(d->CreateVertexBuffer(UINT(bytes.size()),0,0,D3DPOOL_MANAGED,&vb,nullptr));void* p{};Check(vb->Lock(0,0,&p,0));memcpy(p,bytes.data(),bytes.size());Check(vb->Unlock());
            Check(d->SetStreamSource(s,vb.Get(),0,stride));buffers.push_back(vb);}
        std::vector<std::uint16_t> indices(Triangles*3);for(auto& i:indices)i=std::uint16_t(rng.Bits()%Vertices);
        ComPtr<IDirect3DIndexBuffer9> ib;Check(d->CreateIndexBuffer(UINT(indices.size()*2),0,D3DFMT_INDEX16,D3DPOOL_MANAGED,&ib,nullptr));void* p{};Check(ib->Lock(0,0,&p,0));memcpy(p,indices.data(),indices.size()*2);Check(ib->Unlock());
        Check(d->SetIndices(ib.Get()));Check(d->BeginScene());Check(d->DrawIndexedPrimitive(D3DPT_TRIANGLELIST,0,0,Vertices,0,Triangles));Check(d->EndScene());
    }
    std::cout<<"PASS interpreter capture fixture: draws=4 triangles="<<Triangles<<"\n";
}
