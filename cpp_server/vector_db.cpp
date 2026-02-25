#include "vector_db.hpp"

#include <algorithm>

void VectorDB::store(const std::string& chunk_id,
                     const std::string& doc_id,
                     const std::string& text,
                     const nlohmann::json& metadata,
                     const std::vector<float>& embedding) {
    // If overwriting, remove old doc_index entry
    auto it = entries_.find(chunk_id);
    if (it != entries_.end()) {
        const std::string& old_doc_id = it->second.doc_id;
        auto& ids = doc_index_[old_doc_id];
        ids.erase(std::remove(ids.begin(), ids.end(), chunk_id), ids.end());
        if (ids.empty()) {
            doc_index_.erase(old_doc_id);
        }
    }

    entries_[chunk_id] = VectorEntry{chunk_id, doc_id, text, metadata, embedding};
    doc_index_[doc_id].push_back(chunk_id);
}

std::vector<SearchResult> VectorDB::search(const std::vector<float>& query_embedding,
                                            int top_k,
                                            const std::string& doc_id_filter) const {
    std::vector<std::pair<float, const VectorEntry*>> scored;

    if (!doc_id_filter.empty()) {
        // Filtered search: only entries matching doc_id
        auto it = doc_index_.find(doc_id_filter);
        if (it != doc_index_.end()) {
            for (const auto& cid : it->second) {
                auto eit = entries_.find(cid);
                if (eit != entries_.end()) {
                    float score = dot_product(query_embedding, eit->second.embedding);
                    scored.emplace_back(score, &eit->second);
                }
            }
        }
    } else {
        // Unfiltered: scan all entries
        for (const auto& [cid, entry] : entries_) {
            float score = dot_product(query_embedding, entry.embedding);
            scored.emplace_back(score, &entry);
        }
    }

    // Sort descending by score
    std::sort(scored.begin(), scored.end(),
              [](const auto& a, const auto& b) { return a.first > b.first; });

    // Take top_k
    std::vector<SearchResult> results;
    int count = std::min(top_k, static_cast<int>(scored.size()));
    for (int i = 0; i < count; ++i) {
        results.push_back({
            scored[i].second->chunk_id,
            scored[i].first,
            scored[i].second->text,
            scored[i].second->metadata
        });
    }

    return results;
}

float VectorDB::dot_product(const std::vector<float>& a, const std::vector<float>& b) {
    float sum = 0.0f;
    size_t n = std::min(a.size(), b.size());
    for (size_t i = 0; i < n; ++i) {
        sum += a[i] * b[i];
    }
    return sum;
}
