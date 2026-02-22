#include "server.hpp"
#include "embedder.hpp"

#include <arpa/inet.h>
#include <csignal>
#include <cstring>
#include <iostream>
#include <netdb.h>
#include <sys/socket.h>
#include <unistd.h>

std::atomic<bool> Server::shutdown_requested{false};

static void signal_handler(int) {
    Server::shutdown_requested.store(true);
}

Server::Server(const std::string& host, int port)
    : host_(host), port_(port) {}

Server::~Server() {
    if (listen_fd_ >= 0) {
        close(listen_fd_);
    }
}

void Server::setup_socket() {
    listen_fd_ = socket(AF_INET, SOCK_STREAM, 0);
    if (listen_fd_ < 0) {
        throw std::runtime_error("Failed to create socket: " + std::string(strerror(errno)));
    }

    int opt = 1;
    setsockopt(listen_fd_, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    struct addrinfo hints{}, *res;
    hints.ai_family = AF_INET;
    hints.ai_socktype = SOCK_STREAM;

    int rc = getaddrinfo(host_.c_str(), std::to_string(port_).c_str(), &hints, &res);
    if (rc != 0) {
        close(listen_fd_);
        listen_fd_ = -1;
        throw std::runtime_error("getaddrinfo failed: " + std::string(gai_strerror(rc)));
    }

    if (bind(listen_fd_, res->ai_addr, res->ai_addrlen) < 0) {
        freeaddrinfo(res);
        close(listen_fd_);
        listen_fd_ = -1;
        throw std::runtime_error("Failed to bind: " + std::string(strerror(errno)));
    }
    freeaddrinfo(res);

    if (listen(listen_fd_, 8) < 0) {
        close(listen_fd_);
        listen_fd_ = -1;
        throw std::runtime_error("Failed to listen: " + std::string(strerror(errno)));
    }
}

void Server::run() {
    // Install signal handler
    struct sigaction sa{};
    sa.sa_handler = signal_handler;
    sigemptyset(&sa.sa_mask);
    sa.sa_flags = 0;
    sigaction(SIGINT, &sa, nullptr);
    sigaction(SIGTERM, &sa, nullptr);

    setup_socket();
    std::cout << "[vectordb] Listening on " << host_ << ":" << port_ << std::endl;

    while (!shutdown_requested.load()) {
        // Use select with timeout so we can check shutdown flag
        fd_set fds;
        FD_ZERO(&fds);
        FD_SET(listen_fd_, &fds);

        struct timeval tv;
        tv.tv_sec = 1;
        tv.tv_usec = 0;

        int ready = select(listen_fd_ + 1, &fds, nullptr, nullptr, &tv);
        if (ready < 0) {
            if (errno == EINTR) continue;
            break;
        }
        if (ready == 0) continue; // timeout, check shutdown flag

        int client_fd = accept(listen_fd_, nullptr, nullptr);
        if (client_fd < 0) {
            if (errno == EINTR) continue;
            std::cerr << "[vectordb] Accept error: " << strerror(errno) << std::endl;
            continue;
        }

        handle_connection(client_fd);
        close(client_fd);
    }

    std::cout << "\n[vectordb] Shutting down." << std::endl;
}

void Server::handle_connection(int client_fd) {
    try {
        std::string msg = read_message(client_fd);
        nlohmann::json request = nlohmann::json::parse(msg);
        nlohmann::json response = dispatch(request);
        write_message(client_fd, response.dump());
    } catch (const nlohmann::json::parse_error& e) {
        nlohmann::json err = {{"status", "error"}, {"message", std::string("JSON parse error: ") + e.what()}};
        write_message(client_fd, err.dump());
    } catch (const std::exception& e) {
        nlohmann::json err = {{"status", "error"}, {"message", e.what()}};
        try {
            write_message(client_fd, err.dump());
        } catch (...) {
            // Client may have disconnected; ignore write failure
        }
    }
}

std::string Server::read_message(int fd) {
    // Read 4-byte length header (big-endian)
    uint8_t len_buf[4];
    size_t total = 0;
    while (total < 4) {
        ssize_t n = read(fd, len_buf + total, 4 - total);
        if (n <= 0) {
            throw std::runtime_error("Failed to read message length");
        }
        total += static_cast<size_t>(n);
    }

    uint32_t length = (static_cast<uint32_t>(len_buf[0]) << 24) |
                      (static_cast<uint32_t>(len_buf[1]) << 16) |
                      (static_cast<uint32_t>(len_buf[2]) << 8)  |
                      (static_cast<uint32_t>(len_buf[3]));

    if (length == 0 || length > 10 * 1024 * 1024) {
        throw std::runtime_error("Invalid message length: " + std::to_string(length));
    }

    // Read payload
    std::string payload(length, '\0');
    total = 0;
    while (total < length) {
        ssize_t n = read(fd, &payload[total], length - total);
        if (n <= 0) {
            throw std::runtime_error("Failed to read message payload");
        }
        total += static_cast<size_t>(n);
    }

    return payload;
}

void Server::write_message(int fd, const std::string& msg) {
    uint32_t length = static_cast<uint32_t>(msg.size());
    uint8_t len_buf[4] = {
        static_cast<uint8_t>((length >> 24) & 0xFF),
        static_cast<uint8_t>((length >> 16) & 0xFF),
        static_cast<uint8_t>((length >> 8) & 0xFF),
        static_cast<uint8_t>(length & 0xFF)
    };

    size_t total = 0;
    while (total < 4) {
        ssize_t n = write(fd, len_buf + total, 4 - total);
        if (n <= 0) {
            throw std::runtime_error("Failed to write message length");
        }
        total += static_cast<size_t>(n);
    }

    total = 0;
    while (total < msg.size()) {
        ssize_t n = write(fd, msg.data() + total, msg.size() - total);
        if (n <= 0) {
            throw std::runtime_error("Failed to write message payload");
        }
        total += static_cast<size_t>(n);
    }
}

nlohmann::json Server::dispatch(const nlohmann::json& request) {
    if (!request.contains("action") || !request["action"].is_string()) {
        return {{"status", "error"}, {"message", "Missing or invalid 'action' field"}};
    }

    const std::string& action = request["action"].get_ref<const std::string&>();

    if (action == "store") {
        return handle_store(request);
    } else if (action == "search") {
        return handle_search(request);
    } else {
        return {{"status", "error"}, {"message", "Unknown action: " + action}};
    }
}

nlohmann::json Server::handle_store(const nlohmann::json& request) {
    if (!request.contains("chunk_id") || !request.contains("doc_id") || !request.contains("text")) {
        return {{"status", "error"}, {"message", "store requires chunk_id, doc_id, and text"}};
    }

    const std::string& chunk_id = request["chunk_id"].get_ref<const std::string&>();
    const std::string& doc_id = request["doc_id"].get_ref<const std::string&>();
    const std::string& text = request["text"].get_ref<const std::string&>();
    nlohmann::json metadata = request.value("metadata", nlohmann::json::object());

    std::vector<float> embedding = embed(text);
    db_.store(chunk_id, doc_id, text, metadata, embedding);

    return {{"status", "ok"}};
}

nlohmann::json Server::handle_search(const nlohmann::json& request) {
    if (!request.contains("query")) {
        return {{"status", "error"}, {"message", "search requires query"}};
    }

    const std::string& query = request["query"].get_ref<const std::string&>();
    int top_k = request.value("top_k", 5);
    std::string doc_id_filter = request.value("doc_id", std::string(""));

    std::vector<float> query_embedding = embed(query);
    auto results = db_.search(query_embedding, top_k, doc_id_filter);

    nlohmann::json result_array = nlohmann::json::array();
    for (const auto& r : results) {
        result_array.push_back({
            {"chunk_id", r.chunk_id},
            {"score", r.score},
            {"text", r.text}
        });
    }

    return {{"status", "ok"}, {"results", result_array}};
}
