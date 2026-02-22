cmake_minimum_required(VERSION 3.14)
project(vectordb_server LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Fetch nlohmann/json
include(FetchContent)
FetchContent_Declare(
    json
    GIT_REPOSITORY https://github.com/nlohmann/json.git
    GIT_TAG        v3.11.3
)
FetchContent_MakeAvailable(json)

add_executable(vectordb_server
    main.cpp
    embedder.cpp
    vector_db.cpp
    server.cpp
)

target_link_libraries(vectordb_server PRIVATE nlohmann_json::nlohmann_json)
