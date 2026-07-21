# Sentetik Eğitim Belgeleri

Bu klasördeki 18 sözleşme **tamamen sentetiktir** — fine-tune veri seti üretimi
için tasarlanmış şablonlardır. Tüm kişi adları, T.C. numaraları, plakalar,
tutarlar ve tarihler **kurgusaldır**; gerçek kişi/kurum verisi içermez (KVKK
riski yok) ve telif korumasına tabi bir kaynaktan alınmamıştır.

**Hukuki uyarı:** Bu belgeler eğitim verisi üretimi içindir; gerçek hukuki
işlemlerde şablon olarak kullanılmak üzere hazırlanmamıştır.

## Çeşitlilik bilinçlidir

Model ezber yapamasın, bağlamı okumayı öğrensin diye:
- Farklı **artış mekanizmaları**: TÜFE'ye bağlı (konut kira) vs sabit %20 (işyeri kira)
- **Deneme süresi** olan (2 ay / 1 ay) ve olmayan (belirli süreli) iş sözleşmeleri
- **Cezai şart** içeren ve içermeyen sözleşmeler
- Farklı uyuşmazlık yolları: mahkeme, zorunlu arabuluculuk, İSTAC tahkimi
- Her belgede farklı tutar, süre, oran ve şehir

## Kullanım

```bash
# Korpusu yeniden üretmek / genişletmek için:
python3 scripts/build_training_docs.py

# Bu belgelerden fine-tune verisi üretmek için (Ollama çalışıyor olmalı):
python3 scripts/generate_finetune_data.py \
  --docs-dir training_docs \
  --questions-per-chunk 3 \
  --negative-ratio 0.25 \
  --output hukuk_veri_seti_rag.jsonl
```

Yeni sözleşme eklemek için `scripts/build_training_docs.py` içindeki
`CONTRACTS` listesine ekleyip script'i tekrar çalıştırın.
