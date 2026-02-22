#pragma once

#include <string>
#include <unordered_map>
#include <vector>

#include <nlohmann/json.hpp>

struct VectorEntry {
    std::string chunk_id;
    std::string doc_id;
    std::string text;
    nlohmann::json metadata;
    std::vector<float> embedding;
};

struct SearchResult {
    std::string chunk_id;
    float score;
    std::string text;
};

class VectorDB {
public:
    // Insert or overwrite an entry by chunk_id.
    void store(const std::string& chunk_id,
               const std::string& doc_id,
               const std::string& text,
               const nlohmann::json& metadata,
               const std::vector<float>& embedding);

    // Brute-force cosine similarity search.
    // If doc_id_filter is non-empty, only search within that doc_id.
    std::vector<SearchResult> search(const std::vector<float>& query_embedding,
                                     int top_k,
                                     const std::string& doc_id_filter = "") const;

private:
    // Primary store: chunk_id -> entry
    std::unordered_map<std::string, VectorEntry> entries_;

    // Secondary index: doc_id -> [chunk_ids]
    std::unordered_map<std::string, std::vector<std::string>> doc_index_;

    static float dot_product(const std::vector<float>& a, const std::vector<float>& b);
};
