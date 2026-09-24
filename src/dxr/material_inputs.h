// Private, static authoring inputs. No scene mutation or runtime JSON dependency.
struct PbrMaterial {
    float base[3]{1,1,1},roughness{1},emission[3]{},metallic{};
};
static_assert(sizeof(PbrMaterial)==32);
struct MaterialInputs {
    std::map<rrt::scene::Hash,PbrMaterial> records;
    std::string digest;
};
MaterialInputs LoadMaterials(const std::filesystem::path& path,const rrt::scene::Scene& scene) {
    MaterialInputs result; if(path.empty()) return result;
    std::ifstream file(path,std::ios::binary|std::ios::ate); Require(file.good(),"cannot open material sidecar");
    const auto length=file.tellg(); Require(length>=48 && length<=48+64*rrt::scene::MaxDraws,"invalid material sidecar size");
    std::vector<std::uint8_t> bytes(static_cast<std::size_t>(length)); file.seekg(0);
    file.read(reinterpret_cast<char*>(bytes.data()),bytes.size()); Require(file.good(),"material sidecar read failed");
    rrt::scene::Hash checksum{}; memcpy(checksum.data(),bytes.data()+bytes.size()-32,32);
    Require(checksum==rrt::scene::Digest(bytes.data(),bytes.size()-32),"material sidecar checksum mismatch");
    Require(memcmp(bytes.data(),"RRTMAT1\0",8)==0,"invalid material sidecar magic");
    UINT version{},count{}; memcpy(&version,bytes.data()+8,4); memcpy(&count,bytes.data()+12,4);
    Require(version==1 && count<=rrt::scene::MaxDraws && bytes.size()==48+std::size_t(count)*64,"invalid material sidecar version/count");
    std::set<rrt::scene::Hash> known; for(const auto& draw:scene.draws) known.insert(draw.materialId);
    rrt::scene::Hash previous{};
    for(UINT i=0;i<count;++i) {
        const auto* record=bytes.data()+16+std::size_t(i)*64; rrt::scene::Hash id{}; PbrMaterial material;
        memcpy(id.data(),record,32); memcpy(&material,record+32,32);
        Require(i==0 || previous<id,"duplicate or unsorted material target"); previous=id;
        Require(known.contains(id),"unmatched material target");
        for(float value:material.base) Require(std::isfinite(value) && value>=0 && value<=1,"invalid material base colour");
        for(float value:material.emission) Require(std::isfinite(value) && value>=0 && value<=32,"invalid material emission");
        Require(std::isfinite(material.roughness) && material.roughness>=.05f && material.roughness<=1,"invalid material roughness");
        Require(std::isfinite(material.metallic) && material.metallic>=0 && material.metallic<=1,"invalid material metallic");
        result.records.emplace(id,material);
    }
    result.digest=rrt::scene::Hex(rrt::scene::Digest(bytes.data(),bytes.size())); return result;
}
