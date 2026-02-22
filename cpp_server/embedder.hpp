#pragma once

#include <string>
#include <vector>

constexpr size_t EMBED_DIM = 4096;

// Hash-based bag-of-words embedder (hashing trick).
// Tokenizes text, hashes each token into a fixed-size vector, then L2-normalizes.
std::vector<float> embed(const std::string& text);
