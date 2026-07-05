import asyncio
import httpx
import os
from pathlib import Path

API_URL = "http://127.0.0.1:8000/api/v1"

async def upload_documents():
    print("🚀 Belgeler yükleniyor...")
    sample_dir = Path("sample_data")
    files_to_upload = [
        sample_dir / "kira_sozlesmesi.docx",
        sample_dir / "kvkk_metni.rtf"

    ]
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Dosyaları form-data olarak hazırla
        files_data = []
        for file_path in files_to_upload:
            if file_path.exists():
                files_data.append(("files", (file_path.name, open(file_path, "rb"), "application/octet-stream")))
        
        if not files_data:
            print("❌ Yüklenecek belge bulunamadı! Lütfen sample_data klasörünü kontrol edin.")
            return

        response = await client.post(f"{API_URL}/upload", files=files_data)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Başarılı! {len(data['documents'])} belge, toplam {data['total_chunks']} parçaya bölünerek vektör veritabanına eklendi.")
            for doc in data['documents']:
                print(f"  - {doc['filename']} ({doc['chunks_created']} parça)")
        else:
            print(f"❌ Yükleme Hatası: {response.text}")

async def ask_questions():
    questions = [
        "Kira bedeli ne kadar ve ödeme ne zaman yapılacak?",
        "Gizlilik sözleşmesine göre ihlal cezası ne kadardır?",
        "Kişisel verilerimin eksik işlenmesi durumunda hangi haklara sahibim?"
    ]
    
    print("\n🤖 Asistana (Ollama RAG) Sorular Soruluyor...\n" + "-"*50)
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        for q in questions:
            print(f"Soru: {q}")
            response = await client.post(f"{API_URL}/chat", json={"query": q, "stream": False})
            
            if response.status_code == 200:
                answer = response.json()["answer"]
                context_chunks = response.json().get("context", [])
                print(f"Cevap: {answer}")
                if context_chunks:
                    sources = {s["source_id"] for s in context_chunks}
                    print(f"Kaynaklar: {', '.join(sources)}")
            else:
                print(f"❌ Hata: {response.text}")
            print("-" * 50)

async def main():
    # 1. Belgeleri Yükle
    await upload_documents()
    # 2. RAG Sistemine Soru Sor
    await ask_questions()

if __name__ == "__main__":
    asyncio.run(main())
