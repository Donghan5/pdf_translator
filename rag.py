"""
RAG QA module — Flow 2: Retrieval-Augmented QA over stored documents.
Milestone 6: Search VectorDB for relevant chunks, build context prompt, call Groq API.
"""

from groq import Groq, RateLimitError, APIError

import config
from client import CppClient

# Reuse the lazy Groq client from translate.py
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


def ask_question(
    query: str,
    doc_id: str,
    client: CppClient,
    top_k: int = 5,
) -> tuple[str, list[int]]:
    """
    Answer a question using RAG over a stored document.

    Args:
        query: The user's question.
        doc_id: Document ID to search within.
        client: Connected CppClient instance.
        top_k: Number of chunks to retrieve.

    Returns:
        (answer_text, source_pages) tuple.
        source_pages is a sorted list of unique page numbers cited.
    """
    # 1. Search VectorDB for relevant chunks
    print("   Searching relevant chunks...")
    results = client.search(query=query, top_k=top_k, doc_id=doc_id)

    if not results:
        return "No relevant content found. Please rephrase your question.", []

    # 2. Build context from retrieved chunks
    context_parts = []
    source_pages: set[int] = set()

    for r in results:
        text = r.get("text", "")
        metadata = r.get("metadata", {})

        # Prefer translated text if available
        display_text = metadata.get("translated_text", text)
        context_parts.append(display_text)

        # Collect page numbers
        page_start = metadata.get("page_start")
        page_end = metadata.get("page_end")
        if page_start is not None:
            source_pages.add(int(page_start))
        if page_end is not None:
            source_pages.add(int(page_end))

    context = "\n\n".join(context_parts)

    # 3. Build RAG prompt (claude.md Section 5 template)
    prompt = (
        "Answer the question based only on the provided context.\n"
        "If the answer is not in the context, say \"I don't know.\"\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {query}"
    )

    # 4. Call Groq API with QA model
    print("   Generating answer...")
    groq_client = _get_client()

    try:
        response = groq_client.chat.completions.create(
            model=config.GROQ_MODEL_QA,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=1024,
        )
        answer = response.choices[0].message.content.strip()
    except (RateLimitError, APIError) as e:
        answer = f"API error: {e}"

    return answer, sorted(source_pages)


def rag_loop(doc_id: str, filename: str, client: CppClient):
    """Interactive RAG QA loop for a document."""
    print("\n" + "=" * 60)
    print("   RAG QA Mode")
    print(f"   Document: {filename}")
    print("   Type 'q' to quit")
    print("=" * 60)

    while True:
        try:
            query = input("\n   Question: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not query:
            continue
        if query.lower() in ("q", "quit"):
            break

        answer, pages = ask_question(query, doc_id, client)

        print(f"\n   Answer:\n   {answer}")
        if pages:
            print(f"\n   Source pages: {', '.join(str(p) for p in pages)}")

    print("\n   Exiting RAG QA mode.")
