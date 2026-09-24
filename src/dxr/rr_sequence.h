#pragma once

// Bounded offline frames. The path constructor is stationary-only; the explicit
// recorded loader adds source identities/translation. Neither is live IPC.
struct RrSequence {
    std::vector<RrInputFile> frames;
    std::array<unsigned char,32> digest{};
    bool recorded{};
    std::array<std::array<unsigned char,32>,4> identities{};
    std::vector<UINT> segmentIndices;
    std::vector<std::array<float,3>> cameraDeltas;
    RrSequence()=default;
    explicit RrSequence(const std::filesystem::path& path) {
        const auto size=std::filesystem::file_size(path);
        Require(size>=24+2ull*RrInputFile::FileBytes+32&&size<=24+8ull*RrInputFile::FileBytes+32,"RR sequence size invalid");
        std::ifstream file(path,std::ios::binary); std::vector<unsigned char> bytes(static_cast<size_t>(size));
        Require(bool(file.read(reinterpret_cast<char*>(bytes.data()),bytes.size()))&&file.peek()==EOF,"RR sequence read failed");
        UINT header[4]{}; memcpy(header,bytes.data()+8,16);
        Require(!memcmp(bytes.data(),"RRTRRS01",8)&&header[0]==1&&header[1]>=2&&header[1]<=8&&header[2]==RrInputFile::FileBytes&&header[3]==0,"RR sequence header invalid");
        Require(size==24+uint64_t(header[1])*RrInputFile::FileBytes+32,"RR sequence count/size mismatch");
        digest=RrDigest(bytes.data(),bytes.size()-32);
        Require(!memcmp(digest.data(),bytes.data()+bytes.size()-32,32),"RR sequence checksum mismatch");
        frames.reserve(header[1]);
        for(UINT i=0;i<header[1];++i) {
            const auto begin=bytes.begin()+24+size_t(i)*RrInputFile::FileBytes;
            frames.emplace_back(std::vector<unsigned char>(begin,begin+RrInputFile::FileBytes),true);
            const auto& f=frames.back();
            if(f.header[7]) Require(f.header[4]==0&&f.header[5]==0,"RR reset segment must start at zero");
            else {
                Require(i>0,"RR sequence missing initial reset"); const auto& p=frames[i-1];
                Require(f.header[4]==p.header[4]+1&&f.header[5]==p.header[5]+1&&f.header[6]==p.header[6],"RR sequence frame/seed discontinuity");
                Require(!memcmp(f.matrices,p.matrices,48*sizeof(float)),"RR stationary camera changed");
                for(UINT k=0;k<16;++k) Require(std::abs(f.matrices[48+k]-p.matrices[16+k])<.0005f,"RR previous view mismatch");
                using namespace DirectX; XMFLOAT4X4 v{},projection{},vp{};
                memcpy(&v,p.matrices+16,64); memcpy(&projection,p.matrices+32,64);
                XMStoreFloat4x4(&vp,XMLoadFloat4x4(&v)*XMLoadFloat4x4(&projection));
                for(UINT k=0;k<16;++k) Require(std::abs(f.matrices[64+k]-reinterpret_cast<const float*>(&vp)[k])<.0005f,"RR previous projection mismatch");
                for(UINT pixel=0;pixel<f.pixelCount;++pixel) {
                    const auto& a=f.rows[pixel]; const auto& b=p.rows[pixel];
                    Require(!memcmp(a.data()+4,b.data()+4,11*sizeof(float))&&!memcmp(a.data()+19,b.data()+19,5*sizeof(float)),"RR stationary lighting/guides changed");
                }
            }
        }
    }
    void Save(const std::filesystem::path& path,const std::vector<std::vector<unsigned char>>& outputs,bool sqrtAlbedo=false,UINT settingId=0,UINT scaleId=0,UINT guideId=0) const {
        Require(outputs.size()==frames.size(),"RR incomplete sequence output");
        Require(!sqrtAlbedo||recorded,"encoded albedo requires recorded output");
        Require(!settingId||(recorded&&settingId<std::size(RrSettings)),"invalid configured output");
        Require(!scaleId||(recorded&&scaleId<std::size(RrScalePresets)),"invalid scaled output");
        Require(!guideId||(recorded&&guideId<std::size(RrGuidePresets)),"invalid guide output");
        const bool nativeV2=frames[0].width==256; const UINT outputBytes=56+frames[0].pixelCount*16+32;
        const UINT version=guideId?6u:nativeV2?5u:scaleId?4u:settingId?3u:sqrtAlbedo?2u:1u;
        const UINT header[]={version,UINT(frames.size()),outputBytes,(guideId?(nativeV2?1u<<31:0)|(guideId<<24):nativeV2?1u<<24:0)|(scaleId<<16)|(settingId<<1)|(sqrtAlbedo?1u:0u)};
        const char* magic=guideId?"RRTRRD06":nativeV2?"RRTRRD05":scaleId?"RRTRRD04":settingId?"RRTRRD03":recorded?(sqrtAlbedo?"RRTRRD02":"RRTRRD01"):"RRTRRT01";
        std::vector<unsigned char> bytes(56); memcpy(bytes.data(),magic,8); memcpy(bytes.data()+8,header,16); memcpy(bytes.data()+24,digest.data(),32);
        for(const auto& output:outputs) { Require(output.size()==outputBytes,"RR frame output size invalid"); bytes.insert(bytes.end(),output.begin(),output.end()); }
        const auto hash=RrDigest(bytes.data(),bytes.size()); bytes.insert(bytes.end(),hash.begin(),hash.end());
        RrHandle file; file.value=CreateFileW(path.c_str(),GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
        Require(file.value!=INVALID_HANDLE_VALUE,"RR sequence output exists or unavailable"); DWORD written{};
        Require(WriteFile(file.value,bytes.data(),DWORD(bytes.size()),&written,nullptr)&&written==bytes.size(),"RR sequence output write failed");
    }
};
