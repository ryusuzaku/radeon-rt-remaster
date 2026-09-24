#pragma once

std::vector<UINT> RecordRr(Renderer& renderer,const Options& options,const rrt::scene::Hash& sceneDigest,std::vector<std::uint8_t>& bytes) {
    // Canonical serialization, never a raw Options/Frame struct with padding.
    auto append=[&](const void* p,size_t count) { auto data=static_cast<const std::uint8_t*>(p); bytes.insert(bytes.end(),data,data+count); };
    const UINT FrameBytes=360+renderer.scene.width*renderer.scene.height*96+32; constexpr UINT MetadataBytes=36;
    const UINT version=renderer.scene.width==128?1u:2u;
    bytes.reserve(236+options.samples*(FrameBytes+MetadataBytes)+32);
    const UINT header[]={version,options.samples,FrameBytes,84}; append(version==1?"RRTRRC01":"RRTRRC02",8); append(header,16); append(sceneDigest.data(),32);
    rrt::scene::Hash material{},shader{};
    if(!renderer.materialInputs.digest.empty()) for(UINT i=0;i<32;++i) material[i]=static_cast<std::uint8_t>(std::stoul(renderer.materialInputs.digest.substr(i*2,2),nullptr,16));
    append(material.data(),32); append(shader.data(),32);
    const UINT integers[]={options.mode,options.seed,options.shadows?1u:0u,options.rrResetFrame}; append(integers,16);
    append(options.light,12); append(options.lightColor,12); append(&options.lightIntensity,4); append(&options.ambient,4); append(&options.sunRadius,4);
    append(options.offset,12); append(&options.yaw,4); append(&options.pitch,4); append(options.rrStep,12);
    Require(bytes.size()==204,"RR recording settings layout mismatch");
    const auto settings=rrt::scene::Digest(bytes.data()+120,84); append(settings.data(),32);
    std::vector<UINT> pixels; UINT segmentIndex=0; Options previous=options;
    for(UINT i=0;i<options.samples;++i) {
        auto current=options;
        for(UINT k=0;k<3;++k) current.offset[k]=options.offset[k]+float(i)*options.rrStep[k];
        const bool explicitReset=i==options.rrResetFrame;
        renderer.Configure(current,explicitReset); pixels=renderer.Sample();
        const auto allocated=renderer.gpu.allocated;
        rrt::scene::Hash usedShader{};
        auto frame=PrepareRrInputs(renderer,renderer.randomSequence-1,&usedShader);
        // Preparation has returned: its temporary resources have been destroyed
        // after a completed fence. Retire only this scope's known buffer charge.
        Require(renderer.gpu.allocated-allocated==uint64_t(2)*renderer.scene.width*renderer.scene.height*96+512,"RR preparation accounting changed"); renderer.gpu.allocated=allocated;
        if(!i) { shader=usedShader; memcpy(bytes.data()+88,shader.data(),32); }
        else Require(shader==usedShader,"RR shader changed during recording");
        UINT reason=i?0u:1u; if(explicitReset) reason|=2;
        float distance=0; for(UINT k=0;k<3;++k) { const float d=current.offset[k]-previous.offset[k]; distance+=d*d; }
        if(i&&distance>1) reason|=4;
        Require(renderer.rrFrameReset==(reason!=0),"RR reset provenance mismatch");
        if(reason) segmentIndex=0;
        const UINT metadata[]={i,segmentIndex,reason,0}; append(metadata,16); append(current.offset,12); append(&current.yaw,4); append(&current.pitch,4);
        Require(frame.size()==FrameBytes,"RR recording frame size changed"); append(frame.data(),frame.size());
        ++segmentIndex; previous=current;
    }
    const auto digest=rrt::scene::Digest(bytes.data(),bytes.size()); append(digest.data(),32);
    return pixels;
}
