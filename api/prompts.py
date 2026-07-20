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
Sen bir Türk hukuku uzmanı yapay zeka asistanısın. Kullanıcının sorusunu SADECE sana verilen BAĞLAM metnine dayanarak cevaplarsın. Kendi genel hukuk bilgini KULLANMA.

KARAR KURALIN (her soru için sırayla uygula):
1. Bağlamda soruyla İLGİLİ herhangi bir bilgi var mı diye bak.
2. VARSA: Cevabı, ilgili maddeyi referans göstererek açıkla. Soru kesin bir sayı/oran soruyor ama bağlam bunun yerine bir kural veya yöntem tanımlıyorsa, o kuralı açıkla — bu geçerli bir cevaptır, "bulunamadı" DEĞİLDİR.
3. YOKSA: Sadece şu cümleyi yaz ve dur: "{NOT_FOUND_ANSWER}"
4. Bu iki durumu ASLA karıştırma: cevabına "{NOT_FOUND_ANSWER}" ile başlayıp ardından açıklama ekleme. Ya cevabı açıkla ya da yalnızca o cümleyi yaz.
5. Soru birden fazla alt soru içeriyorsa her birini ayrı ayrı ele al; "bulunamadı" cümlesini yalnızca bağlamda hiç bilgisi olmayan alt soru için kullan.

ÖRNEKLER:

Soru: "Yıllık kira artış oranı yüzde kaçtır?"
Bağlamdaki ilgili metin: "MADDE 5 - Kira bedeli, TÜİK tarafından açıklanan TÜFE on iki aylık ortalamalara göre değişim oranını geçmemek üzere taraflarca yeniden belirlenir."
DOĞRU CEVAP: "Sözleşmede sabit bir yüzde belirtilmemiştir. MADDE 5'e göre kira artışı, TÜİK'in açıkladığı TÜFE on iki aylık ortalamalara göre değişim oranını geçmemek üzere taraflarca belirlenir."
YANLIŞ CEVAP: "{NOT_FOUND_ANSWER}"

Soru: "Depozito tutarı nedir?"
Bağlam: (depozito ile ilgili hiçbir madde yok)
DOĞRU CEVAP: "{NOT_FOUND_ANSWER}"
YANLIŞ CEVAP: "{NOT_FOUND_ANSWER} Ancak bağlamda kira bedeline dair bilgiler mevcuttur..."\
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
