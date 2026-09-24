#pragma once

struct RcPathSequenceFixture {
    std::vector<RcCacheInput> predictions,training;
    std::vector<RcCacheOutput> targets;
    std::vector<std::array<float,3>> throughput,direct,sourceIndirect;
    std::vector<uint32_t> pixels;
    std::string artifactSha256;
};

std::array<unsigned char,32> RcSha256(const void* data,size_t size) {
    Require(size<=ULONG_MAX,"RC path artifact exceeds SHA256 input range"); std::array<unsigned char,32> hash{};
    Require(BCryptHash(BCRYPT_SHA256_ALG_HANDLE,nullptr,0,const_cast<PUCHAR>(static_cast<const UCHAR*>(data)),ULONG(size),hash.data(),ULONG(hash.size()))>=0,"RC path SHA256 failed");
    return hash;
}
std::string RcHex(const unsigned char* bytes,size_t size) {
    static const char digits[]="0123456789abcdef"; std::string result(size*2,'0');
    for(size_t i=0;i<size;++i) { result[i*2]=digits[bytes[i]>>4]; result[i*2+1]=digits[bytes[i]&15]; } return result;
}
template<class T> T RcPathPod(const std::vector<unsigned char>& bytes,size_t offset) {
    Require(offset<=bytes.size()&&sizeof(T)<=bytes.size()-offset,"truncated RC path artifact"); T value{}; std::memcpy(&value,bytes.data()+offset,sizeof(T)); return value;
}
std::array<float,2> RcSpherical(const float* value) {
    const float z=std::clamp(value[2],-1.0f,1.0f); float theta=std::acos(z)/(3.14159265358979323846f*.5f);
    theta=theta<1?std::sqrt(theta):2-std::sqrt(2-theta); return {theta*.5f,std::atan2(value[1],value[0])/(2*3.14159265358979323846f)+.5f};
}
constexpr size_t RcPathSequenceBytes=224+128*96*128+32;
RcPathSequenceFixture DecodeRcPathSequence(const std::vector<unsigned char>& bytes) {
    constexpr size_t Header=224,Rows=128*96,Stride=128,Bytes=RcPathSequenceBytes;
    Require(bytes.size()==Bytes,"RC path sequence size mismatch");
    const auto digest=RcSha256(bytes.data(),bytes.size()-32); Require(std::memcmp(digest.data(),bytes.data()+bytes.size()-32,32)==0,"RC path sequence checksum mismatch");
    Require(std::memcmp(bytes.data(),"RCRPATH1",8)==0,"RC path sequence magic mismatch");
    const uint32_t version=RcPathPod<uint32_t>(bytes,8),width=RcPathPod<uint32_t>(bytes,12),height=RcPathPod<uint32_t>(bytes,16),stride=RcPathPod<uint32_t>(bytes,20);
    const uint32_t pixels=RcPathPod<uint32_t>(bytes,24),declaredQueries=RcPathPod<uint32_t>(bytes,28),declaredTraining=RcPathPod<uint32_t>(bytes,32),randomIndex=RcPathPod<uint32_t>(bytes,36);
    Require(version==1&&width==128&&height==96&&stride==Stride&&pixels==Rows&&declaredQueries>0&&declaredQueries<=InferenceSamples
        &&declaredTraining==std::min(declaredQueries,TrainingSamples)&&randomIndex<4096,"unsupported RC path sequence contract");
    const auto settingsDigest=RcSha256(bytes.data()+160,64); Require(std::memcmp(settingsDigest.data(),bytes.data()+104,32)==0,"RC path settings checksum mismatch");
    float lower[3]{},upper[3]{}; std::memcpy(lower,bytes.data()+136,12); std::memcpy(upper,bytes.data()+148,12);
    for(UINT c=0;c<3;++c) Require(std::isfinite(lower[c])&&std::isfinite(upper[c])&&upper[c]-lower[c]>=1e-4f,"invalid RC path bounds");
    RcPathSequenceFixture result; result.artifactSha256=RcHex(digest.data(),digest.size());
    for(uint32_t pixel=0;pixel<Rows;++pixel) {
        float row[32]{}; std::memcpy(row,bytes.data()+Header+size_t(pixel)*Stride,Stride);
        for(float value:row) Require(std::isfinite(value),"nonfinite RC path row");
        Require((row[3]==0||row[3]==1)&&(row[31]==0||row[31]==1)&&row[3]<=row[31],"invalid RC path validity");
        if(!row[3]) continue;
        float normalLength=0,viewLength=0; for(UINT c=0;c<3;++c) { normalLength+=row[4+c]*row[4+c]; viewLength+=row[8+c]*row[8+c];
            Require(row[c]>=lower[c]-1e-4f&&row[c]<=upper[c]+1e-4f&&row[12+c]>=0&&row[12+c]<=1&&row[16+c]>=0&&row[20+c]>=0&&row[20+c]<=1
                &&std::abs(row[24+c]-row[20+c]*row[16+c])<=2e-5f,"invalid RC path query"); }
        Require(std::abs(normalLength-1)<1e-3f&&std::abs(viewLength-1)<1e-3f&&row[7]==1&&row[11]>=1&&row[27]>0,"invalid RC path surface tuple");
        RcCacheInput input{}; for(UINT c=0;c<3;++c) input.position[c]=(((row[c]-lower[c])/(upper[c]-lower[c])-.5f)/1.05f)+.5f;
        const auto normal=RcSpherical(row+4),view=RcSpherical(row+8); std::memcpy(input.normal,normal.data(),8); std::memcpy(input.viewDirection,view.data(),8);
        std::memcpy(input.diffuseAlbedo,row+12,12); input.roughness=row[7];
        for(float value:input.position) Require(value>=0&&value<=1,"RC path normalized position outside unit range");
        for(float value:input.normal) Require(value>=0&&value<=1,"RC path normalized normal outside unit range");
        for(float value:input.viewDirection) Require(value>=0&&value<=1,"RC path normalized view outside unit range");
        result.predictions.push_back(input); result.targets.push_back({{row[16],row[17],row[18]}}); result.throughput.push_back({row[20],row[21],row[22]});
        result.sourceIndirect.push_back({row[24],row[25],row[26]}); result.direct.push_back({row[28],row[29],row[30]}); result.pixels.push_back(pixel);
    }
    Require(result.predictions.size()==declaredQueries,"RC path sequence query count mismatch");
    result.training.assign(result.predictions.begin(),result.predictions.begin()+declaredTraining); return result;
}
RcPathSequenceFixture LoadRcPathSequence(const std::filesystem::path& path) {
    Require(path.is_absolute()&&std::filesystem::is_regular_file(path),"RC path sequence requires an absolute regular file");
    Require(std::filesystem::file_size(path)==RcPathSequenceBytes,"RC path sequence size mismatch");
    std::ifstream stream(path,std::ios::binary); Require(bool(stream),"RC path sequence open failed"); std::vector<unsigned char> bytes(RcPathSequenceBytes);
    stream.read(reinterpret_cast<char*>(bytes.data()),std::streamsize(bytes.size())); Require(stream&&stream.peek()==std::char_traits<char>::eof(),"RC path sequence read failed");
    return DecodeRcPathSequence(bytes);
}
