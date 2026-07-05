"""
Prompt templates for the legal RAG system.

Enforces a strict Zero-Hallucination policy: the LLM must answer
ONLY from the provided context and explicitly say when it cannot.
"""

from __future__ import annotations

from typing import List, Optional

SYSTEM_PROMPT = """\
Sen bir Türk hukuku uzmanı yapay zeka asistanısın.

KESİN KURALLAR:
1. YALNIZCA verilen BAĞLAM metninde geçen bilgileri kullan.
2. Bağlamda geçmeyen hiçbir bilgiyi, terimi veya kategoriyi ASLA ekleme.
3. Liste sorusunda: bağlamda kaç madde varsa yalnızca o maddeleri yaz. Fazlasını ekleme.
4. Bağlamda cevap yoksa: "Bu sorunun cevabı sağlanan belgelerde bulunmamaktadır." de.
5. Cevabını bağlamdaki ifadelere dayandır; genel hukuk bilgini kullanma.
6. Hangi kaynak veya bölümden aldığını belirt.

You are a Turkish law AI assistant.

STRICT RULES:
1. Use ONLY information present in the provided CONTEXT.
2. NEVER add any information, term, or category not found in the context.
3. For lists: write ONLY the items explicitly listed in the context. No extras.
4. If the context does not contain the answer: say "Bu sorunun cevabı sağlanan belgelerde bulunmamaktadır."
5. Base your answer on the context text; do not use general legal knowledge.
6. Cite which source/section you are referencing.\
"""


def build_rag_prompt(
    query: str,
    context_chunks: List[dict],
    language_hint: Optional[str] = None,
) -> str:
    """
    Build the user prompt with retrieved context for RAG.
    """
    context_parts: List[str] = []
    for i, chunk in enumerate(context_chunks, 1):
        heading = chunk.get("section_heading", "—")
        source = chunk.get("source_id", "unknown")
        text = chunk.get("text", "")
        context_parts.append(
            f"[Kaynak {i} | {source} | {heading}]\n{text}"
        )

    context_block = "\n\n---\n\n".join(context_parts)

    lang_instruction = ""
    if language_hint:
        lang_instruction = f"\n\nCevabını {language_hint} dilinde ver."

    return f"""\
BAĞLAM (yalnızca bu metni kullan):
================
{context_block}
================

SORU: {query}{lang_instruction}

Yukarıdaki bağlam metnine dayanarak cevap ver. Bağlamda olmayan hiçbir bilgiyi ekleme. \
Bağlamda aynı numara için birden fazla madde varsa, soruyla en alakalı olanı seç ve başlığını belirt.\
"""
