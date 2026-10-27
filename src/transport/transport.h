#pragma once
// Wire protocol between the 32-bit D3D9 proxy and the 64-bit renderer process.
// Layout and rules: docs/schemas/transport-v1.json and docs/TRANSPORT_PROTOCOL.md.
// Header-only, standard library only, so the x86 proxy and the x64 renderer include
// the same file. Every field is fixed width and naturally aligned; the static_asserts
// below fail the build in either architecture if a layout drifts from the schema.
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <vector>

namespace rrt::transport {

constexpr std::uint32_t Magic = 0x50545252u;  // "RRTP" on the wire (little-endian)
constexpr std::uint16_t SupportedVersion = 1;
constexpr std::size_t MaxMessageBytes = 4096;
constexpr std::uint32_t MaxInFlight = 2;
constexpr std::uint32_t MaxDimension = 16384;
constexpr std::uint32_t MaxSlots = 8;
constexpr std::uint32_t FlagSupersedePending = 1u << 0;
constexpr std::uint64_t MaxSceneBytes = 64ull * 1024 * 1024;

enum class Type : std::uint16_t { Hello = 1, HelloAck = 2, FrameSubmit = 3, FrameComplete = 4, Stop = 5, StopAck = 6, SceneAttach = 7, SceneAttachAck = 8 };
enum class Direction : std::uint8_t { ProxyToRenderer, RendererToProxy };
enum HelloAckStatus : std::uint32_t { AckOk = 0, AckVersionMismatch = 1, AckAdapterMismatch = 2, AckBusy = 3 };
enum FrameCompleteStatus : std::uint32_t { FrameReady = 0, FrameDiscarded = 1, FrameFailed = 2, FrameDeviceRemoved = 3 };
enum SceneAttachStatus : std::uint32_t { SceneOk = 0, SceneBadDigest = 1, SceneTooLarge = 2, SceneDecodeFailed = 3 };

// Same order as "errors" in the schema; the numeric values are what the golden-vector test prints.
enum class Error : std::uint8_t {
    Ok, ShortHeader, BadMagic, BadVersion, UnknownType, Oversized, PayloadSizeMismatch, BadFlags, ReservedNonzero,
    WrongDirection, OutOfSequence, UnexpectedState, BadFrameId, TooManyInFlight, UnknownFrame, GenerationMismatch, BadField
};

inline const char* ErrorName(Error error) {
    static const char* const names[] = {"ok", "short_header", "bad_magic", "bad_version", "unknown_type", "oversized", "payload_size_mismatch", "bad_flags", "reserved_nonzero",
        "wrong_direction", "out_of_sequence", "unexpected_state", "bad_frame_id", "too_many_in_flight", "unknown_frame", "generation_mismatch", "bad_field"};
    return names[static_cast<std::size_t>(error)];
}

struct Header {
    std::uint32_t magic; std::uint16_t version; std::uint16_t type; std::uint32_t payloadBytes; std::uint32_t flags;
    std::uint64_t sequence; std::uint64_t frameId;
};
struct Hello {
    std::uint32_t minVersion, maxVersion; std::uint64_t adapterLuid; std::uint32_t processId, capabilities, captureLevel, reserved;
};
struct HelloAck {
    std::uint32_t selectedVersion, status; std::uint64_t adapterLuid; std::uint32_t maxInFlight, capabilities; std::uint64_t reserved;
};
struct Generations { std::uint32_t scene, camera, lighting, material, settings; };
struct FrameSubmit {
    std::uint64_t fenceValue; std::uint32_t resourceSlot, width, height; Generations generations; std::uint64_t reserved;
};
// A SHA-256 digest travels as four u64 words in digest byte order (little-endian host and wire).
struct FrameComplete {
    std::uint64_t fenceValue; std::uint32_t status, resourceSlot; Generations generations; std::uint32_t reserved32; std::uint64_t outputSha256[4];
};
struct StopAck { std::uint32_t completedFrames, discardedFrames; std::uint64_t reserved; };
struct SceneAttach { std::uint64_t sectionHandle, sectionBytes, sha256[4]; std::uint32_t sceneGeneration, reserved; };
struct SceneAttachAck { std::uint32_t status, sceneGeneration, width, height; };

static_assert(sizeof(Header) == 32 && offsetof(Header, magic) == 0 && offsetof(Header, version) == 4 && offsetof(Header, type) == 6 &&
    offsetof(Header, payloadBytes) == 8 && offsetof(Header, flags) == 12 && offsetof(Header, sequence) == 16 && offsetof(Header, frameId) == 24);
static_assert(sizeof(Hello) == 32 && offsetof(Hello, minVersion) == 0 && offsetof(Hello, maxVersion) == 4 && offsetof(Hello, adapterLuid) == 8 &&
    offsetof(Hello, processId) == 16 && offsetof(Hello, capabilities) == 20 && offsetof(Hello, captureLevel) == 24 && offsetof(Hello, reserved) == 28);
static_assert(sizeof(HelloAck) == 32 && offsetof(HelloAck, selectedVersion) == 0 && offsetof(HelloAck, status) == 4 && offsetof(HelloAck, adapterLuid) == 8 &&
    offsetof(HelloAck, maxInFlight) == 16 && offsetof(HelloAck, capabilities) == 20 && offsetof(HelloAck, reserved) == 24);
static_assert(sizeof(FrameSubmit) == 48 && offsetof(FrameSubmit, fenceValue) == 0 && offsetof(FrameSubmit, resourceSlot) == 8 && offsetof(FrameSubmit, width) == 12 &&
    offsetof(FrameSubmit, height) == 16 && offsetof(FrameSubmit, generations) == 20 && offsetof(FrameSubmit, reserved) == 40);
static_assert(sizeof(FrameComplete) == 72 && offsetof(FrameComplete, fenceValue) == 0 && offsetof(FrameComplete, status) == 8 && offsetof(FrameComplete, resourceSlot) == 12 &&
    offsetof(FrameComplete, generations) == 16 && offsetof(FrameComplete, reserved32) == 36 && offsetof(FrameComplete, outputSha256) == 40);
static_assert(sizeof(SceneAttach) == 56 && offsetof(SceneAttach, sectionHandle) == 0 && offsetof(SceneAttach, sectionBytes) == 8 && offsetof(SceneAttach, sha256) == 16 &&
    offsetof(SceneAttach, sceneGeneration) == 48 && offsetof(SceneAttach, reserved) == 52);
static_assert(sizeof(SceneAttachAck) == 16 && offsetof(SceneAttachAck, status) == 0 && offsetof(SceneAttachAck, sceneGeneration) == 4 &&
    offsetof(SceneAttachAck, width) == 8 && offsetof(SceneAttachAck, height) == 12);
static_assert(sizeof(StopAck) == 16 && offsetof(StopAck, completedFrames) == 0 && offsetof(StopAck, discardedFrames) == 4 && offsetof(StopAck, reserved) == 8);
static_assert(sizeof(Generations) == 20 && offsetof(Generations, scene) == 0 && offsetof(Generations, camera) == 4 && offsetof(Generations, lighting) == 8 &&
    offsetof(Generations, material) == 12 && offsetof(Generations, settings) == 16);

struct Parsed {
    Header header{}; Type type{}; Direction direction{};
    union { Hello hello; HelloAck ack; FrameSubmit submit; FrameComplete complete; StopAck stopAck; SceneAttach attach; SceneAttachAck attachAck; } body{};
};

inline std::size_t PayloadSize(Type type) {
    switch (type) {
    case Type::Hello: return sizeof(Hello); case Type::HelloAck: return sizeof(HelloAck); case Type::FrameSubmit: return sizeof(FrameSubmit);
    case Type::FrameComplete: return sizeof(FrameComplete); case Type::Stop: return 0; case Type::StopAck: return sizeof(StopAck);
    case Type::SceneAttach: return sizeof(SceneAttach); case Type::SceneAttachAck: return sizeof(SceneAttachAck);
    }
    return 0;
}
inline Direction DirectionOf(Type type) {
    return (type == Type::Hello || type == Type::FrameSubmit || type == Type::Stop || type == Type::SceneAttach) ? Direction::ProxyToRenderer : Direction::RendererToProxy;
}
inline bool KnownType(std::uint16_t value) { return value >= 1 && value <= 8; }

// Builds a complete message (header plus payload) for sending. Fields are written in host order.
inline std::vector<std::uint8_t> Build(Type type, std::uint64_t sequence, std::uint64_t frameId, const void* payload, std::uint32_t flags = 0) {
    Header header{Magic, SupportedVersion, static_cast<std::uint16_t>(type), static_cast<std::uint32_t>(PayloadSize(type)), flags, sequence, frameId};
    std::vector<std::uint8_t> out(sizeof(Header) + header.payloadBytes);
    std::memcpy(out.data(), &header, sizeof(Header));
    if (header.payloadBytes) std::memcpy(out.data() + sizeof(Header), payload, header.payloadBytes);
    return out;
}

// Structural checks that need no session state. Fields are decoded in host order; the target
// architectures (x86 and x64 Windows) are little-endian like the wire format.
inline Error Parse(const std::uint8_t* data, std::size_t size, Parsed& out) {
    if (size < sizeof(Header)) return Error::ShortHeader;
    if (size > MaxMessageBytes) return Error::Oversized;
    std::memcpy(&out.header, data, sizeof(Header));
    if (out.header.magic != Magic) return Error::BadMagic;
    if (out.header.version != SupportedVersion) return Error::BadVersion;
    if (!KnownType(out.header.type)) return Error::UnknownType;
    out.type = static_cast<Type>(out.header.type); out.direction = DirectionOf(out.type);
    const std::size_t payload = PayloadSize(out.type);
    if (out.header.payloadBytes != payload || size != sizeof(Header) + payload) return Error::PayloadSizeMismatch;
    const std::uint32_t allowed = out.type == Type::FrameSubmit ? FlagSupersedePending : 0u;
    if (out.header.flags & ~allowed) return Error::BadFlags;
    std::memset(&out.body, 0, sizeof(out.body));
    if (payload) std::memcpy(&out.body, data + sizeof(Header), payload);
    return Error::Ok;
}

inline std::uint32_t Negotiate(std::uint32_t minVersion, std::uint32_t maxVersion) {
    return (minVersion <= SupportedVersion && SupportedVersion <= maxVersion) ? SupportedVersion : 0u;
}

// Protocol monitor shared by both endpoints; feed it every message in order. An error leaves the
// state untouched. The check order matches tools/transport_io.py exactly.
class Session {
public:
    Error Feed(Direction direction, const std::uint8_t* data, std::size_t size) {
        Parsed m;
        if (const Error error = Parse(data, size, m); error != Error::Ok) return error;
        if (m.direction != direction) return Error::WrongDirection;
        const std::size_t index = direction == Direction::ProxyToRenderer ? 0 : 1;
        if (m.header.sequence != next_[index]) return Error::OutOfSequence;
        if (closed_) return Error::UnexpectedState;
        if (haveHello_ && selected_ && m.header.version != selected_) return Error::BadVersion;
        Error code = Error::UnexpectedState;
        switch (m.type) {
        case Type::Hello: code = OnHello(m); break;
        case Type::HelloAck: code = OnHelloAck(m); break;
        case Type::FrameSubmit: code = OnSubmit(m); break;
        case Type::FrameComplete: code = OnComplete(m); break;
        case Type::Stop: code = OnStop(m); break;
        case Type::StopAck: code = OnStopAck(m); break;
        case Type::SceneAttach: code = OnSceneAttach(m); break;
        case Type::SceneAttachAck: code = OnSceneAttachAck(m); break;
        }
        if (code == Error::Ok) ++next_[index];
        return code;
    }
    bool Ready() const { return haveAck_ && ackStatus_ == AckOk && !closed_; }
    bool Closed() const { return closed_; }
    std::uint32_t Outstanding() const { return count_; }
    std::uint32_t Completed() const { return completed_; }
    std::uint32_t Discarded() const { return discarded_; }

private:
    struct Entry { std::uint64_t frameId, fenceValue; std::uint32_t slot; Generations generations; };
    static bool Same(const Generations& a, const Generations& b) {
        return a.scene == b.scene && a.camera == b.camera && a.lighting == b.lighting && a.material == b.material && a.settings == b.settings;
    }
    Error OnHello(const Parsed& m) {
        if (haveHello_) return Error::UnexpectedState;
        if (m.header.frameId != 0) return Error::BadFrameId;
        if (m.body.hello.reserved != 0) return Error::ReservedNonzero;
        if (!(m.body.hello.minVersion >= 1 && m.body.hello.minVersion <= m.body.hello.maxVersion)) return Error::BadField;
        hello_ = m.body.hello; haveHello_ = true; return Error::Ok;
    }
    Error OnHelloAck(const Parsed& m) {
        if (!haveHello_ || haveAck_) return Error::UnexpectedState;
        if (m.header.frameId != 0) return Error::BadFrameId;
        const HelloAck& a = m.body.ack;
        if (a.reserved != 0) return Error::ReservedNonzero;
        if (a.status > AckBusy) return Error::BadField;
        const std::uint32_t selected = Negotiate(hello_.minVersion, hello_.maxVersion);
        bool closes = false;
        if (a.status == AckOk) {
            if (a.selectedVersion != selected || !selected || m.header.version != selected) return Error::BadField;
            if (a.adapterLuid != hello_.adapterLuid || a.maxInFlight != MaxInFlight) return Error::BadField;
            selected_ = selected;
        } else {
            if (a.selectedVersion != 0 || a.maxInFlight != 0) return Error::BadField;
            if (a.status == AckVersionMismatch && selected) return Error::BadField;
            if (a.status == AckAdapterMismatch && (!selected || a.adapterLuid == hello_.adapterLuid)) return Error::BadField;
            closes = true;
        }
        if (closes) closed_ = true;
        haveAck_ = true; ackStatus_ = a.status; return Error::Ok;
    }
    Error OnSceneAttach(const Parsed& m) {
        if (!Ready() || stopping_ || count_ || pendingAttach_) return Error::UnexpectedState;
        if (m.header.frameId != 0) return Error::BadFrameId;
        const SceneAttach& a = m.body.attach;
        if (a.sectionHandle == 0 || a.sectionBytes < 1 || a.sectionBytes > MaxSceneBytes) return Error::BadField;
        if (a.reserved != 0) return Error::ReservedNonzero;
        pendingAttach_ = true; pendingGeneration_ = a.sceneGeneration; return Error::Ok;
    }
    Error OnSceneAttachAck(const Parsed& m) {
        if (!Ready() || !pendingAttach_) return Error::UnexpectedState;
        if (m.header.frameId != 0) return Error::BadFrameId;
        const SceneAttachAck& a = m.body.attachAck;
        if (a.sceneGeneration != pendingGeneration_) return Error::GenerationMismatch;
        if (a.status > SceneDecodeFailed) return Error::BadField;
        if (a.status == SceneOk) {
            if (!(a.width >= 1 && a.width <= MaxDimension && a.height >= 1 && a.height <= MaxDimension)) return Error::BadField;
            attached_ = true; attachedGeneration_ = a.sceneGeneration;
        } else if (a.width != 0 || a.height != 0) return Error::BadField;
        pendingAttach_ = false; return Error::Ok;
    }
    Error OnSubmit(const Parsed& m) {
        if (!Ready() || stopping_ || !attached_ || pendingAttach_) return Error::UnexpectedState;
        if (m.header.frameId == 0 || m.header.frameId <= lastFrame_) return Error::BadFrameId;
        const FrameSubmit& f = m.body.submit;
        if (!(f.width >= 1 && f.width <= MaxDimension && f.height >= 1 && f.height <= MaxDimension && f.resourceSlot < MaxSlots)) return Error::BadField;
        if (f.reserved != 0) return Error::ReservedNonzero;
        if (f.generations.scene != attachedGeneration_) return Error::GenerationMismatch;
        const bool supersede = (m.header.flags & FlagSupersedePending) != 0;
        if (count_ >= MaxInFlight && !supersede) return Error::TooManyInFlight;
        if (count_ >= MaxInFlight) { --count_; ++discarded_; }
        lastFrame_ = m.header.frameId;
        entries_[count_++] = Entry{m.header.frameId, f.fenceValue, f.resourceSlot, f.generations};
        return Error::Ok;
    }
    Error OnComplete(const Parsed& m) {
        if (!Ready()) return Error::UnexpectedState;
        std::uint32_t at = count_;
        for (std::uint32_t i = 0; i < count_; ++i) if (entries_[i].frameId == m.header.frameId) { at = i; break; }
        if (at == count_) return Error::UnknownFrame;
        const FrameComplete& f = m.body.complete;
        if (f.reserved32 != 0) return Error::ReservedNonzero;
        if (f.status > FrameDeviceRemoved) return Error::BadField;
        if (f.resourceSlot != entries_[at].slot || !Same(f.generations, entries_[at].generations)) return Error::GenerationMismatch;
        if (f.fenceValue < entries_[at].fenceValue) return Error::BadField;
        if (f.status != FrameReady && (f.outputSha256[0] | f.outputSha256[1] | f.outputSha256[2] | f.outputSha256[3])) return Error::BadField;
        for (std::uint32_t i = at; i + 1 < count_; ++i) entries_[i] = entries_[i + 1];
        --count_;
        if (f.status == FrameDiscarded) ++discarded_; else ++completed_;
        return Error::Ok;
    }
    Error OnStop(const Parsed& m) {
        if (!Ready() || stopping_) return Error::UnexpectedState;
        if (m.header.frameId != 0) return Error::BadFrameId;
        stopping_ = true; return Error::Ok;
    }
    Error OnStopAck(const Parsed& m) {
        if (!stopping_ || count_ || pendingAttach_) return Error::UnexpectedState;
        if (m.header.frameId != 0) return Error::BadFrameId;
        if (m.body.stopAck.reserved != 0) return Error::ReservedNonzero;
        if (m.body.stopAck.completedFrames != completed_ || m.body.stopAck.discardedFrames != discarded_) return Error::BadField;
        closed_ = true; return Error::Ok;
    }

    std::uint64_t next_[2]{1, 1}; Hello hello_{}; bool haveHello_{}, haveAck_{}, closed_{}, stopping_{};
    std::uint32_t ackStatus_{}, selected_{}, count_{}, completed_{}, discarded_{}, pendingGeneration_{}, attachedGeneration_{}; std::uint64_t lastFrame_{};
    bool pendingAttach_{}, attached_{};
    Entry entries_[MaxInFlight]{};
};

}  // namespace rrt::transport
