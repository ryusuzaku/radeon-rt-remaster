// Descriptors are observations, never initialized texel or alias/write claims.
std::string PixelMaterial(IDirect3DDevice9* d,const Knowledge& knowledge){
    auto require=[](bool ok,const char* reason){if(!ok)throw std::runtime_error(reason);};
    auto hex=[](const void* data,std::size_t size){std::string s;const char* h="0123456789abcdef";auto b=static_cast<const unsigned char*>(data);for(std::size_t i=0;i<size;++i){s+=h[b[i]>>4];s+=h[b[i]&15];}return s;};
    ComPtr<IDirect3DPixelShader9> ps;require(SUCCEEDED(d->GetPixelShader(&ps))&&ps,"pixel_material_shader");
    UINT size{};require(SUCCEEDED(ps->GetFunction(nullptr,&size))&&size==1792,"pixel_material_shader");
    std::array<DWORD,448> code{};require(SUCCEEDED(ps->GetFunction(code.data(),&size))&&size==1792,"pixel_material_shader");
    auto digest=scene::Digest(code.data(),size);require(hex(digest.data(),digest.size())=="ad230bcdf05abdbb558451943e3dcc7c4e9995b28905d87ea3c39d1b29d76a11","pixel_material_shader");
    std::array<std::array<float,4>,4> constants{};constexpr UINT rows[]={11,12,29,30};
    for(unsigned i=0;i<4;++i){require(knowledge.pixelConstants[rows[i]],"unknown_pixel_constants");require(SUCCEEDED(d->GetPixelShaderConstantF(rows[i],constants[i].data(),1)),"pixel_constant_query");for(float v:constants[i])require(std::isfinite(v),"nonfinite_pixel_constant");}
    std::string s=",\"pixel_material\":{\"constants\":\""+hex(constants.data(),64)+"\",\"samplers\":[";
    for(UINT slot=0;slot<2;++slot){
        ComPtr<IDirect3DBaseTexture9> base;require(SUCCEEDED(d->GetTexture(slot,&base))&&base&&base->GetType()==D3DRTYPE_TEXTURE,"pixel_texture_binding");
        ComPtr<IDirect3DTexture9> texture;require(SUCCEEDED(base.As(&texture))&&texture,"pixel_texture_binding");
        auto tag=Get(texture.Get(),true);require(bool(tag),"pixel_texture_identity");
        UINT levels=texture->GetLevelCount();require(levels>0&&levels<=16,"pixel_texture_budget");
        if(slot)s+=",";s+="{\"states\":[";
        for(unsigned state=1;state<=13;++state){DWORD value{};require(SUCCEEDED(d->GetSamplerState(slot,static_cast<D3DSAMPLERSTATETYPE>(state),&value)),"pixel_sampler_query");if(state>1)s+=",";s+=std::to_string(value);}
        s+="],\"texture\":{\"id\":"+std::to_string(tag->id)+",\"type\":3,\"levels\":"+std::to_string(levels)+",\"lod\":"+std::to_string(texture->GetLOD())+",\"autogen_filter\":"+std::to_string(texture->GetAutoGenFilterType())+",\"contents\":\"unknown\",\"descriptors\":[";
        for(UINT level=0;level<levels;++level){D3DSURFACE_DESC desc{};require(SUCCEEDED(texture->GetLevelDesc(level,&desc))&&desc.Width&&desc.Height&&desc.Width<=16384&&desc.Height<=16384,"pixel_texture_descriptor");
            if(level)s+=",";s+="["+std::to_string(desc.Width)+","+std::to_string(desc.Height)+","+std::to_string(desc.Format)+","+std::to_string(desc.Usage)+","+std::to_string(desc.Pool)+","+std::to_string(desc.MultiSampleType)+","+std::to_string(desc.MultiSampleQuality)+"]";}
        s+="]}}";
    }
    return s+"]}";
}
