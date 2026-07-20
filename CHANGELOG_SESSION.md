# Değişiklik Özeti & Çalıştırma Rehberi

Bu belge, bu oturumda projeye yapılan tüm değişiklikleri ve sistemi
çalıştırma komutlarını özetler. Baz commit: `6d55ae7`.

---

## 1. Çalıştırma Komutları

### Ön gereksinimler (tek seferlik)

```bash
# Python bağımlılıkları
cd /Users/acar/Desktop/hukuk
pip install -r requirements.txt

# Ollama (LLM motoru)
brew install ollama
ollama pull llama3.1:8b

# (Opsiyonel) taranmış PDF'ler için OCR
brew install tesseract tesseract-lang
```

### Terminal 1 — Ollama (modeli bellekte tutarak)

```bash
OLLAMA_KEEP_ALIVE=-1 ollama serve
```

### Terminal 2 — Backend API

```bash
cd /Users/acar/Desktop/hukuk

# Geliştirme (auth kapalı)
PYTHONPATH=. uvicorn api.main:app --reload --port 8000

# veya auth açık (üretime yakın)
API_KEY=guclu-bir-sifre PYTHONPATH=. uvicorn api.main:app --port 8000
```

- Swagger arayüzü: http://localhost:8000/docs
- `PYTHONPATH=.` → Python'un import ederken proje kökünü aramasını sağlar
  (`api`, `legal_doc_ingestion` paketleri burada). Önce `cd` ile köke gir.

### Terminal 3 — Flutter uygulaması

```bash
cd /Users/acar/Desktop/hukuk/hukuk_app
export LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8   # CocoaPods locale hatasını önler

# Web (önerilen — Xcode/CocoaPods gerektirmez)
flutter run -d chrome --web-port=3000        # port 3000: backend CORS listesinde

# Auth açıksa aynı anahtarı ver:
flutter run -d chrome --web-port=3000 --dart-define=API_KEY=guclu-bir-sifre
```

> **macOS masaüstü (`-d macos`) şu an çalışmıyor:** Flutter 3.35.7 ↔ Xcode 26
> uyumsuzluğu (FlutterMacOS/SwiftUICore link hatası). Düzeltmek için
> `flutter upgrade` gerekir. Web sürümü sorunsuz çalışıyor.

### API'yi doğrudan test (uygulamasız)

```bash
# Belge yükle
curl -X POST http://localhost:8000/api/v1/upload \
  -F "files=@sample_data/kira_sozlesmesi.docx"

# Soru sor (streaming)
curl -N -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "Kira bedeli nedir?", "stream": true}'

# Auth açıksa her isteğe ekle:  -H "X-API-Key: guclu-bir-sifre"
```

### Testler

```bash
cd /Users/acar/Desktop/hukuk
python3 -m pytest tests/ -q          # 76 test
```

### Fine-tune verisi üretme (yeni araç)

```bash
# Önce kaç chunk bulunacağını gör (Ollama çağırmaz)
python3 scripts/generate_finetune_data.py --docs-dir sample_data --dry-run

# Gerçek üretim (kendi belgelerini ayrı bir klasöre topla)
python3 scripts/generate_finetune_data.py \
  --docs-dir sample_data \
  --questions-per-chunk 3 \
  --negative-ratio 0.25 \
  --output hukuk_veri_seti_rag.jsonl
```

---

## 2. Yapılan Değişiklikler (commit sırasıyla)

### Güvenlik

**`f1ecbd2` — API-key auth, CORS sertleştirme, KVKK audit log**
- Yeni `api/security.py`: `X-API-Key` başlığı ile sabit-zaman doğrulama.
  `API_KEY` set edilince `/upload`, `/chat`, `/documents` korunur; boşsa
  auth kapalı (dev) + başlangıçta uyarı.
- Sunucu varsayılanı `0.0.0.0` → `127.0.0.1`.
- CORS: mantıklı varsayılan origin listesi; `*` seçilince credentials
  otomatik kapanır (tarayıcı zaten reddediyordu).
- `legal_rag.access` logger'ına otomatik `RotatingFileHandler`
  (`AUDIT_LOG_FILE`, varsayılan `logs/access.log`).
- Config `pydantic-settings`'e taşındı → gerçek `.env` desteği (+`.env.example`).

**`ddb7f61` — Upload'ı diske stream et + boyut limiti**
- Dosya 1 MB'lık parçalarla diske yazılır; limit aşılınca hemen kesilip
  yarım dosya silinir (önceden tüm dosya RAM'e alınıp sonra kontrol ediliyordu).

**`d3f86cd` — Delete path-traversal sertleştirme + public store API**
- `delete_document` artık basename'e indirger ve silmeden önce yolun
  `UPLOAD_DIR` içinde kaldığını doğrular (`../` saldırısını engeller).
- `ChromaVectorStore.get_all` / `get_source_metadata` public metotları;
  route'lardaki 3 private `_get_collection()` erişimi kaldırıldı.

### Frontend

**`d35da6f` — SSE parser + konfigüre edilebilir base URL / API key**
- SSE byte akışı chunk sınırları arasında buffer'lanır; yalnızca tam olaylar
  (`\n\n` ile ayrılan) parse edilir → ağda token kaybı/bozulması giderildi.
- `X-API-Key` başlığı gönderilir; base URL ve API key `--dart-define` ile
  ayarlanabilir.

### Test & Dokümantasyon

**`3dbb3e7` — API-key auth testleri** (401/200/kapalı-geçiş/health-açık).
**`f351979` — README:** auth, CORS, `.env`, `--workers` uyarısı hizalandı.

### RAG Kalitesi

**`5304669` — Bileşik soru ayrıştırma + prompt yumuşatma**
- Retrieval: "X? veya Y?" tipi sorular alt-sorulara bölünür, her biri ayrı
  aranır, sonuçlar round-robin birleştirilir. (Önceden bulanık ortalama
  embedding bir konuyu tamamen kaçırıyordu.)
- Prompt: çok parçalı sorular parça parça cevaplanır; bağlam kesin sayı yerine
  bir mekanizma tanımlıyorsa (örn. TÜFE'ye bağlı kira artışı) "bulunamadı"
  yerine kural açıklanır.

### Fine-tune Aracı

**`6f1c676` — Sentetik fine-tune verisi üreteci + prompt DRY**
- `api/prompts.py`: `NOT_FOUND_ANSWER` sabiti + `format_context_block()`
  helper (prompt, retrieval ve araçlar aynı formatı paylaşır).
- `scripts/generate_finetune_data.py`: belgeleri API ile aynı pipeline'dan
  geçirip her chunk için Ollama'ya grounded Türkçe soru-cevap ürettirir;
  alakasız bağlam eşleyerek negatif ("bulunamadı") örnekler sentezler.
  Çıktı Alpaca formatında, yeni dosyaya yazılır (mevcut veri seti korunur).

### Performans

**`7d48efa` — Modeli sıcak tut, sessiz context kırpmayı düzelt, top_k düşür**
- `keep_alive` (varsayılan `30m`): soğuk model yükleme maliyeti kalkar.
- `num_ctx=4096`: Ollama'nın varsayılan 2048'i RAG bağlamını sessizce
  kırpıyordu → model artık tüm chunk'ları görüyor.
- `RAG_TOP_K` 8→5, max bağlam 16000→10000 karakter: daha az prefill = daha
  hızlı ilk token.

---

## 3. Yeni / Değişen Dosyalar

| Dosya | Durum |
|-------|-------|
| `api/security.py` | **yeni** — API-key auth |
| `scripts/generate_finetune_data.py` | **yeni** — fine-tune veri üreteci |
| `.env.example` | **yeni** — örnek konfigürasyon |
| `api/config.py` | pydantic-settings, auth, CORS, perf ayarları |
| `api/main.py` | auth uyarısı, CORS mantığı, audit handler |
| `api/llm.py` | keep_alive + num_ctx |
| `api/prompts.py` | NOT_FOUND_ANSWER, format_context_block, prompt kuralları |
| `api/routes/upload.py` | streaming upload + auth |
| `api/routes/chat.py` | bileşik soru ayrıştırma, delete sertleştirme, auth |
| `legal_doc_ingestion/vectorization/store.py` | public get_all/get_source_metadata |
| `hukuk_app/lib/services/api_service.dart` | SSE fix + konfigüre edilebilir URL/key |
| `tests/test_api.py` | auth + subquery testleri |
| `requirements.txt` | pydantic-settings |
| `README.md` | dokümantasyon hizalama |

**Not:** `hukuk_veri_seti.jsonl` (fine-tune veri setin) `[cite: N]` artefaktları
temizlendi ama bilerek git'e eklenmedi — senin gözden geçirmen gereken veri.

---

## 4. Model Değişimi Planı (ileride)

Backend model etiketini `OLLAMA_MODEL` env'inden okur, yani modeli değiştirmek
kod değişikliği gerektirmez — sadece `.env`'de bir satır:

```bash
# .env
OLLAMA_MODEL=hf.co/<kullanici>/<repo>:Q4_K_M
```

Fine-tune için: veri setini `input` alanına BAĞLAM bloğu koyarak
(RAG formatında) hazırla; birkaç "bağlamda yok → bulunamadı" örneği ekle ki
zero-hallucination davranışı korunsun. `scripts/generate_finetune_data.py`
tam bu formatta üretiyor.
