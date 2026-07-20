"""
Prompt templates for the legal RAG system.

Enforces a strict Zero-Hallucination policy: the LLM must answer
ONLY from the provided context and explicitly say when it cannot.
"""

from __future__ import annotations

from typing import List, Optional

# Canonical "no answer in context" sentence — single source of truth so the
# system prompt, the API's article-range formatter, and any tooling that
# needs to recognize/produce this exact string (e.g. synthetic fine-tuning
# data generation) never drift apart.
NOT_FOUND_ANSWER = "Bu sorunun cevabı sağlanan belgelerde bulunmamaktadır."

SYSTEM_PROMPT = f"""\
Sen bir Türk hukuku uzmanı yapay zeka asistanısın.

GÖREVİN: Kullanıcının sorusunu SADECE sana verilen BAĞLAM metnine dayanarak cevaplamaktır.

KURALLAR:
1. Cevabını yalnızca BAĞLAM metnindeki bilgilere dayandır ve ilgili maddeyi referans göstererek anlaşılır bir dille açıkla. Kendi genel hukuk bilgini KULLANMA.
2. Soru birden fazla alt soru içeriyorsa (örn. "X nedir? veya Y kaç ay?"), her alt soruyu AYRI AYRI ele al: bağlamda cevabı olanları cevapla; yalnızca cevabı gerçekten olmayan alt soru için "{NOT_FOUND_ANSWER}" de.
3. Soru kesin bir sayı veya oran sorsa bile, bağlam bunun yerine bir kural/yöntem/mekanizma tanımlıyorsa (örn. sabit bir yüzde yerine "TÜFE on iki aylık ortalamasını geçmemek üzere belirlenir"), bu kuralı cevap olarak AÇIKLA; "bulunamadı" deme.
4. Sorunun HİÇBİR kısmına dair bağlamda bilgi yoksa sadece şu cümleyi yaz ve dur: "{NOT_FOUND_ANSWER}" Ekstra yorum ekleme.\
"""


def format_context_block(context_chunks: List[dict]) -> str:
    """
    Render retrieved chunks as the numbered "[Kaynak N | source | heading]"
    block shared by ``build_rag_prompt`` and any offline tooling (e.g.
    fine-tuning data generation) that needs to match the exact input format
    the model sees at inference time.
    """
    context_parts: List[str] = []
    for i, chunk in enumerate(context_chunks, 1):
        heading = chunk.get("section_heading", "—")
        source = chunk.get("source_id", "unknown")
        text = chunk.get("text", "")
        context_parts.append(
            f"[Kaynak {i} | {source} | {heading}]\n{text}"
        )
    return "\n\n---\n\n".join(context_parts)


def build_rag_prompt(
    query: str,
    context_chunks: List[dict],
    language_hint: Optional[str] = None,
) -> str:
    """
    Build the user prompt with retrieved context for RAG.
    """
    context_block = format_context_block(context_chunks)

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
Bağlamda aynı numara için birden fazla madde varsa, soruyla en alakalı olanı seç ve başlığını belirt. \
Soru birden fazla alt soru içeriyorsa her birini ayrı ayrı cevapla.\
"""
