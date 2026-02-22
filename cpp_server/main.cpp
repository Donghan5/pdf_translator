#include "server.hpp"

#include <iostream>
#include <string>

int main(int argc, char* argv[]) {
    std::string host = "localhost";
    int port = 50051;

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--host" && i + 1 < argc) {
            host = argv[++i];
        } else if (arg == "--port" && i + 1 < argc) {
            port = std::stoi(argv[++i]);
        } else {
            std::cerr << "Usage: vectordb_server [--host HOST] [--port PORT]" << std::endl;
            return 1;
        }
    }

    try {
        Server server(host, port);
        server.run();
    } catch (const std::exception& e) {
        std::cerr << "[vectordb] Fatal: " << e.what() << std::endl;
        return 1;
    }

    return 0;
}
