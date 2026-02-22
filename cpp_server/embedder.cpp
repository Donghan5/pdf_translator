#include "embedder.hpp"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <functional>

std::vector<float> embed(const std::string& text) {
    std::vector<float> vec(EMBED_DIM, 0.0f);

    // Tokenize: lowercase, split on non-alphanumeric
    std::string token;
    for (char c : text) {
        if (std::isalnum(static_cast<unsigned char>(c))) {
            token += static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
        } else {
            if (!token.empty()) {
                size_t h = std::hash<std::string>{}(token) % EMBED_DIM;
                vec[h] += 1.0f;
                token.clear();
            }
        }
    }
    if (!token.empty()) {
        size_t h = std::hash<std::string>{}(token) % EMBED_DIM;
        vec[h] += 1.0f;
    }

    // L2-normalize
    float norm = 0.0f;
    for (float v : vec) {
        norm += v * v;
    }
    if (norm > 0.0f) {
        norm = std::sqrt(norm);
        for (float& v : vec) {
            v /= norm;
        }
    }

    return vec;
}
