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
1. Cevabını yalnızca BAĞLAM metnindeki bilgilere dayandır ve ilgili maddeyi referans göstererek anlaşılır bir dille açıkla. Kendi genel hukuk bilgini KULLANMA.
2. Soru birden fazla alt soru içeriyorsa (örn. "X nedir? veya Y kaç ay?"), her alt soruyu AYRI AYRI ele al: bağlamda cevabı olanları cevapla; yalnızca cevabı gerçekten olmayan alt soru için "Bu sorunun cevabı sağlanan belgelerde bulunmamaktadır." de.
3. Soru kesin bir sayı veya oran sorsa bile, bağlam bunun yerine bir kural/yöntem/mekanizma tanımlıyorsa (örn. sabit bir yüzde yerine "TÜFE on iki aylık ortalamasını geçmemek üzere belirlenir"), bu kuralı cevap olarak AÇIKLA; "bulunamadı" deme.
4. Sorunun HİÇBİR kısmına dair bağlamda bilgi yoksa sadece şu cümleyi yaz ve dur: "Bu sorunun cevabı sağlanan belgelerde bulunmamaktadır." Ekstra yorum ekleme.\
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
Bağlamda aynı numara için birden fazla madde varsa, soruyla en alakalı olanı seç ve başlığını belirt. \
Soru birden fazla alt soru içeriyorsa her birini ayrı ayrı cevapla.\
"""
