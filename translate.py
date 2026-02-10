import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from parse import split_into_chunks
from config import MODEL_NAME, LOCAL_MODEL_PATH
import config  # Import config module to access current language settings

# =============================================================================
# Usage Tracking (Local Model)
# =============================================================================
class UsageTracker:
    """Track token usage across translations."""
    def __init__(self):
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.translations = 0
    
    def add(self, input_tokens: int, output_tokens: int):
        """Add usage from translation."""
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.translations += 1
    
    def print_summary(self):
        """Print usage summary."""
        total = self.total_input_tokens + self.total_output_tokens
        print(f"\n 📊 Local Model Usage Summary:")
        print(f"      Input tokens:  {self.total_input_tokens:,}")
        print(f"      Output tokens: {self.total_output_tokens:,}")
        print(f"      Total tokens:  {total:,}")
        print(f"      Translations:  {self.translations}")
        print(f"      💡 Running locally - no API costs!")


# Global tracker
usage_tracker = UsageTracker()

# Model cache (singleton pattern)
_tokenizer = None
_model = None


# =============================================================================
# Model Loading
# =============================================================================
def load_model():
    """Load the NLLB model and tokenizer (singleton pattern)."""
    global _tokenizer, _model
    
    if _tokenizer is None or _model is None:
        print(f"   🔄 Loading model: {MODEL_NAME}...")
        
        model_path = LOCAL_MODEL_PATH if LOCAL_MODEL_PATH else MODEL_NAME
        
        _tokenizer = AutoTokenizer.from_pretrained(model_path)
        _model = AutoModelForSeq2SeqLM.from_pretrained(model_path)
        
        # Move to GPU if available
        if torch.cuda.is_available():
            _model = _model.to("cuda")
            print("   ✓ Model loaded on GPU")
        else:
            print("   ✓ Model loaded on CPU (GPU not available)")
    
    return _tokenizer, _model


# =============================================================================
# AI Translation with Local Model
# =============================================================================
def translate_chunk(chunk: str, chunk_num: int, total_chunks: int) -> str:
    """
    Translate a single chunk using local NLLB model.
    Uses current SOURCE_LANG and TARGET_LANG from config module.
    """
    tokenizer, model = load_model()
    
    print(f"   🔄 Translating chunk {chunk_num}/{total_chunks}...", end=" ")
    
    try:
        # Set source language (read current value from config module)
        tokenizer.src_lang = config.SOURCE_LANG
        
        # Encode input text
        inputs = tokenizer(chunk, return_tensors="pt", truncation=True, max_length=1024)
        
        # Move to GPU if available
        if torch.cuda.is_available():
            inputs = {k: v.to("cuda") for k, v in inputs.items()}
        
        # Generate translation with target language
        translated_tokens = model.generate(
            **inputs,
            forced_bos_token_id=tokenizer.convert_tokens_to_ids(config.TARGET_LANG),
            max_length=1024,
            num_beams=5,
            length_penalty=1.0,
            early_stopping=True
        )
        
        # Decode output
        translated_text = tokenizer.batch_decode(translated_tokens, skip_special_tokens=True)[0]
        
        # Track usage
        input_len = len(inputs["input_ids"][0])
        output_len = len(translated_tokens[0])
        usage_tracker.add(input_len, output_len)
        
        print("✓ Done")
        return translated_text
        
    except Exception as e:
        print(f"\n   ❌ Error: {str(e)}")
        raise


def translate_text(text: str) -> str:
    """
    Translate full text by processing in chunks.
    """
    chunks = split_into_chunks(text)
    if not chunks:
        return ""
    
    translated_chunks = []
    for i, chunk in enumerate(chunks, 1):
        translated = translate_chunk(chunk, i, len(chunks))
        translated_chunks.append(translated)
    
    # Print usage after translation
    usage_tracker.print_summary()
    
    return "\n\n".join(translated_chunks)