"""
Prompt templates for the legal RAG system.

Enforces a strict Zero-Hallucination policy: the LLM must answer
ONLY from the provided context and explicitly say when it cannot.
"""

from __future__ import annotations

from typing import List, Optional

SYSTEM_PROMPT = """\
Sen bir Türk hukuku alanında uzmanlaşmış yapay zeka asistanısın.

KESİN KURALLAR:
1. YALNIZCA aşağıda sana verilen BAĞLAM (context) bilgisine dayanarak cevap ver.
2. Bağlamda bulunmayan bilgiyi ASLA uydurma veya tahmin etme.
3. Eğer soru bağlamdaki bilgilerle cevaplanamıyorsa, açıkça "Bu sorunun cevabı \
sağlanan belgelerde bulunmamaktadır." de.
4. Cevabını verirken hangi madde veya bölümden alıntı yaptığını belirt.
5. Kısa, net ve profesyonel bir dil kullan.
6. Bağlam dışına ASLA çıkma — bu en kritik kuraldır.

You are an AI assistant specialized in Turkish law.

STRICT RULES:
1. Answer ONLY based on the CONTEXT provided below.
2. NEVER fabricate or guess information not found in the context.
3. If the question cannot be answered from the context, explicitly state: \
"The answer to this question is not found in the provided documents."
4. When answering, cite which article or section you are referencing.
5. Use concise, clear, and professional language.
6. NEVER go beyond the provided context — this is the most critical rule.\
"""


def build_rag_prompt(
    query: str,
    context_chunks: List[dict],
    language_hint: Optional[str] = None,
) -> str:
    """
    Build the user prompt with retrieved context for RAG.

    Parameters
    ----------
    query
        The user's natural language question.
    context_chunks
        List of dicts with keys: ``text``, ``source_id``, ``section_heading``.
    language_hint
        Optional hint like ``"Turkish"`` or ``"English"`` to guide response language.
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
        lang_instruction = f"\n\nCevabını {language_hint} dilinde ver. / Answer in {language_hint}."

    return f"""\
BAĞLAM / CONTEXT:
================
{context_block}
================

SORU / QUESTION:
{query}{lang_instruction}

Yukarıdaki bağlama dayanarak cevap ver. Bağlamda olmayan bilgiyi ekleme.
Answer based on the context above. Do not add information not in the context."""
