#pragma once

// One parent command per acknowledged epoch on the existing shared fence.
// Four values per ticket: reset, continue, stop, acknowledgement. No payload
// or additional inherited handle is required; the parent owns inputs until
// signalling a command, and regains ownership only after acknowledgement.
struct RcEpochProtocol {
    enum Command : uint64_t { Reset=0, Continue=1, Stop=2 };
    static constexpr UINT MaxEpochs=64;
    static uint64_t Base(UINT epoch) { Require(epoch<=MaxEpochs,"RC session epoch limit"); return 40+uint64_t(epoch)*4; }
    static uint64_t Signal(UINT epoch,Command command) { return Base(epoch)+command; }
    static uint64_t Ack(UINT epoch) { return Base(epoch)+3; }
    static Command Decode(UINT epoch,uint64_t value) {
        const auto base=Base(epoch);
        Require(value>=base&&value<=base+2,"RC session command out of sequence");
        return static_cast<Command>(value-base);
    }
};
