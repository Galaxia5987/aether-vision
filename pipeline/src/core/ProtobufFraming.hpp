#pragma once

#include <google/protobuf/message.h>
#include <iostream>
#include <vector>
#include <cstdint>
#include <mutex>
#include <arpa/inet.h>

namespace aether::vision {

class ProtobufFraming {
public:
    static constexpr uint32_t MAX_MESSAGE_SIZE = 64 * 1024 * 1024; // 64 MB protection limit

    // Writes a length-prefixed protobuf message to an output stream (e.g. stdout)
    static bool writeDelimited(std::ostream& os, const google::protobuf::Message& msg) {
        size_t byte_size = msg.ByteSizeLong();
        if (byte_size > MAX_MESSAGE_SIZE) {
            return false;
        }

        uint32_t net_len = htonl(static_cast<uint32_t>(byte_size));
        
        // Write 4-byte big endian header
        os.write(reinterpret_cast<const char*>(&net_len), sizeof(net_len));
        if (!os) {
            return false;
        }

        // Write serialized protobuf payload
        if (!msg.SerializeToOstream(&os)) {
            return false;
        }

        os.flush();
        return os.good();
    }

    // Reads a length-prefixed protobuf message from an input stream (e.g. stdin)
    static bool readDelimited(std::istream& is, google::protobuf::Message& msg, std::vector<char>& buffer) {
        uint32_t net_len = 0;
        is.read(reinterpret_cast<char*>(&net_len), sizeof(net_len));
        if (!is || is.gcount() != sizeof(net_len)) {
            return false; // EOF or stream closed
        }

        uint32_t host_len = ntohl(net_len);
        if (host_len > MAX_MESSAGE_SIZE) {
            return false; // Exceeded safety threshold
        }

        if (buffer.size() < host_len) {
            buffer.resize(host_len);
        }

        is.read(buffer.data(), host_len);
        if (!is || static_cast<uint32_t>(is.gcount()) != host_len) {
            return false;
        }

        return msg.ParseFromArray(buffer.data(), static_cast<int>(host_len));
    }
};

} // namespace aether::vision
