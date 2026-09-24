// Offline diagnostic composition. No game material/depth/blend-state replay.
void PositionGroupFixture() {
    using namespace rrt::shader::position;
    auto line=[](std::size_t maximum){std::string s;char c;while(std::cin.get(c)&&c!='\n'){Need(s.size()<maximum,"group input bound");s+=c;}Need(bool(std::cin),"truncated group input");return s;};
    auto header=line(32);const bool colorMode=header=="RRT_POSITION_COLOR1";Need(colorMode||header=="RRT_POSITION_GROUP1","group header");
    auto countText=line(2);Need(!countText.empty()&&countText.size()<=2,"group count");unsigned count=0;
    for(auto c:countText){Need(c>='0'&&c<='9',"group count");count=count*10+c-'0';}
    Need(count>=1&&count<=16&&std::to_string(count)==countText,"group count");
    auto hex=[&](std::size_t maximum){auto s=line(maximum*2);Need(s.size()%2==0,"group hex alignment");std::vector<std::uint8_t> b(s.size()/2);
        auto digit=[](char c){Need((c>='0'&&c<='9')||(c>='a'&&c<='f'),"group hex");return c<='9'?c-'0':c-'a'+10;};
        for(std::size_t i=0;i<b.size();++i)b[i]=static_cast<std::uint8_t>(digit(s[2*i])*16+digit(s[2*i+1]));return b;};
    auto program=hex(612);Admit(program);
    auto word=[&](){auto s=line(10);Need(!s.empty(),"color integer");std::uint64_t value{};for(char c:s){Need(c>='0'&&c<='9',"color integer");value=value*10+c-'0';Need(value<=0xffffffff,"color integer bound");}Need(std::to_string(value)==s,"color integer form");return static_cast<DWORD>(value);};
    const DWORD clearColor=colorMode?word():0;
    struct Input {float p[3],uv[2],uv1[2],color[4];};
    struct Batch {Constants constants{};std::vector<Input> input;std::vector<Result> evaluated;std::array<float,4> rgba{};DWORD blend{},src=2,dst=1;};
    std::vector<Batch> batches;
    for(unsigned i=0;i<count;++i){auto constants=hex(128),positions=hex(4096*3*12);
        Need(constants.size()==128&&!positions.empty()&&positions.size()%36==0,"group input shape");Batch batch;
        memcpy(batch.constants.rows.data(),constants.data(),128);batch.constants.known.fill(true);
        if(!colorMode&&!batches.empty())for(unsigned row=1;row<=4;++row)Need(batch.constants.rows[row]==batches[0].constants.rows[row],"mixed group clip rows");
        batch.input.resize(positions.size()/12);
        for(std::size_t j=0;j<batch.input.size();++j){memcpy(batch.input[j].p,positions.data()+j*12,12);auto p=batch.input[j].p;batch.evaluated.push_back(Evaluate({p[0],p[1],p[2]},batch.constants));}
        if(colorMode){auto rgba=hex(16);Need(rgba.size()==16,"color shape");memcpy(batch.rgba.data(),rgba.data(),16);for(float v:batch.rgba)Need(std::isfinite(v)&&v>=0&&v<=1,"color range");
            batch.blend=word();batch.src=word();batch.dst=word();auto factor=[](DWORD x){return x==1||x==2||x==5||x==6;};Need(batch.blend<=1&&factor(batch.src)&&factor(batch.dst),"color blend subset");}
        batches.push_back(std::move(batch));
    }
    char trailing;Need(!std::cin.get(trailing),"trailing group input"); // All bounds/values validated before GPU creation.
    Device source(true);auto d=source.device.Get();
    ComPtr<IDirect3DVertexShader9> native,pass;ComPtr<IDirect3DPixelShader9> pixel;
    std::array<DWORD,153> code{};memcpy(code.data(),program.data(),612);Check(d->CreateVertexShader(code.data(),&native));
    auto compile=[](const char* text,const char* profile){ComPtr<ID3DBlob> blob,error;Check(D3DCompile(text,strlen(text),nullptr,nullptr,nullptr,"main",profile,D3DCOMPILE_OPTIMIZATION_LEVEL3,0,&blob,&error));return blob;};
    auto vs=compile("struct O{float4 p:POSITION;float4 m:TEXCOORD4;}; O main(float4 p:POSITION,float4 m:TEXCOORD4){O o;o.p=p;o.m=m;return o;}","vs_2_0");
    auto ps=compile("float4 main(float4 m:TEXCOORD4):COLOR{return float4(m.xyz,1);}","ps_2_0");
    Check(d->CreateVertexShader(static_cast<const DWORD*>(vs->GetBufferPointer()),&pass));Check(d->CreatePixelShader(static_cast<const DWORD*>(ps->GetBufferPointer()),&pixel));
    if(colorMode){pixel.Reset();Check(d->CreatePixelShader(ColorProgram.data(),&pixel));}
    D3DVERTEXELEMENT9 nl[]={{0,0,D3DDECLTYPE_FLOAT3,0,D3DDECLUSAGE_POSITION,0},{0,12,D3DDECLTYPE_FLOAT2,0,D3DDECLUSAGE_TEXCOORD,0},{0,20,D3DDECLTYPE_FLOAT2,0,D3DDECLUSAGE_TEXCOORD,1},{0,28,D3DDECLTYPE_FLOAT4,0,D3DDECLUSAGE_COLOR,0},D3DDECL_END()};
    D3DVERTEXELEMENT9 cl[]={{0,0,D3DDECLTYPE_FLOAT4,0,D3DDECLUSAGE_POSITION,0},{0,16,D3DDECLTYPE_FLOAT4,0,D3DDECLUSAGE_TEXCOORD,4},D3DDECL_END()};
    ComPtr<IDirect3DVertexDeclaration9> nd,cd;Check(d->CreateVertexDeclaration(nl,&nd));Check(d->CreateVertexDeclaration(cl,&cd));
    ComPtr<IDirect3DSurface9> target,read;Check(d->CreateRenderTarget(128,96,D3DFMT_A32B32G32R32F,D3DMULTISAMPLE_NONE,0,FALSE,&target,nullptr));
    Check(d->CreateOffscreenPlainSurface(128,96,D3DFMT_A32B32G32R32F,D3DPOOL_SYSTEMMEM,&read,nullptr));
    Check(d->SetRenderTarget(0,target.Get()));Check(d->SetDepthStencilSurface(nullptr));Configure(d);Check(d->SetPixelShader(pixel.Get()));
    if(colorMode)for(auto [state,value]:ColorExtraStates)Check(d->SetRenderState(state,value));
    auto render=[&](bool cpu){
        Check(d->Clear(0,nullptr,D3DCLEAR_TARGET,clearColor,1,0));Check(d->SetVertexShader(cpu?pass.Get():native.Get()));Check(d->SetVertexDeclaration(cpu?cd.Get():nd.Get()));
        Check(d->BeginScene());
        for(const auto& batch:batches){constexpr UINT registers[]={0,4,5,6,7,58,59,60};for(unsigned i=0;i<8;++i)Check(d->SetVertexShaderConstantF(registers[i],batch.constants.rows[i].data(),1));
            if(colorMode){Check(d->SetPixelShaderConstantF(0,batch.rgba.data(),1));Check(d->SetRenderState(D3DRS_ALPHABLENDENABLE,batch.blend));Check(d->SetRenderState(D3DRS_SRCBLEND,batch.src));Check(d->SetRenderState(D3DRS_DESTBLEND,batch.dst));Check(d->SetRenderState(D3DRS_BLENDOP,D3DBLENDOP_ADD));}
            float extra[4]={0,0,0,1};Check(d->SetVertexShaderConstantF(12,extra,1));Check(d->SetVertexShaderConstantF(16,extra,1));
            Check(d->DrawPrimitiveUP(D3DPT_TRIANGLELIST,static_cast<UINT>(batch.input.size()/3),cpu?static_cast<const void*>(batch.evaluated.data()):static_cast<const void*>(batch.input.data()),cpu?sizeof(Result):sizeof(Input)));}
        Check(d->EndScene());Check(d->GetRenderTargetData(target.Get(),read.Get()));D3DLOCKED_RECT locked{};Check(read->LockRect(&locked,nullptr,D3DLOCK_READONLY));
        std::vector<float> output(128*96*4);for(unsigned y=0;y<96;++y)memcpy(output.data()+y*128*4,static_cast<const char*>(locked.pBits)+y*locked.Pitch,128*16);Check(read->UnlockRect());return output;
    };
    auto actual=render(false),expected=render(true);double worst=0;unsigned covered=0;
    for(std::size_t i=0;i<actual.size();i+=4){Need(actual[i+3]==expected[i+3],"group coverage mismatch");if(actual[i+3]!=0)++covered;
        for(unsigned j=0;j<4;++j){Need(std::isfinite(actual[i+j])&&std::isfinite(expected[i+j]),"group nonfinite output");double e=std::abs(double(actual[i+j])-expected[i+j])/(1+std::abs(double(expected[i+j])));worst=std::max(worst,e);Need(e<=2e-4,"group interpolation mismatch");}}
    // Non-cryptographic diagnostic fingerprint, never source/asset identity.
    std::uint64_t hash=14695981039346656037ull;for(std::size_t i=0;i<actual.size()*4;++i){hash^=reinterpret_cast<const unsigned char*>(actual.data())[i];hash*=1099511628211ull;}
    std::cout<<"{\"status\":\""<<(covered?"matched":"empty")<<"\",\"draws\":"<<count<<",\"covered\":"<<covered<<",\"max_normalized_error\":"<<worst<<",\"fingerprint_fnv1a64\":\""<<hash<<"\",\"width\":128,\"height\":96";
    if(colorMode){std::cout<<",\"mode\":\"constant_rgba_color\",\"center\":[";for(unsigned c=0;c<4;++c){if(c)std::cout<<",";std::cout<<actual[(48*128+64)*4+c];}std::cout<<"],\"background\":[";for(unsigned c=0;c<4;++c){if(c)std::cout<<",";std::cout<<actual[c];}std::cout<<"]";}
    std::cout<<"}\n";
}
