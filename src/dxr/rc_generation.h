#pragma once

// Stage 1 of docs/RC_STALENESS_POLICY.md: the admission generations derived from
// the renderer's own inputs instead of caller-issued constants. A generation is
// the first four bytes (big-endian) of SHA-256 over a canonical encoding, so it
// is reproducible and independent of how the inputs were assembled. The encoding
// and the field split mirror tools/rc_staleness.py, which pins them with known
// answers (tests/verify_rc_staleness_contract.py); VerifyRcGenerations() checks
// the same values here. Nothing in this header changes admission behaviour: the
// derived values are compared for equality exactly like the constants they
// replace, and every canonical scenario keeps them constant.

struct RcGenerations { std::uint64_t scene{},lighting{},material{},settings{}; };

// Lighting describes the one global sun plus ambient; settings describe how the
// paths are realized and accumulated. The two field sets are disjoint so that
// changing one never moves the other's generation.
struct RcLightingInputs { float light[3],sunRadius,lightColor[3],intensity,ambient; std::uint32_t shadows; };
struct RcSettingsInputs { std::uint32_t seed,flags,renderPercent; bool denoise,temporal; };

class RcGenerationWriter {
    std::vector<std::uint8_t> bytes;
    void Text(const char* text) { for(;*text;++text) bytes.push_back(static_cast<std::uint8_t>(*text)); }
public:
    void Field(const char* name) { Text(name); bytes.push_back(0); }
    void End() { bytes.push_back(0); }
    void Float(double value) {
        std::uint64_t bits; std::memcpy(&bits,&value,sizeof(bits)); bytes.push_back('f');
        for(unsigned i=0;i<8;++i) bytes.push_back(static_cast<std::uint8_t>(bits>>(8*i)));
    }
    void Int(std::uint64_t value) { bytes.push_back('i'); Text(std::to_string(value).c_str()); bytes.push_back(';'); }
    void Bool(bool value) { bytes.push_back('b'); bytes.push_back(value?'1':'0'); }
    void Vec3(const float* value) { bytes.push_back('v'); Text("3"); bytes.push_back(':'); for(unsigned i=0;i<3;++i) Float(value[i]); }
    std::uint64_t Generation() const {
        const auto digest=rrt::scene::Digest(bytes.data(),bytes.size());
        return (std::uint64_t(digest[0])<<24)|(std::uint64_t(digest[1])<<16)|(std::uint64_t(digest[2])<<8)|std::uint64_t(digest[3]);
    }
};

std::uint64_t RcLightingGeneration(const RcLightingInputs& in) {
    RcGenerationWriter w;
    w.Field("sun_direction"); w.Vec3(in.light); w.End();
    w.Field("sun_radius"); w.Float(in.sunRadius); w.End();
    w.Field("light_colour"); w.Vec3(in.lightColor); w.End();
    w.Field("intensity"); w.Float(in.intensity); w.End();
    w.Field("ambient"); w.Float(in.ambient); w.End();
    w.Field("shadows"); w.Int(in.shadows); w.End();
    return w.Generation();
}

std::uint64_t RcSettingsGeneration(const RcSettingsInputs& in) {
    RcGenerationWriter w;
    w.Field("seed"); w.Int(in.seed); w.End();
    w.Field("denoise"); w.Bool(in.denoise); w.End();
    w.Field("temporal"); w.Bool(in.temporal); w.End();
    w.Field("render_scale"); w.Int(in.renderPercent); w.End();
    w.Field("flags"); w.Int(in.flags); w.End();
    return w.Generation();
}

// Scene and material generations come from digests the caller owns. A material
// sidecar cannot be combined with the RC path export today, so without one the
// material digest input is a fixed tag; with one it is the sidecar path, a
// placeholder until a content digest exists.
std::uint64_t RcDigestGeneration(const void* data,std::size_t size) {
    const auto digest=rrt::scene::Digest(data,size);
    return (std::uint64_t(digest[0])<<24)|(std::uint64_t(digest[1])<<16)|(std::uint64_t(digest[2])<<8)|std::uint64_t(digest[3]);
}

RcGenerations RcGenerationsFor(const Frame& frame,const Options& options,const rrt::scene::Hash& sceneDigest) {
    RcGenerations g;
    RcLightingInputs lighting{}; std::memcpy(lighting.light,frame.light,sizeof(lighting.light)); lighting.sunRadius=frame.sunRadius;
    std::memcpy(lighting.lightColor,frame.lightColor,sizeof(lighting.lightColor)); lighting.intensity=frame.intensity; lighting.ambient=frame.ambient; lighting.shadows=frame.shadows;
    // Only the persistent setting bits (denoise, temporal, light tint, variance filter); the other
    // frame flag bits are per-dispatch state such as a forced reset.
    const RcSettingsInputs settings{frame.seed,frame.flags&53u,options.renderPercent,options.denoise,options.temporal};
    g.scene=RcDigestGeneration(sceneDigest.data(),sceneDigest.size());
    if(options.materialPath.empty()) { static const char none[]="rrt-rc-material:none"; g.material=RcDigestGeneration(none,sizeof(none)-1); }
    else { const std::string tag="rrt-rc-material:path:"+options.materialPath.string(); g.material=RcDigestGeneration(tag.data(),tag.size()); }
    g.lighting=RcLightingGeneration(lighting); g.settings=RcSettingsGeneration(settings);
    return g;
}

// Known answers computed by tools/rc_staleness.py for the same inputs. A
// mismatch means the C++ and Python encodings have drifted apart.
void VerifyRcGenerations() {
    const RcLightingInputs lighting{{-.5f,.5f,-1.f},.25f,{1.f,.5f,.25f},.75f,.125f,1};
    const RcSettingsInputs settings{1,3,100,false,false};
    Require(RcLightingGeneration(lighting)==121089966u,"RC lighting generation known answer mismatch");
    Require(RcSettingsGeneration(settings)==4205968792u,"RC settings generation known answer mismatch");
    const std::array<std::uint8_t,32> zero{}; Require(RcDigestGeneration(zero.data(),zero.size())==1718123181u,"RC scene generation known answer mismatch");
    static const char none[]="rrt-rc-material:none"; Require(RcDigestGeneration(none,sizeof(none)-1)==3197883127u,"RC material generation known answer mismatch");
    auto moved=lighting; moved.ambient=.25f; Require(RcLightingGeneration(moved)!=RcLightingGeneration(lighting)&&RcSettingsGeneration(settings)==4205968792u,"RC lighting change did not isolate");
    auto reseeded=settings; reseeded.seed=2; Require(RcSettingsGeneration(reseeded)!=RcSettingsGeneration(settings)&&RcLightingGeneration(lighting)==121089966u,"RC settings change did not isolate");
}
