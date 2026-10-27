// Test host for the transport protocol: prints the compiled layout and runs hex-encoded messages
// through the C++ session monitor so tests/verify_transport_layout.py can compare it, message by
// message, with tools/transport_io.py. Built for both x86 and x64.
#include "transport.h"

#include <cstdio>
#include <iostream>
#include <string>
#include <vector>

using namespace rrt::transport;

static bool Hex(const std::string& text, std::vector<std::uint8_t>& out) {
    if (text.size() % 2) return false;
    auto nibble = [](char c) -> int { return c >= '0' && c <= '9' ? c - '0' : c >= 'a' && c <= 'f' ? c - 'a' + 10 : c >= 'A' && c <= 'F' ? c - 'A' + 10 : -1; };
    for (std::size_t i = 0; i < text.size(); i += 2) {
        const int high = nibble(text[i]), low = nibble(text[i + 1]);
        if (high < 0 || low < 0) return false;
        out.push_back(static_cast<std::uint8_t>(high * 16 + low));
    }
    return true;
}

static void Layout() {
    const std::uint16_t probe = 1; const bool little = *reinterpret_cast<const std::uint8_t*>(&probe) == 1;
    std::printf("{\"pointer_bytes\":%zu,\"little_endian\":%s,\"max_message_bytes\":%zu,\"magic\":%u,\"max_in_flight\":%u,\"sizes\":{"
        "\"Header\":%zu,\"Hello\":%zu,\"HelloAck\":%zu,\"FrameSubmit\":%zu,\"FrameComplete\":%zu,\"StopAck\":%zu},\"offsets\":{"
        "\"Header\":{\"magic\":%zu,\"version\":%zu,\"type\":%zu,\"payload_bytes\":%zu,\"flags\":%zu,\"sequence\":%zu,\"frame_id\":%zu},"
        "\"Hello\":{\"min_version\":%zu,\"max_version\":%zu,\"adapter_luid\":%zu,\"process_id\":%zu,\"capabilities\":%zu,\"capture_level\":%zu,\"reserved\":%zu},"
        "\"HelloAck\":{\"selected_version\":%zu,\"status\":%zu,\"adapter_luid\":%zu,\"max_in_flight\":%zu,\"capabilities\":%zu,\"reserved\":%zu},"
        "\"FrameSubmit\":{\"fence_value\":%zu,\"resource_slot\":%zu,\"width\":%zu,\"height\":%zu,\"scene_generation\":%zu,\"camera_generation\":%zu,"
        "\"lighting_generation\":%zu,\"material_generation\":%zu,\"settings_generation\":%zu,\"reserved\":%zu},"
        "\"FrameComplete\":{\"fence_value\":%zu,\"status\":%zu,\"resource_slot\":%zu,\"scene_generation\":%zu,\"camera_generation\":%zu,"
        "\"lighting_generation\":%zu,\"material_generation\":%zu,\"settings_generation\":%zu,\"reserved32\":%zu,\"reserved\":%zu},"
        "\"StopAck\":{\"completed_frames\":%zu,\"discarded_frames\":%zu,\"reserved\":%zu}}}\n",
        sizeof(void*), little ? "true" : "false", MaxMessageBytes, Magic, MaxInFlight,
        sizeof(Header), sizeof(Hello), sizeof(HelloAck), sizeof(FrameSubmit), sizeof(FrameComplete), sizeof(StopAck),
        offsetof(Header, magic), offsetof(Header, version), offsetof(Header, type), offsetof(Header, payloadBytes), offsetof(Header, flags), offsetof(Header, sequence), offsetof(Header, frameId),
        offsetof(Hello, minVersion), offsetof(Hello, maxVersion), offsetof(Hello, adapterLuid), offsetof(Hello, processId), offsetof(Hello, capabilities), offsetof(Hello, captureLevel), offsetof(Hello, reserved),
        offsetof(HelloAck, selectedVersion), offsetof(HelloAck, status), offsetof(HelloAck, adapterLuid), offsetof(HelloAck, maxInFlight), offsetof(HelloAck, capabilities), offsetof(HelloAck, reserved),
        offsetof(FrameSubmit, fenceValue), offsetof(FrameSubmit, resourceSlot), offsetof(FrameSubmit, width), offsetof(FrameSubmit, height),
        offsetof(FrameSubmit, generations) + offsetof(Generations, scene), offsetof(FrameSubmit, generations) + offsetof(Generations, camera), offsetof(FrameSubmit, generations) + offsetof(Generations, lighting),
        offsetof(FrameSubmit, generations) + offsetof(Generations, material), offsetof(FrameSubmit, generations) + offsetof(Generations, settings), offsetof(FrameSubmit, reserved),
        offsetof(FrameComplete, fenceValue), offsetof(FrameComplete, status), offsetof(FrameComplete, resourceSlot),
        offsetof(FrameComplete, generations) + offsetof(Generations, scene), offsetof(FrameComplete, generations) + offsetof(Generations, camera), offsetof(FrameComplete, generations) + offsetof(Generations, lighting),
        offsetof(FrameComplete, generations) + offsetof(Generations, material), offsetof(FrameComplete, generations) + offsetof(Generations, settings), offsetof(FrameComplete, reserved32), offsetof(FrameComplete, reserved),
        offsetof(StopAck, completedFrames), offsetof(StopAck, discardedFrames), offsetof(StopAck, reserved));
}

// stdin: "reset" starts a fresh session; "p2r HEX" / "r2p HEX" feeds one message. Prints one error
// number per message, in the order of rrt::transport::Error and "errors" in the schema.
int main(int argc, char** argv) {
    if (argc > 1 && std::string(argv[1]) == "--layout") { Layout(); return 0; }
    Session session; std::string line;
    while (std::getline(std::cin, line)) {
        while (!line.empty() && line.back() == '\r') line.pop_back();
        if (line.empty()) continue;
        if (line == "reset") { session = Session(); continue; }
        const std::size_t space = line.find(' ');
        const std::string direction = line.substr(0, space);  // the hex part is empty for a zero-length message
        std::vector<std::uint8_t> bytes;
        if ((direction != "p2r" && direction != "r2p") || (space != std::string::npos && !Hex(line.substr(space + 1), bytes))) { std::fprintf(stderr, "bad line\n"); return 2; }
        std::printf("%u\n", static_cast<unsigned>(session.Feed(direction == "p2r" ? Direction::ProxyToRenderer : Direction::RendererToProxy, bytes.data(), bytes.size())));
    }
    return 0;
}
