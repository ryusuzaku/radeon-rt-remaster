#pragma once

bool RrNear(double a,double b) { return std::isfinite(a)&&std::isfinite(b)&&std::abs(a-b)<=.0005*std::max({1.,std::abs(a),std::abs(b)}); }
std::array<double,4> RrTransform(const std::array<double,4>& v,const float* m) {
    std::array<double,4> result{};
    for(UINT j=0;j<4;++j) for(UINT k=0;k<4;++k) result[j]+=v[k]*m[k*4+j];
    return result;
}
std::array<double,3> RrEye(const float* view) {
    std::array<double,3> result{};
    for(UINT j=0;j<3;++j) for(UINT k=0;k<3;++k) result[j]-=double(view[12+k])*view[j*4+k];
    return result; // rigid row-vector view: eye = -translation * rotation transpose
}
void LoadRrRecording(RrSequence& result,const std::filesystem::path& path) {
    constexpr size_t Prefix=236,MinStride=36+RrInputFile::FileBytes,MaxStride=36+RrInputFile::NativeFileBytes;
    const auto size=std::filesystem::file_size(path);
    Require(size>=Prefix+2*MinStride+32&&size<=Prefix+8*MaxStride+32,"RR recording size invalid");
    std::ifstream file(path,std::ios::binary); std::vector<unsigned char> bytes(static_cast<size_t>(size));
    Require(bool(file.read(reinterpret_cast<char*>(bytes.data()),bytes.size()))&&file.peek()==EOF,"RR recording read failed");
    UINT header[4]{}; memcpy(header,bytes.data()+8,16);
    const bool legacy=!memcmp(bytes.data(),"RRTRRC01",8)&&header[0]==1&&header[2]==RrInputFile::FileBytes;
    const bool nativeV2=!memcmp(bytes.data(),"RRTRRC02",8)&&header[0]==2&&header[2]==RrInputFile::NativeFileBytes;
    Require((legacy||nativeV2)&&header[1]>=2&&header[1]<=8&&header[3]==84,"RR recording header invalid");
    const size_t Stride=36+header[2];
    Require(size==Prefix+header[1]*Stride+32,"RR recording count mismatch");
    result.digest=RrDigest(bytes.data(),bytes.size()-32);
    Require(!memcmp(result.digest.data(),bytes.data()+bytes.size()-32,32),"RR recording checksum mismatch");
    for(UINT k=0;k<3;++k) memcpy(result.identities[k].data(),bytes.data()+24+k*32,32);
    memcpy(result.identities[3].data(),bytes.data()+204,32);
    Require(result.identities[0]!=std::array<unsigned char,32>{}&&result.identities[2]!=std::array<unsigned char,32>{},"RR missing identity");
    Require(result.identities[3]==RrDigest(bytes.data()+120,84),"RR settings checksum mismatch");
    UINT settings[4]{}; float values[17]{}; memcpy(settings,bytes.data()+120,16); memcpy(values,bytes.data()+136,68);
    Require(settings[0]==3&&settings[2]<=1&&(settings[3]==UINT32_MAX||(settings[3]>0&&settings[3]<header[1])),"RR settings invalid");
    for(float v:values) Require(std::isfinite(v),"RR nonfinite setting");
    double light=0; for(UINT k=0;k<3;++k) { Require(std::abs(values[k])<1000,"RR light range"); light+=double(values[k])*values[k]; }
    Require(light>1e-12,"RR zero light direction");
    for(UINT k=3;k<8;++k) Require(values[k]>=0&&values[k]<=32,"RR lighting range");
    Require(values[8]>=0&&values[8]<=1&&std::abs(values[12])<=360&&std::abs(values[13])<=89,"RR radius/orientation range");
    for(UINT k=0;k<3;++k) Require(std::abs(values[9+k])<1e5&&std::abs(values[14+k])<=2,"RR trajectory range");
    result.frames.reserve(header[1]); UINT segment=0; std::array<float,3> previousPose{values[9],values[10],values[11]};
    for(UINT i=0;i<header[1];++i) {
        const size_t start=Prefix+i*Stride; UINT meta[4]{}; float pose[5]{};
        memcpy(meta,bytes.data()+start,16); memcpy(pose,bytes.data()+start+16,20);
        for(UINT k=0;k<5;++k) Require(std::isfinite(pose[k]),"RR pose nonfinite");
        for(UINT k=0;k<3;++k) Require(pose[k]==values[9+k]+float(i)*values[14+k],"RR pose mismatch");
        Require(pose[3]==values[12]&&pose[4]==values[13],"RR orientation changed");
        float distance=0; for(UINT k=0;k<3;++k) { const float d=pose[k]-previousPose[k]; distance+=d*d; }
        const UINT reason=(i?0u:1u)|(i==settings[3]?2u:0u)|((i&&distance>1)?4u:0u);
        if(reason) segment=0;
        Require(meta[0]==i&&meta[1]==segment&&meta[2]==reason&&meta[3]==0,"RR recording order/reset mismatch");
        const auto begin=bytes.begin()+start+36;
        result.frames.emplace_back(std::vector<unsigned char>(begin,begin+header[2]),true,true);
        const auto& f=result.frames.back(); const auto& previous=reason?f:result.frames[i-1];
        Require(f.header[4]==i&&f.header[5]==segment&&f.header[6]==settings[1]&&f.header[7]==(reason?1u:0u),"RR frame provenance mismatch");
        if(i) Require(!memcmp(f.matrices+32,result.frames[0].matrices+32,64),"RR projection changed");
        const auto eye=RrEye(f.matrices+16),firstEye=RrEye(result.frames[0].matrices+16),previousEye=RrEye(previous.matrices+16);
        for(UINT r=0;r<3;++r) {
            for(UINT c=0;c<3;++c) Require(RrNear(f.matrices[16+r*4+c],result.frames[0].matrices[16+r*4+c]),"RR camera rotation changed");
            Require(RrNear(eye[r]-firstEye[r],double(pose[r])-values[9+r]),"RR camera/trajectory mismatch");
        }
        for(UINT k=0;k<16;++k) Require(RrNear(f.matrices[48+k],previous.matrices[16+k]),"RR previous view mismatch");
        for(UINT r=0;r<4;++r) for(UINT c=0;c<4;++c) {
            double value=0; for(UINT k=0;k<4;++k) value+=double(previous.matrices[16+r*4+k])*previous.matrices[32+k*4+c];
            Require(RrNear(f.matrices[64+r*4+c],value),"RR previous projection mismatch");
        }
        for(UINT pixel=0;pixel<f.pixelCount;++pixel) {
            const auto& row=f.rows[pixel]; if(!row[23]||reason) continue;
            const std::array<double,4> position{row[20],row[21],row[22],1};
            const auto clip=RrTransform(position,f.matrices+64),z=RrTransform(position,f.matrices+48);
            Require(clip[3]>1e-8,"RR invalid previous projection requires reset");
            const double motion[]={clip[0]/clip[3]*.5+.5-(pixel%f.width+.5)/f.width,.5-clip[1]/clip[3]*.5-(pixel/f.width+.5)/f.height,z[2]-row[19]};
            for(UINT k=0;k<3;++k) Require(RrNear(row[16+k],motion[k]),"RR motion reprojection mismatch");
        }
        std::array<float,3> delta{};
        for(UINT k=0;k<3;++k) { delta[k]=reason?0.f:float(previousEye[k]-eye[k]); previousPose[k]=pose[k]; }
        result.cameraDeltas.push_back(delta); result.segmentIndices.push_back(segment++);
    }
    result.recorded=true;
}
