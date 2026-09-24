// Isolated material diagnostic; normalized raster state never implies frame equivalence.
#include "reconstructed_pixel.inc"
#include <bcrypt.h>
namespace scene=rrt::scene;
struct PixelMipLayout {std::size_t rowBytes{},rows{};};
PixelMipLayout PixelLayout(DWORD width,DWORD height,DWORD format){
    Need(width&&height&&width<=16384&&height<=16384,"pixel mip dimensions");
    if(format==D3DFMT_A8R8G8B8||format==D3DFMT_X8R8G8B8)return {std::size_t(width)*4,height};
    Need(format==D3DFMT_DXT1||format==D3DFMT_DXT3||format==D3DFMT_DXT5,"pixel texture format");
    return {std::size_t((width+3)/4)*(format==D3DFMT_DXT1?8:16),(height+3)/4};
}
void PixelReplayFixture(){
    using namespace rrt::shader::position;
    auto line=[](std::size_t max){std::string s;char c;while(std::cin.get(c)&&c!='\n'){Need(s.size()<max,"pixel input bound");s+=c;}Need(bool(std::cin),"truncated pixel input");return s;};
    auto header=line(32);Need(header=="RRT_PIXEL_REPLAY1"||header=="RRT_PIXEL_REPLAY2","pixel header");
    auto hex=[&](std::size_t max){auto s=line(max*2);Need(s.size()%2==0,"pixel hex shape");std::vector<std::uint8_t> bytes(s.size()/2);
        auto digit=[](char c){Need((c>='0'&&c<='9')||(c>='a'&&c<='f'),"pixel hex");return c<='9'?c-'0':c-'a'+10;};
        for(std::size_t i=0;i<bytes.size();++i)bytes[i]=static_cast<std::uint8_t>(digit(s[2*i])*16+digit(s[2*i+1]));return bytes;};
    auto word=[&](){auto s=line(10);std::uint64_t n=0;Need(!s.empty(),"pixel integer");for(char c:s){Need(c>='0'&&c<='9',"pixel integer");n=n*10+c-'0';Need(n<=0xffffffff,"pixel integer bound");}Need(std::to_string(n)==s,"pixel integer form");return DWORD(n);};
    DWORD width=128,height=96;D3DVIEWPORT9 viewport{0,0,128,96,0,1};
    if(header=="RRT_PIXEL_REPLAY2"){
        width=word();height=word();viewport.X=word();viewport.Y=word();viewport.Width=word();viewport.Height=word();
        auto lo=word(),hi=word();memcpy(&viewport.MinZ,&lo,4);memcpy(&viewport.MaxZ,&hi,4);
    }
    Need(width&&height&&width<=8192&&height<=8192&&std::uint64_t(width)*height<=8000000,"pixel target budget");
    Need(viewport.Width&&viewport.Height&&std::uint64_t(viewport.X)+viewport.Width<=width&&std::uint64_t(viewport.Y)+viewport.Height<=height&&
        std::isfinite(viewport.MinZ)&&std::isfinite(viewport.MaxZ)&&viewport.MinZ>=0&&viewport.MinZ<=viewport.MaxZ&&viewport.MaxZ<=1,"pixel viewport bounds");
    auto vs=hex(612),ps=hex(1792),vc=hex(128),extraBytes=hex(32),pc=hex(64),vertices=hex(1024*3*48);Admit(vs);
    Need(ps.size()==1792&&vc.size()==128&&extraBytes.size()==32&&pc.size()==64&&!vertices.empty()&&vertices.size()%144==0,"pixel input shape");
    constexpr scene::Hash expected={0xad,0x23,0x0b,0xcd,0xf0,0x5a,0xbd,0xbb,0x55,0x84,0x51,0x94,0x3e,0x3d,0xcc,0x7c,0x4e,0x99,0x95,0xb2,0x89,0x05,0xd8,0x7e,0xa3,0xc3,0x9d,0x1b,0x29,0xd7,0x6a,0x11};
    Need(scene::Digest(ps.data(),ps.size())==expected,"pixel program not admitted");
    Constants constants{};constants.known.fill(true);memcpy(constants.rows.data(),vc.data(),128);std::array<Vec,2> extra{};memcpy(extra.data(),extraBytes.data(),32);
    std::array<Vec,4> pixelConstants{};memcpy(pixelConstants.data(),pc.data(),64);for(auto r:pixelConstants)for(float v:r)Need(std::isfinite(v),"pixel constant nonfinite");
    for(std::size_t i=0;i<vertices.size();i+=48){std::array<float,3> p{};std::array<float,4> uv{};DWORD color{};memcpy(p.data(),vertices.data()+i,12);memcpy(&color,vertices.data()+i+24,4);memcpy(uv.data(),vertices.data()+i+28,16);EvaluateMaterial(p,uv,color,constants,extra);}
    struct Texture{DWORD width{},height{},format{},levels{},lod{};std::array<DWORD,13> states{};std::vector<std::vector<std::uint8_t>> mips;};
    std::array<Texture,2> textures;
    for(auto& t:textures){t.width=word();t.height=word();t.format=word();t.levels=word();t.lod=word();
        PixelLayout(t.width,t.height,t.format);
        Need(t.levels>0&&t.levels<=16&&t.lod<t.levels,"pixel texture shape");
        UINT maximumLevels=1;for(auto extent=(std::max)(t.width,t.height);extent>1;extent>>=1)++maximumLevels;
        Need(t.levels<=maximumLevels,"pixel mip count");
        if(t.format!=21&&t.format!=22)Need(t.width%4==0&&t.height%4==0,"pixel compressed base alignment");
        for(auto& s:t.states)s=word();
        for(unsigned i=0;i<3;++i)Need(t.states[i]>=1&&t.states[i]<=4,"pixel address subset");
        Need((t.states[4]==1||t.states[4]==2)&&(t.states[5]==1||t.states[5]==2)&&t.states[6]<=2&&t.states[8]<t.levels&&t.states[9]==1&&t.states[10]<=1&&t.states[11]==0&&t.states[12]==0,"pixel sampler subset");
        float bias{};memcpy(&bias,&t.states[7],4);Need(std::isfinite(bias)&&std::abs(bias)<=4,"pixel LOD bias");
        std::size_t total=0;for(UINT level=0;level<t.levels;++level){auto layout=PixelLayout((std::max)(DWORD(1),t.width>>level),(std::max)(DWORD(1),t.height>>level),t.format);auto size=layout.rowBytes*layout.rows;Need(size<=16*1024*1024&&total+size<=16*1024*1024,"pixel mip budget");auto mip=hex(size);total+=size;Need(mip.size()==size,"pixel mip size");t.mips.push_back(std::move(mip));}
    }
    char trailing;Need(!std::cin.get(trailing),"pixel trailing input");
    wchar_t control[64]{};GetEnvironmentVariableW(L"RRT_PIXEL_REPLAY_CONTROL",control,64);std::wstring mode=control;
    Device source(true);auto d=source.device.Get();std::array<ComPtr<IDirect3DTexture9>,2> nativeTextures;ComPtr<IDirect3DVertexShader9> vertex;ComPtr<IDirect3DPixelShader9> original,reconstructed;
    std::array<DWORD,153> vsCode{};memcpy(vsCode.data(),vs.data(),612);std::array<DWORD,448> psCode{};memcpy(psCode.data(),ps.data(),1792);
    Check(d->CreateVertexShader(vsCode.data(),&vertex));Check(d->CreatePixelShader(psCode.data(),&original));
    D3D_SHADER_MACRO oneSample[]={{"RRT_ONE_SAMPLE","1"},{nullptr,nullptr}};
    ComPtr<ID3DBlob> compiled,error;auto hr=D3DCompile(ReconstructedPixel,strlen(ReconstructedPixel),nullptr,mode==L"one_sample"?oneSample:nullptr,nullptr,"main","ps_2_b",D3DCOMPILE_OPTIMIZATION_LEVEL3|D3DCOMPILE_IEEE_STRICTNESS,0,&compiled,&error);
    if(FAILED(hr)&&error)std::cerr<<static_cast<const char*>(error->GetBufferPointer());Check(hr);Check(d->CreatePixelShader(static_cast<const DWORD*>(compiled->GetBufferPointer()),&reconstructed));
    for(UINT slot=0;slot<2;++slot){auto& t=textures[slot];auto& texture=nativeTextures[slot];Check(d->CreateTexture(t.width,t.height,t.levels,0,static_cast<D3DFORMAT>(t.format),D3DPOOL_MANAGED,&texture,nullptr));
        Need(texture->GetLevelCount()==t.levels,"pixel native mip count");for(UINT level=0;level<t.levels;++level){auto layout=PixelLayout((std::max)(DWORD(1),t.width>>level),(std::max)(DWORD(1),t.height>>level),t.format);
            D3DLOCKED_RECT lock{};Check(texture->LockRect(level,&lock,nullptr,0));Need(lock.pBits&&lock.Pitch>0&&std::size_t(lock.Pitch)>=layout.rowBytes,"pixel upload pitch");
            for(std::size_t y=0;y<layout.rows;++y)memcpy(static_cast<char*>(lock.pBits)+y*lock.Pitch,t.mips[level].data()+y*layout.rowBytes,layout.rowBytes);Check(texture->UnlockRect(level));
            Check(texture->LockRect(level,&lock,nullptr,D3DLOCK_READONLY));Need(lock.pBits&&lock.Pitch>0&&std::size_t(lock.Pitch)>=layout.rowBytes,"pixel readback pitch");
            for(std::size_t y=0;y<layout.rows;++y)Need(memcmp(static_cast<const char*>(lock.pBits)+y*lock.Pitch,t.mips[level].data()+y*layout.rowBytes,layout.rowBytes)==0,"pixel restored bytes");
            Check(texture->UnlockRect(level));}
        texture->SetLOD(t.lod);Check(d->SetTexture(slot,texture.Get()));for(unsigned i=0;i<13;++i)Check(d->SetSamplerState(slot,static_cast<D3DSAMPLERSTATETYPE>(i+1),t.states[i]));}
    D3DVERTEXELEMENT9 layout[]={{0,0,D3DDECLTYPE_FLOAT3,0,D3DDECLUSAGE_POSITION,0},{0,24,D3DDECLTYPE_D3DCOLOR,0,D3DDECLUSAGE_COLOR,0},{0,28,D3DDECLTYPE_FLOAT2,0,D3DDECLUSAGE_TEXCOORD,0},{0,36,D3DDECLTYPE_FLOAT2,0,D3DDECLUSAGE_TEXCOORD,1},D3DDECL_END()};
    ComPtr<IDirect3DVertexDeclaration9> decl;Check(d->CreateVertexDeclaration(layout,&decl));Check(d->SetVertexDeclaration(decl.Get()));Check(d->SetVertexShader(vertex.Get()));
    constexpr UINT rows[]={0,4,5,6,7,58,59,60};for(unsigned i=0;i<8;++i)Check(d->SetVertexShaderConstantF(rows[i],constants.rows[i].data(),1));Check(d->SetVertexShaderConstantF(12,extra[0].data(),1));Check(d->SetVertexShaderConstantF(16,extra[1].data(),1));
    constexpr UINT prows[]={11,12,29,30};for(unsigned i=0;i<4;++i)Check(d->SetPixelShaderConstantF(prows[i],pixelConstants[i].data(),1));
    ComPtr<IDirect3DSurface9> target,read;Check(d->CreateRenderTarget(width,height,D3DFMT_A32B32G32R32F,D3DMULTISAMPLE_NONE,0,FALSE,&target,nullptr));Check(d->CreateOffscreenPlainSurface(width,height,D3DFMT_A32B32G32R32F,D3DPOOL_SYSTEMMEM,&read,nullptr));
    Check(d->SetRenderTarget(0,target.Get()));Check(d->SetDepthStencilSurface(nullptr));Configure(d);for(auto [s,v]:ColorExtraStates)Check(d->SetRenderState(s,v));
    Check(d->SetRenderState(D3DRS_DEPTHBIAS,0));Check(d->SetRenderState(D3DRS_SLOPESCALEDEPTHBIAS,0));Check(d->SetNPatchMode(0));
    auto render=[&](IDirect3DPixelShader9* shader){Check(d->SetPixelShader(shader));D3DVIEWPORT9 full{0,0,width,height,0,1};Check(d->SetViewport(&full));Check(d->Clear(0,nullptr,D3DCLEAR_TARGET,0,1,0));Check(d->SetViewport(&viewport));Check(d->BeginScene());Check(d->DrawPrimitiveUP(D3DPT_TRIANGLELIST,UINT(vertices.size()/144),vertices.data(),48));Check(d->EndScene());
        Check(d->GetRenderTargetData(target.Get(),read.Get()));D3DLOCKED_RECT lock{};Check(read->LockRect(&lock,nullptr,D3DLOCK_READONLY));Need(lock.pBits&&lock.Pitch>0&&std::size_t(lock.Pitch)>=std::size_t(width)*16,"pixel target pitch");std::vector<float> pixels(std::size_t(width)*height*4);
        for(UINT y=0;y<height;++y)memcpy(pixels.data()+std::size_t(y)*width*4,static_cast<const char*>(lock.pBits)+y*lock.Pitch,std::size_t(width)*16);Check(read->UnlockRect());return pixels;};
    auto native=render(original.Get());
    if(mode==L"fog"){Vec zero{};Check(d->SetPixelShaderConstantF(11,zero.data(),1));}
    else if(mode==L"alpha"){auto value=pixelConstants[1];value[3]=0;Check(d->SetPixelShaderConstantF(12,value.data(),1));}
    else if(mode==L"address")Check(d->SetSamplerState(0,D3DSAMP_ADDRESSU,textures[0].states[0]==D3DTADDRESS_WRAP?D3DTADDRESS_CLAMP:D3DTADDRESS_WRAP));
    else if(mode==L"srgb")Check(d->SetSamplerState(0,D3DSAMP_SRGBTEXTURE,1-textures[0].states[10]));
    else if(mode==L"lod")nativeTextures[0]->SetLOD(textures[0].levels-1);
    else if(mode==L"filter")Check(d->SetSamplerState(0,D3DSAMP_MAGFILTER,textures[0].states[4]==D3DTEXF_LINEAR?D3DTEXF_POINT:D3DTEXF_LINEAR));
    else if(mode==L"texel"){auto& t=textures[0];for(UINT level=0;level<t.levels;++level){auto layout=PixelLayout((std::max)(DWORD(1),t.width>>level),(std::max)(DWORD(1),t.height>>level),t.format);D3DLOCKED_RECT lock{};Check(nativeTextures[0]->LockRect(level,&lock,nullptr,0));Need(lock.pBits&&lock.Pitch>0&&std::size_t(lock.Pitch)>=layout.rowBytes,"pixel control pitch");for(std::size_t y=0;y<layout.rows;++y)memset(static_cast<char*>(lock.pBits)+y*lock.Pitch,0,layout.rowBytes);Check(nativeTextures[0]->UnlockRect(level));}}
    else Need(mode.empty()||mode==L"one_sample","pixel control");
    auto actual=render(reconstructed.Get());double worst=0,alphaSum=0;unsigned covered=0;
    for(std::size_t i=0;i<native.size();++i){Need(std::isfinite(native[i])&&std::isfinite(actual[i]),"pixel nonfinite result");worst=(std::max)(worst,std::abs(double(native[i])-actual[i])/(1+std::abs(double(native[i]))));if(native[i]!=0)++covered;}
    for(std::size_t i=3;i<native.size();i+=4)alphaSum+=native[i];
    auto digest=[](const std::vector<float>& p){Need(p.size()<=8000000*4,"pixel hash budget");scene::Hash hash{};Need(BCryptHash(BCRYPT_SHA256_ALG_HANDLE,nullptr,0,reinterpret_cast<PUCHAR>(const_cast<float*>(p.data())),static_cast<ULONG>(p.size()*4),hash.data(),32)>=0,"pixel SHA256 failed");std::string s;const char* h="0123456789abcdef";for(auto b:hash){s+=h[b>>4];s+=h[b&15];}return s;};
    std::cout<<"{\"status\":\""<<(worst<=2e-4&&covered>100?"matched":"different")<<"\",\"max_normalized_error\":"<<worst<<",\"nonzero_lanes\":"<<covered<<",\"native_alpha_sum\":"<<alphaSum<<",\"native_sha256\":\""<<digest(native)<<"\",\"reconstructed_sha256\":\""<<digest(actual)<<"\"}\n";
}
