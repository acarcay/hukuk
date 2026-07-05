"""
Prompt templates for the legal RAG system.

Enforces a strict Zero-Hallucination policy: the LLM must answer
ONLY from the provided context and explicitly say when it cannot.
"""

from __future__ import annotations

from typing import List, Optional

SYSTEM_PROMPT = """\
Sen bir Türk hukuku uzmanı yapay zeka asistanısın.

KURALLAR:
1. Sana verilen BAĞLAM metnini dikkatlice oku ve soruya cevap vermek için sadece bu metindeki bilgileri kullan.
2. Bağlam metnindeki maddeleri ve bilgileri kendi kelimelerinle veya doğrudan alıntı yaparak, anlaşılır bir Türkçe ile cevapla.
3. Asla kendi hukuk bilgini kullanarak bağlamda olmayan cezalar, süreler veya terimler uydurma. 
4. Eğer sorulan sorunun cevabı sağlanan bağlam metninde kesinlikle yoksa veya alakasızsa, o zaman "Bu sorunun cevabı sağlanan belgelerde bulunmamaktadır." de.
5. Cevaplarında hangi belge veya maddeyi referans aldığını belirtmeyi unutma.

You are a Turkish law AI assistant.

RULES:
1. Read the provided CONTEXT carefully and use ONLY the information in it to answer the question.
2. You may use your own words to explain the context clearly, but remain strictly faithful to the facts in the context.
3. NEVER make up penalties, durations, or legal terms that are not in the context.
4. If the provided context does not contain the answer, say EXACTLY: "Bu sorunun cevabı sağlanan belgelerde bulunmamaktadır."
5. Always cite the document or section you are referencing.\
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
