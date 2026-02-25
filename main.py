"""
Easy PDF Translator v2.0
CLI entry point — Milestone 7: Full interactive UX.
"""

import sys
import time

import pdfplumber

from client import CppClient
from config import (
    CPP_SERVER_PORT,
    DEFAULT_SOURCE_LANG,
    DEFAULT_TARGET_LANG,
    GROQ_MODEL_TRANSLATE,
    INPUT_DIR,
    OUTPUT_DIR,
    SUPPORTED_LANGUAGES,
    ensure_directories,
    print_supported_languages,
    set_languages,
)
from parse import _generate_doc_id
from process import process_pdf, process_txt
from rag import rag_loop
from translate import usage_tracker


# =============================================================================
# ANSI Colors
# =============================================================================
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"


def ok(msg: str) -> str:
    return f"{GREEN}\u2713 {msg}{RESET}"


def err(msg: str) -> str:
    return f"{RED}\u2717 {msg}{RESET}"


def warn(msg: str) -> str:
    return f"{YELLOW}! {msg}{RESET}"


# =============================================================================
# Progress Bar
# =============================================================================
_progress_start: float = 0.0


def progress_callback(current: int, total: int, skipped: int):
    """Real-time progress bar with ETA, printed on one line."""
    global _progress_start
    if current == 1:
        _progress_start = time.time()

    elapsed = time.time() - _progress_start
    if current > 0 and elapsed > 0:
        rate = current / elapsed
        remaining = (total - current) / rate if rate > 0 else 0
        eta = format_time(remaining)
    else:
        eta = "..."

    bar_width = 20
    filled = int(bar_width * current / total) if total > 0 else 0
    bar = "\u2588" * filled + "\u2591" * (bar_width - filled)

    status = f"[SKIP: {skipped}] " if skipped else ""
    line = f"\r   Progress: {bar}  {current}/{total} chunks  {status}[ETA: {eta}]"
    sys.stdout.write(line)
    sys.stdout.flush()

    if current == total:
        sys.stdout.write("\n")
        sys.stdout.flush()


def format_time(seconds: float) -> str:
    """Format seconds into a human-readable string."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s:02d}s"


# =============================================================================
# File Discovery
# =============================================================================
def get_pdf_page_count(path) -> int | None:
    """Quickly get PDF page count without full extraction."""
    try:
        with pdfplumber.open(path) as pdf:
            return len(pdf.pages)
    except Exception:
        return None


def discover_files():
    """Find files in input/ and display them with page counts."""
    pdf_files = sorted(INPUT_DIR.glob("*.pdf"))
    txt_files = sorted(INPUT_DIR.glob("*.txt"))
    all_files = pdf_files + txt_files

    if not all_files:
        return []

    print(f"\n{BOLD}Found {len(all_files)} file(s):{RESET}")
    for i, f in enumerate(all_files, 1):
        if f.suffix == ".pdf":
            pages = get_pdf_page_count(f)
            page_info = f"  ({pages} pages)" if pages else ""
            print(f"   [{i}] {f.name}{page_info}")
        else:
            print(f"   [{i}] {f.name}")

    return all_files


# =============================================================================
# Language Selection
# =============================================================================
def select_language(prompt: str, default: str) -> str:
    while True:
        user_input = input(prompt).strip().lower()
        if not user_input:
            return default
        if user_input in SUPPORTED_LANGUAGES:
            return user_input
        print(f"   {err('Invalid language code:')} '{user_input}'. Try again.")


def configure_languages() -> bool:
    print_supported_languages()

    print(f"\n   Source [{DEFAULT_SOURCE_LANG}] \u2192 Target [{DEFAULT_TARGET_LANG}]"
          f"  (Press Enter for defaults)")

    source = select_language(f"   Source [{DEFAULT_SOURCE_LANG}]: ", DEFAULT_SOURCE_LANG)
    target = select_language(f"   Target [{DEFAULT_TARGET_LANG}]: ", DEFAULT_TARGET_LANG)

    if source == target:
        print(f"   {warn('Source and target languages are the same!')}")
        return False

    set_languages(source, target)
    return True


# =============================================================================
# Main
# =============================================================================
def main():
    overall_start = time.time()

    # --- Banner ---
    print("=" * 60)
    print(f"   {BOLD}Easy PDF Translator v2.0{RESET}")
    print(f"   Model: Groq API ({GROQ_MODEL_TRANSLATE})")
    print("=" * 60)

    # --- Directories ---
    ensure_directories()

    # --- Server check ---
    cpp_client = CppClient()
    if cpp_client.is_alive():
        print(ok(f"cpp_server connected (port: {CPP_SERVER_PORT})"))
    else:
        print(warn("cpp_server not reachable \u2014 VectorDB features disabled"))
        print(f"   Start it with: ./cpp_server/build/vectordb_server")
        cpp_client = None

    # --- Languages ---
    if not configure_languages():
        input("\nPress Enter to exit...")
        return

    # --- File discovery ---
    all_files = discover_files()
    if not all_files:
        print(f"\n   No PDF or TXT files found in '{INPUT_DIR.name}/' folder.")
        print("   Please drop your files there and run again.")
        input("\nPress Enter to exit...")
        return

    # --- Confirm ---
    confirm = input(f"\n   \u25b6 Start translation? [Y/n]: ").strip().lower()
    if confirm in ("n", "no"):
        print("   Cancelled.")
        return

    # --- Process files ---
    success_count = 0
    fail_count = 0
    translated_files: list[tuple[str, str]] = []  # (filename, doc_id)

    for i, file_path in enumerate(all_files, 1):
        print("\n" + "-" * 60)
        print(f"{BOLD}[{i}/{len(all_files)}] {file_path.name}{RESET}")

        if file_path.suffix == ".pdf":
            ok_flag = process_pdf(file_path, client=cpp_client, on_progress=progress_callback)
        else:
            ok_flag = process_txt(file_path, client=cpp_client, on_progress=progress_callback)

        if ok_flag:
            success_count += 1
            doc_id = _generate_doc_id(file_path.name)
            translated_files.append((file_path.name, doc_id))
        else:
            fail_count += 1

    # --- Summary ---
    total_elapsed = time.time() - overall_start
    print("\n" + "=" * 60)
    print(f"   {BOLD}TRANSLATION COMPLETE{RESET}")
    print(f"   {GREEN}\u2713 Successful: {success_count}{RESET}")
    if fail_count:
        print(f"   {RED}\u2717 Failed: {fail_count}{RESET}")
    print(f"   Tokens: {usage_tracker.total_input_tokens:,} in"
          f" + {usage_tracker.total_output_tokens:,} out"
          f" = {usage_tracker.total_input_tokens + usage_tracker.total_output_tokens:,} total")
    if usage_tracker.skipped:
        print(f"   {YELLOW}Skipped chunks: {usage_tracker.skipped}{RESET}")
    print(f"   Elapsed: {format_time(total_elapsed)}")
    print(f"   Output folder: {OUTPUT_DIR}")
    print("=" * 60)

    # --- RAG QA mode ---
    if cpp_client and translated_files:
        enter_rag = input("\n   Enter RAG QA mode? [Y/n]: ").strip().lower()
        if enter_rag not in ("n", "no"):
            if len(translated_files) == 1:
                filename, doc_id = translated_files[0]
                rag_loop(doc_id, filename, cpp_client)
            else:
                print(f"\n   Select a document for QA:")
                for j, (fname, _) in enumerate(translated_files, 1):
                    print(f"   [{j}] {fname}")

                while True:
                    choice = input(f"   Document [1-{len(translated_files)}]: ").strip()
                    if choice.isdigit() and 1 <= int(choice) <= len(translated_files):
                        filename, doc_id = translated_files[int(choice) - 1]
                        rag_loop(doc_id, filename, cpp_client)
                        break
                    print(f"   {err('Invalid choice.')}")

    print("\nDone.")


if __name__ == "__main__":
    main()
