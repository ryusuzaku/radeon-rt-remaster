// One coverage flag per complete texel/compressed block; all admitted writes use these units.
struct TextureMip {
    UINT width{},height{},unit{1},unitBytes{4},columns{},rows{};std::vector<std::uint8_t> bytes,known;
    const std::uint8_t* pointer{};INT pitch{};RECT rect{};bool pending{},copied{},dirtyOnUnlock{};
};
struct TextureShadow {
    std::vector<TextureMip> mips;std::uint64_t revision{},epoch{};std::size_t reserved{};
    D3DPOOL pool=D3DPOOL_MANAGED;D3DFORMAT format=D3DFMT_UNKNOWN;bool fullDirty=true;
    const char* dirtyProof="creation";const char* uploadDirtyProof{};
    const char* lastInvalidation="none";const char* lastUpload="none";
    DWORD lastLockFlags{},uploadSourceLockFlags{};bool lockObserved{},uploadSourceLockObserved{};
    const char* uploadSourceInvalidation="unavailable";
    std::uint64_t uploadSource{},uploadRevision{};
    std::vector<SurfaceTransfer> surfaceTransfers;
    ~TextureShadow(){Retained().fetch_sub(reserved);}
    void Invalidate(){lastInvalidation="internal";++revision;fullDirty=false;dirtyProof=uploadDirtyProof=nullptr;uploadSource=uploadRevision=0;surfaceTransfers.clear();for(auto& m:mips){std::fill(m.known.begin(),m.known.end(),0);m.pending=m.copied=false;m.pointer=nullptr;}}
};
