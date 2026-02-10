from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

MODEL_ID = "facebook/nllb-200-distilled-600M"

def download():
    print(f"Downloading model: {MODEL_ID}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_ID)
    print("Download complete!")

if __name__ == "__main__":
    download()