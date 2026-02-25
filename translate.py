"""
Translation module — Groq API
Milestone 2: Full Groq API integration with rate limiting and error handling.
"""

import time
import logging

from groq import Groq, RateLimitError, APIError

import config

logger = logging.getLogger(__name__)


# =============================================================================
# Usage Tracking
# =============================================================================
class UsageTracker:
    def __init__(self):
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.translations = 0
        self.skipped = 0

    def add(self, input_tokens: int, output_tokens: int):
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.translations += 1

    def add_skip(self):
        self.skipped += 1

    def print_summary(self):
        total = self.total_input_tokens + self.total_output_tokens
        print(f"\n   Usage Summary:")
        print(f"      Input tokens:  {self.total_input_tokens:,}")
        print(f"      Output tokens: {self.total_output_tokens:,}")
        print(f"      Total tokens:  {total:,}")
        print(f"      Translations:  {self.translations}")
        if self.skipped:
            print(f"      Skipped:       {self.skipped}")


usage_tracker = UsageTracker()

# Groq client (initialized lazily)
_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        if not config.GROQ_API_KEY:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Add it to your .env file or environment."
            )
        _client = Groq(api_key=config.GROQ_API_KEY)
    return _client


# =============================================================================
# Translation
# =============================================================================
REQUEST_DELAY = 0.5        # seconds between API calls
MAX_RETRIES = 3
BACKOFF_BASE = 1           # exponential backoff: 1s -> 2s -> 4s


def translate_chunk(
    chunk_text: str,
    chunk_num: int,
    total_chunks: int,
    source_lang: str | None = None,
    target_lang: str | None = None,
) -> tuple[str | None, int, int]:
    """
    Translate a single chunk via Groq API.

    Returns:
        (translated_text, input_tokens, output_tokens)
        translated_text is None if all retries failed.
    """
    source = config.get_language_name(source_lang or config.SOURCE_LANG)
    target = config.get_language_name(target_lang or config.TARGET_LANG)

    prompt = (
        f"Translate the following text from {source} to {target}.\n"
        f"Output only the translated text, no explanations.\n\n"
        f"Text:\n{chunk_text}"
    )

    # Dynamic max_tokens: input word count as rough token proxy * 1.5
    estimated_input_tokens = int(len(chunk_text.split()) / 0.75)
    max_tokens = int(estimated_input_tokens * 1.5)
    max_tokens = max(max_tokens, 256)  # floor to avoid tiny limits

    client = _get_client()

    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=config.GROQ_MODEL_TRANSLATE,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=max_tokens,
            )

            translated = response.choices[0].message.content.strip()
            input_tok = response.usage.prompt_tokens
            output_tok = response.usage.completion_tokens

            print(f"   Chunk {chunk_num}/{total_chunks} translated "
                  f"({input_tok}+{output_tok} tokens)")
            return translated, input_tok, output_tok

        except RateLimitError:
            wait = BACKOFF_BASE * (2 ** attempt)
            print(f"   Chunk {chunk_num}/{total_chunks} rate-limited, "
                  f"retrying in {wait}s... (attempt {attempt + 1}/{MAX_RETRIES})")
            time.sleep(wait)

        except APIError as e:
            wait = BACKOFF_BASE * (2 ** attempt)
            logger.warning("Groq API error on chunk %d: %s", chunk_num, e)
            print(f"   Chunk {chunk_num}/{total_chunks} API error, "
                  f"retrying in {wait}s... (attempt {attempt + 1}/{MAX_RETRIES})")
            time.sleep(wait)

    # All retries exhausted
    print(f"   [SKIP] Chunk {chunk_num}/{total_chunks} failed after {MAX_RETRIES} retries")
    return None, 0, 0


def translate_text(
    chunks: list[dict],
    source_lang: str | None = None,
    target_lang: str | None = None,
    on_progress=None,
) -> list[tuple[dict, str]]:
    """
    Translate metadata-enriched chunks via Groq API.

    Args:
        chunks: List of chunk metadata dicts from parse.split_into_chunks().
        source_lang: Override source language code.
        target_lang: Override target language code.
        on_progress: Optional callback(current, total, skipped) called after each chunk.

    Returns:
        List of (chunk_metadata, translated_text) pairs.
        Failed chunks are skipped (not included in output).
    """
    if not chunks:
        return []

    results: list[tuple[dict, str]] = []
    skipped = 0

    for i, chunk in enumerate(chunks, 1):
        # Rate-limit delay (skip before first request)
        if i > 1:
            time.sleep(REQUEST_DELAY)

        translated, in_tok, out_tok = translate_chunk(
            chunk["original_text"], i, len(chunks),
            source_lang=source_lang, target_lang=target_lang,
        )

        if translated is not None:
            usage_tracker.add(in_tok, out_tok)
            chunk["translated_text"] = translated
            results.append((chunk, translated))
        else:
            usage_tracker.add_skip()
            skipped += 1

        if on_progress:
            on_progress(i, len(chunks), skipped)

    return results
