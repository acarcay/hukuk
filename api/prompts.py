"""
Prompt templates for the legal RAG system.

Enforces a strict Zero-Hallucination policy: the LLM must answer
ONLY from the provided context and explicitly say when it cannot.
"""

from __future__ import annotations

from typing import List, Optional

SYSTEM_PROMPT = """\
Sen bir Türk hukuku uzmanı yapay zeka asistanısın.

GÖREVİN: Kullanıcının sorusunu SADECE sana verilen BAĞLAM metnine dayanarak cevaplamaktır.

KURALLAR:
1. Eğer BAĞLAM metni sorunun cevabını İÇERİYORSA: Cevabı anlaşılır bir dille, ilgili maddeyi referans göstererek açıkla.
2. Eğer BAĞLAM metni sorunun cevabını İÇERMİYORSA: Sadece şu cümleyi yaz ve dur: "Bu sorunun cevabı sağlanan belgelerde bulunmamaktadır." Asla "Cevap yoktur" gibi başka bir ifade kullanma ve kesinlikle ekstra yorum ekleme.
3. Kendi genel hukuk bilgini KULLANMA, sadece bağlama sadık kal.\
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
