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

static std::string Field(const char* name, std::size_t offset, bool first = false) {
    return std::string(first ? "" : ",") + "\"" + name + "\":" + std::to_string(offset);
}
static std::string Words(const char* base, std::size_t offset) {
    std::string out;
    for (int i = 0; i < 4; ++i) out += Field((std::string(base) + "_" + std::to_string(i)).c_str(), offset + 8 * i);
    return out;
}
static std::string Generation(std::size_t base) {
    return Field("scene_generation", base + offsetof(Generations, scene)) + Field("camera_generation", base + offsetof(Generations, camera)) +
        Field("lighting_generation", base + offsetof(Generations, lighting)) + Field("material_generation", base + offsetof(Generations, material)) +
        Field("settings_generation", base + offsetof(Generations, settings));
}

static void Layout() {
    const std::uint16_t probe = 1; const bool little = *reinterpret_cast<const std::uint8_t*>(&probe) == 1;
    std::string out = "{\"pointer_bytes\":" + std::to_string(sizeof(void*)) + ",\"little_endian\":" + (little ? "true" : "false") +
        ",\"max_message_bytes\":" + std::to_string(MaxMessageBytes) + ",\"magic\":" + std::to_string(Magic) + ",\"max_in_flight\":" + std::to_string(MaxInFlight) +
        ",\"max_scene_bytes\":" + std::to_string(MaxSceneBytes);
    out += ",\"sizes\":{" + std::string("\"Header\":") + std::to_string(sizeof(Header)) + ",\"Hello\":" + std::to_string(sizeof(Hello)) + ",\"HelloAck\":" + std::to_string(sizeof(HelloAck)) +
        ",\"FrameSubmit\":" + std::to_string(sizeof(FrameSubmit)) + ",\"FrameComplete\":" + std::to_string(sizeof(FrameComplete)) + ",\"StopAck\":" + std::to_string(sizeof(StopAck)) +
        ",\"SceneAttach\":" + std::to_string(sizeof(SceneAttach)) + ",\"SceneAttachAck\":" + std::to_string(sizeof(SceneAttachAck)) + "}";
    out += ",\"offsets\":{";
    out += "\"Header\":{" + Field("magic", offsetof(Header, magic), true) + Field("version", offsetof(Header, version)) + Field("type", offsetof(Header, type)) +
        Field("payload_bytes", offsetof(Header, payloadBytes)) + Field("flags", offsetof(Header, flags)) + Field("sequence", offsetof(Header, sequence)) + Field("frame_id", offsetof(Header, frameId)) + "}";
    out += ",\"Hello\":{" + Field("min_version", offsetof(Hello, minVersion), true) + Field("max_version", offsetof(Hello, maxVersion)) + Field("adapter_luid", offsetof(Hello, adapterLuid)) +
        Field("process_id", offsetof(Hello, processId)) + Field("capabilities", offsetof(Hello, capabilities)) + Field("capture_level", offsetof(Hello, captureLevel)) + Field("reserved", offsetof(Hello, reserved)) + "}";
    out += ",\"HelloAck\":{" + Field("selected_version", offsetof(HelloAck, selectedVersion), true) + Field("status", offsetof(HelloAck, status)) + Field("adapter_luid", offsetof(HelloAck, adapterLuid)) +
        Field("max_in_flight", offsetof(HelloAck, maxInFlight)) + Field("capabilities", offsetof(HelloAck, capabilities)) + Field("reserved", offsetof(HelloAck, reserved)) + "}";
    out += ",\"FrameSubmit\":{" + Field("fence_value", offsetof(FrameSubmit, fenceValue), true) + Field("resource_slot", offsetof(FrameSubmit, resourceSlot)) + Field("width", offsetof(FrameSubmit, width)) +
        Field("height", offsetof(FrameSubmit, height)) + Generation(offsetof(FrameSubmit, generations)) + Field("reserved", offsetof(FrameSubmit, reserved)) + "}";
    out += ",\"FrameComplete\":{" + Field("fence_value", offsetof(FrameComplete, fenceValue), true) + Field("status", offsetof(FrameComplete, status)) + Field("resource_slot", offsetof(FrameComplete, resourceSlot)) +
        Generation(offsetof(FrameComplete, generations)) + Field("reserved32", offsetof(FrameComplete, reserved32)) + Words("output_sha256", offsetof(FrameComplete, outputSha256)) + "}";
    out += ",\"StopAck\":{" + Field("completed_frames", offsetof(StopAck, completedFrames), true) + Field("discarded_frames", offsetof(StopAck, discardedFrames)) + Field("reserved", offsetof(StopAck, reserved)) + "}";
    out += ",\"SceneAttach\":{" + Field("section_handle", offsetof(SceneAttach, sectionHandle), true) + Field("section_bytes", offsetof(SceneAttach, sectionBytes)) + Words("sha256", offsetof(SceneAttach, sha256)) +
        Field("scene_generation", offsetof(SceneAttach, sceneGeneration)) + Field("reserved", offsetof(SceneAttach, reserved)) + "}";
    out += ",\"SceneAttachAck\":{" + Field("status", offsetof(SceneAttachAck, status), true) + Field("scene_generation", offsetof(SceneAttachAck, sceneGeneration)) +
        Field("width", offsetof(SceneAttachAck, width)) + Field("height", offsetof(SceneAttachAck, height)) + "}";
    out += "}}\n";
    std::fputs(out.c_str(), stdout);
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
