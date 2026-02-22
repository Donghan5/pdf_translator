"""
Translation module — Groq API
Full implementation in Milestone 2.
"""

from parse import split_into_chunks
import config


# =============================================================================
# Usage Tracking
# =============================================================================
class UsageTracker:
    def __init__(self):
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.translations = 0

    def add(self, input_tokens: int, output_tokens: int):
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.translations += 1

    def print_summary(self):
        total = self.total_input_tokens + self.total_output_tokens
        print(f"\n   Usage Summary:")
        print(f"      Input tokens:  {self.total_input_tokens:,}")
        print(f"      Output tokens: {self.total_output_tokens:,}")
        print(f"      Total tokens:  {total:,}")
        print(f"      Translations:  {self.translations}")


usage_tracker = UsageTracker()


# =============================================================================
# Translation (stub — will use Groq API in M2)
# =============================================================================
def translate_chunk(chunk: str, chunk_num: int, total_chunks: int) -> str:
    """Translate a single chunk. Placeholder until Groq API integration."""
    print(f"   [STUB] Translating chunk {chunk_num}/{total_chunks}... skipped (Groq not yet wired)")
    return chunk


def translate_text(text: str) -> str:
    """Translate full text by processing in chunks."""
    chunks = split_into_chunks(text)
    if not chunks:
        return ""

    translated_chunks = []
    for i, chunk in enumerate(chunks, 1):
        translated = translate_chunk(chunk, i, len(chunks))
        translated_chunks.append(translated)

    usage_tracker.print_summary()
    return "\n\n".join(translated_chunks)
