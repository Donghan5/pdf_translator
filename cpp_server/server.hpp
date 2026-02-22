#pragma once

#include <atomic>
#include <string>

#include <nlohmann/json.hpp>

#include "vector_db.hpp"

class Server {
public:
    Server(const std::string& host, int port);
    ~Server();

    // Main accept loop. Blocks until shutdown.
    void run();

    // Signal handler sets this to trigger clean shutdown.
    static std::atomic<bool> shutdown_requested;

private:
    std::string host_;
    int port_;
    int listen_fd_ = -1;
    VectorDB db_;

    void setup_socket();
    void handle_connection(int client_fd);

    // Length-prefixed framing: 4-byte uint32 big-endian + JSON payload
    std::string read_message(int fd);
    void write_message(int fd, const std::string& msg);

    nlohmann::json dispatch(const nlohmann::json& request);
    nlohmann::json handle_store(const nlohmann::json& request);
    nlohmann::json handle_search(const nlohmann::json& request);
};
