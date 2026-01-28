import time
import google.generativeai as genai
from parse import split_into_chunks
from config import MODEL_NAME, MAX_RETRIES, INITIAL_BACKOFF

# =============================================================================
# Usage Tracking
# =============================================================================
class UsageTracker:
    """Track API token usage across translations."""
    def __init__(self):
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.api_calls = 0
    
    def add(self, response):
        """Add usage from API response."""
        if hasattr(response, 'usage_metadata'):
            self.total_input_tokens += response.usage_metadata.prompt_token_count
            self.total_output_tokens += response.usage_metadata.candidates_token_count
        self.api_calls += 1
    
    def print_summary(self):
        """Print usage summary."""
        total = self.total_input_tokens + self.total_output_tokens
        print(f"\n 📊 API Usage Summary:")
        print(f"      Input tokens:  {self.total_input_tokens:,}")
        print(f"      Output tokens: {self.total_output_tokens:,}")
        print(f"      Total tokens:  {total:,}")
        print(f"      API calls:     {self.api_calls}")
        # Free tier info (as of 2024)
        print(f"      💡 Free tier: 1M tokens/min, 1500 requests/day")


# Global tracker
usage_tracker = UsageTracker()


# =============================================================================
# AI Translation with Rate Limiting
# =============================================================================
def translate_chunk(model, chunk: str, chunk_num: int, total_chunks: int) -> str:
    """
    Translate a single chunk using Gemini API.
    Implements exponential backoff for rate limiting.
    """
    prompt = f"""Translate the following text to Korean. 
            Preserve any formatting, headers, or structure where possible.
            Output only the translated text, no explanations.

            Text to translate:
            {chunk}"""

    retries = 0
    backoff = INITIAL_BACKOFF

    while retries < MAX_RETRIES:
        try:
            print(f"   🔄 Translating chunk {chunk_num}/{total_chunks}...", end=" ")
            response = model.generate_content(prompt)
            usage_tracker.add(response)  # Track usage
            print("✓ Done")
            return response.text

        except Exception as e:
            error_msg = str(e)

            # Check for rate limiting (429 error)
            if "429" in error_msg or "quota" in error_msg.lower() or "rate" in error_msg.lower():
                retries += 1
                print(f"\n   ⚠ Rate limit hit. Waiting {backoff} seconds... (Retry {retries}/{MAX_RETRIES})")
                time.sleep(backoff)
                backoff = min(backoff * 2, 120)
            else:
                print(f"\n   ❌ Error: {error_msg}")
                raise

    raise Exception(f"Failed after {MAX_RETRIES} retries due to rate limiting")


def translate_text(api_key: str, text: str) -> str:
    """
    Translate full text by processing in chunks.
    """
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(MODEL_NAME)

    chunks = split_into_chunks(text)
    if not chunks:
        return ""

    translated_chunks = []
    for i, chunk in enumerate(chunks, 1):
        translated = translate_chunk(model, chunk, i, len(chunks))
        translated_chunks.append(translated)

        if i < len(chunks):
            time.sleep(1)

    # Print usage after translation
    usage_tracker.print_summary()

    return "\n\n".join(translated_chunks)