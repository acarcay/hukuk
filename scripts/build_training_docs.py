#!/usr/bin/env python3
"""
Build the synthetic training-document corpus under ``training_docs/``.

Generates 18 varied, MADDE-structured Turkish contract templates as .docx
files (the ingestion pipeline supports .pdf/.docx/.rtf — not .txt). All
parties, ID numbers, amounts and dates are FICTIONAL. The variety is
deliberate — different amounts, increase mechanisms (TÜFE vs. fixed %),
contracts with and without probation/penalty clauses, different dispute
resolution paths — so a fine-tuned model must read the context instead of
memorizing one canonical answer.

Usage:
    python3 scripts/build_training_docs.py
    # then, on the training machine:
    python3 scripts/generate_finetune_data.py --docs-dir training_docs ...
"""

from __future__ import annotations

import sys
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent / "training_docs"

CONTRACTS: list[tuple[str, str]] = [
    ("konut_kira_sozlesmesi.docx", """\
KONUT KİRA SÖZLEŞMESİ

İşbu sözleşme, aşağıda bilgileri yer alan Kiraya Veren ile Kiracı arasında aşağıdaki şartlarla akdedilmiştir. Taraf bilgileri kurgusaldır.

MADDE 1 - TARAFLAR
Kiraya Veren: Selim ARSLAN, T.C. No: 11111111110, Adres: Caferağa Mah. Moda Cad. No:41, Kadıköy/İSTANBUL.
Kiracı: Deniz KOÇ, T.C. No: 22222222220, Adres: Osmanağa Mah. Söğütlüçeşme Cad. No:7, Kadıköy/İSTANBUL.

MADDE 2 - KİRALANAN TAŞINMAZ
Kiralanan, Caferağa Mahallesi, Sakız Sokak No:12 Daire:6 Kadıköy/İSTANBUL adresindeki 2+1, brüt 95 m² konuttur. Taşınmaz eşyasız teslim edilmiştir.

MADDE 3 - KİRA SÜRESİ
Kira süresi 1 (bir) yıl olup 01.10.2026 tarihinde başlar. Taraflardan biri sürenin bitiminden en az 15 gün önce yazılı bildirimde bulunmadıkça sözleşme aynı koşullarla birer yıl uzar.

MADDE 4 - KİRA BEDELİ
Aylık kira bedeli 32.000 TL olup her ayın en geç 3'üncü günü Kiraya Verenin banka hesabına ödenir.

MADDE 5 - KİRA ARTIŞI
Yenilenen kira dönemlerinde kira bedeli, TÜİK tarafından açıklanan TÜFE on iki aylık ortalamalara göre değişim oranını geçmemek üzere artırılır.

MADDE 6 - DEPOZİTO
Kiracı, iki aylık kira tutarı olan 64.000 TL güvence bedelini imza tarihinde ödemiştir. Depozito, taşınmazın hasarsız teslimi ve borç bulunmaması halinde iade edilir.

MADDE 7 - GİDERLER
Elektrik, su, doğalgaz, internet ve apartman aidatı Kiracıya; deprem sigortası (DASK) ve emlak vergisi Kiraya Verene aittir.

MADDE 8 - ALT KİRA YASAĞI
Kiracı, Kiraya Verenin yazılı izni olmadan taşınmazı üçüncü kişilere kısmen veya tamamen devredemez ve alt kiraya veremez.

MADDE 9 - TAHLİYE
Kira bedelinin art arda iki ay ödenmemesi halinde Kiraya Veren yazılı ihtarla 30 günlük süre verir; ödeme yapılmazsa tahliye talepli icra takibi başlatabilir.

MADDE 10 - UYUŞMAZLIK
Uyuşmazlıklarda İstanbul Anadolu Mahkemeleri ve İcra Daireleri yetkilidir.

İşbu sözleşme 10 maddeden ibaret olup 20.09.2026 tarihinde iki nüsha düzenlenmiştir.
KİRAYA VEREN: Selim ARSLAN          KİRACI: Deniz KOÇ
"""),
    ("isyeri_kira_sozlesmesi.docx", """\
İŞYERİ KİRA SÖZLEŞMESİ

İşbu işyeri kira sözleşmesi aşağıdaki taraflar arasında akdedilmiştir. Taraf bilgileri kurgusaldır.

MADDE 1 - TARAFLAR
Kiraya Veren: Hasan DEMİRTAŞ, Kızılay Mah. Atatürk Bulvarı No:88, Çankaya/ANKARA.
Kiracı: Meltem Gıda Sanayi ve Ticaret Ltd. Şti., Vergi No: 1234567890, temsilen Müdür Ayşe MELTEM.

MADDE 2 - KİRALANAN
Kızılay Mah. Sakarya Cad. No:15 Çankaya/ANKARA adresindeki zemin kat 140 m² dükkan, restoran işletmeciliği amacıyla kiralanmıştır.

MADDE 3 - SÜRE
Kira süresi 5 (beş) yıl olup 01.11.2026 tarihinde başlar.

MADDE 4 - KİRA BEDELİ
Aylık kira bedeli 85.000 TL + KDV olup her ayın 5'inci gününe kadar ödenir. Stopaj yükümlülüğü Kiracıya aittir.

MADDE 5 - KİRA ARTIŞI
Kira bedeli her yıl dönümünde bir önceki yılın kirasına yüzde 20 (yirmi) sabit oran uygulanarak artırılır.

MADDE 6 - DEPOZİTO
Kiracı üç aylık kira tutarında (255.000 TL) depozitoyu nakden ödemiştir.

MADDE 7 - CEZAİ ŞART
Kiracının sözleşmeyi süresinden önce haksız feshi halinde üç aylık kira bedeli tutarında cezai şart Kiraya Verene ödenir.

MADDE 8 - TADİLAT
Kiracı, Kiraya Verenin yazılı onayı olmadan esaslı tadilat yapamaz. Onaylı tadilatlar tahliyede sökülmeksizin kalır ve bedel talep edilemez.

MADDE 9 - KULLANIM
Kiralanan yalnızca restoran olarak kullanılabilir; faaliyet konusu Kiraya Verenin yazılı izni olmadan değiştirilemez.

MADDE 10 - UYUŞMAZLIK
Uyuşmazlıklarda Ankara Mahkemeleri ve İcra Daireleri yetkilidir.

İşbu sözleşme 10 maddeden ibaret olup 15.10.2026 tarihinde imzalanmıştır.
KİRAYA VEREN: Hasan DEMİRTAŞ          KİRACI: Meltem Gıda Ltd. Şti.
"""),
    ("belirsiz_sureli_is_sozlesmesi.docx", """\
BELİRSİZ SÜRELİ İŞ SÖZLEŞMESİ

4857 sayılı İş Kanunu uyarınca aşağıdaki taraflar arasında düzenlenmiştir. Taraf bilgileri kurgusaldır.

MADDE 1 - TARAFLAR
İşveren: Aydın Tekstil A.Ş., Adalet Mah. Sanayi Cad. No:24, Bornova/İZMİR.
İşçi: Zeynep KAYA, T.C. No: 33333333330, Muhasebe Uzmanı.

MADDE 2 - İŞİN KONUSU
İşçi, muhasebe uzmanı unvanıyla Bornova merkez ofiste görev yapacaktır.

MADDE 3 - DENEME SÜRESİ
Sözleşme belirsiz sürelidir. İlk 2 (iki) ay deneme süresidir; bu süre içinde taraflar sözleşmeyi ihbarsız ve tazminatsız feshedebilir.

MADDE 4 - ÜCRET
Aylık brüt ücret 78.000 TL olup her ayın son iş günü banka hesabına ödenir.

MADDE 5 - ÇALIŞMA SÜRESİ
Haftalık çalışma süresi 45 saattir; Pazartesi-Cuma 08:30-18:00, bir saat ara dinlenme uygulanır.

MADDE 6 - FAZLA ÇALIŞMA
Fazla çalışma ücreti, normal saat ücretinin yüzde 50 zamlı tutarı üzerinden ödenir.

MADDE 7 - YILLIK İZİN
Yıllık ücretli izin hakkı 4857 sayılı Kanun hükümlerine göre belirlenir.

MADDE 8 - İHBAR SÜRELERİ
Fesihte İş Kanunu m.17'deki ihbar süreleri uygulanır.

MADDE 9 - GİZLİLİK
İşçi, işverene ait ticari sırları iş ilişkisi sırasında ve sonrasında süresiz olarak saklamakla yükümlüdür.

MADDE 10 - UYUŞMAZLIK
Uyuşmazlıklarda önce zorunlu arabuluculuğa başvurulur; sonuç alınamazsa İzmir İş Mahkemeleri yetkilidir.

İşbu sözleşme 01.10.2026 tarihinde imzalanmıştır.
İŞVEREN: Aydın Tekstil A.Ş.          İŞÇİ: Zeynep KAYA
"""),
    ("belirli_sureli_is_sozlesmesi.docx", """\
BELİRLİ SÜRELİ İŞ SÖZLEŞMESİ

Proje bazlı istihdam için düzenlenmiştir. Taraf bilgileri kurgusaldır.

MADDE 1 - TARAFLAR
İşveren: Marmara İnşaat ve Taahhüt A.Ş., Nilüfer/BURSA.
İşçi: Kerem AKSOY, T.C. No: 44444444440, Proje Mühendisi.

MADDE 2 - SÜRE
İşbu sözleşme, Gemlik Lojistik Merkezi projesiyle sınırlı olmak üzere 01.09.2026 - 31.08.2027 tarihleri arasında 12 ay süreyle belirli sürelidir.

MADDE 3 - GÖREV
İşçi, proje mühendisi olarak Gemlik şantiyesinde görev yapar.

MADDE 4 - ÜCRET
Aylık brüt ücret 120.000 TL'dir; her ayın 5'inde ödenir.

MADDE 5 - ÇALIŞMA DÜZENİ
Haftalık çalışma süresi 45 saattir. Şantiye koşullarına göre vardiya düzeni uygulanabilir.

MADDE 6 - FAZLA ÇALIŞMA
Fazla çalışma, saat ücretinin yüzde 50 zamlı ödenmesi suretiyle karşılanır.

MADDE 7 - KONAKLAMA
Şantiye lojmanı ve günde üç öğün yemek işverence karşılanır.

MADDE 8 - SÜRE SONU
Sözleşme, sürenin bitiminde kendiliğinden sona erer; bu nedenle ihbar tazminatı doğmaz.

MADDE 9 - UYUŞMAZLIK
Uyuşmazlıklarda zorunlu arabuluculuk sonrası Bursa İş Mahkemeleri yetkilidir.

İşbu sözleşme 20.08.2026 tarihinde imzalanmıştır.
İŞVEREN: Marmara İnşaat A.Ş.          İŞÇİ: Kerem AKSOY
"""),
    ("uzaktan_calisma_sozlesmesi.docx", """\
UZAKTAN ÇALIŞMA İŞ SÖZLEŞMESİ

4857 sayılı Kanun m.14 ve Uzaktan Çalışma Yönetmeliği uyarınca düzenlenmiştir. Taraf bilgileri kurgusaldır.

MADDE 1 - TARAFLAR
İşveren: Nova Yazılım Teknolojileri A.Ş., Maslak/İSTANBUL.
İşçi: Elif ŞAHİN, T.C. No: 55555555550, Kıdemli Yazılım Geliştirici.

MADDE 2 - ÇALIŞMA BİÇİMİ
İşçi görevini uzaktan, kendi belirleyeceği yerden yürütür. Ayda 2 (iki) gün Maslak ofisinde yüz yüze toplantıya katılım zorunludur.

MADDE 3 - ÇALIŞMA SÜRESİ
Haftalık çalışma süresi 40 saattir; 10:00-16:00 arası ortak erişilebilirlik saatleridir, kalan süre esnektir.

MADDE 4 - ÜCRET
Aylık net ücret 95.000 TL olup her ayın son iş günü ödenir.

MADDE 5 - EKİPMAN
Dizüstü bilgisayar ve gerekli yazılım lisansları işverence sağlanır; internet gideri için aylık 1.500 TL ödenek verilir.

MADDE 6 - VERİ GÜVENLİĞİ
İşçi, işveren tarafından bildirilen bilgi güvenliği politikalarına uymak ve şirket verilerini üçüncü kişilerin erişiminden korumakla yükümlüdür.

MADDE 7 - DENEME SÜRESİ
Deneme süresi 1 (bir) aydır.

MADDE 8 - GİZLİLİK VE FİKRİ HAKLAR
İş kapsamında üretilen tüm kod ve eserlerin mali hakları işverene aittir.

MADDE 9 - UYUŞMAZLIK
Zorunlu arabuluculuk sonrası İstanbul İş Mahkemeleri yetkilidir.

İşbu sözleşme 05.10.2026 tarihinde imzalanmıştır.
İŞVEREN: Nova Yazılım A.Ş.          İŞÇİ: Elif ŞAHİN
"""),
    ("gizlilik_sozlesmesi_nda.docx", """\
GİZLİLİK SÖZLEŞMESİ (NDA)

Karşılıklı gizlilik esasına dayalı olarak düzenlenmiştir. Taraf bilgileri kurgusaldır.

MADDE 1 - TARAFLAR
Açıklayan Taraf: Alfa Biyoteknoloji A.Ş., Gebze/KOCAELİ.
Alan Taraf: Beta Danışmanlık Ltd. Şti., Beşiktaş/İSTANBUL.

MADDE 2 - KONU
Taraflar arasında yürütülecek ürün geliştirme iş birliği kapsamında paylaşılacak her türlü teknik, ticari ve mali bilginin gizliliğinin korunmasıdır.

MADDE 3 - GİZLİ BİLGİ TANIMI
Yazılı, sözlü veya elektronik ortamda paylaşılan formüller, araştırma verileri, müşteri listeleri, fiyatlama bilgileri ve iş planları gizli bilgi sayılır.

MADDE 4 - İSTİSNALAR
Kamuya mal olmuş bilgiler, alan tarafça bağımsız geliştirildiği ispatlanan bilgiler ve yasal zorunlulukla açıklanan bilgiler gizlilik kapsamı dışındadır.

MADDE 5 - SÜRE
İşbu sözleşme imza tarihinden itibaren 3 (üç) yıl geçerlidir. Gizlilik yükümlülüğü, sözleşme sona erdikten sonra 5 (beş) yıl daha devam eder.

MADDE 6 - CEZAİ ŞART
Gizlilik yükümlülüğünün ihlali halinde ihlal eden taraf, diğer tarafa 500.000 TL cezai şart öder; bu bedel, doğan zararın tazminini engellemez.

MADDE 7 - İADE
Sözleşmenin sona ermesi halinde taraflar, aldıkları tüm gizli bilgi ve kopyalarını 15 gün içinde iade veya imha eder.

MADDE 8 - UYUŞMAZLIK
Uyuşmazlıklar İstanbul Tahkim Merkezi (İSTAC) Tahkim Kuralları uyarınca çözülür; tahkim yeri İstanbul, dili Türkçedir.

İşbu sözleşme 12.09.2026 tarihinde imzalanmıştır.
ALFA BİYOTEKNOLOJİ A.Ş.          BETA DANIŞMANLIK LTD. ŞTİ.
"""),
    ("hizmet_sozlesmesi_temizlik.docx", """\
HİZMET SÖZLEŞMESİ (TEMİZLİK HİZMETLERİ)

Sürekli hizmet alımına ilişkin düzenlenmiştir. Taraf bilgileri kurgusaldır.

MADDE 1 - TARAFLAR
Hizmet Veren: Pırıl Temizlik Hizmetleri Ltd. Şti., Ümraniye/İSTANBUL.
Hizmet Alan: Vadi Alışveriş Merkezi İşletmeciliği A.Ş., Sarıyer/İSTANBUL.

MADDE 2 - KONU
Vadi AVM ortak alanlarının günlük temizliği, atık toplama ve dezenfeksiyon hizmetlerinin yürütülmesidir.

MADDE 3 - PERSONEL
Hizmet Veren, sahada en az 8 (sekiz) temizlik personeli ve 1 saha şefi bulundurur. Personelin SGK ve tüm özlük yükümlülükleri Hizmet Verene aittir.

MADDE 4 - ÇALIŞMA DÜZENİ
Hizmet haftada 6 gün, 07:00-23:00 saatleri arasında iki vardiya halinde verilir.

MADDE 5 - BEDEL
Aylık hizmet bedeli 45.000 TL + KDV olup fatura tarihinden itibaren 15 gün içinde ödenir.

MADDE 6 - MALZEME
Temizlik ekipman ve sarf malzemeleri Hizmet Veren tarafından karşılanır.

MADDE 7 - DENETİM
Hizmet Alan, hizmet kalitesini her zaman denetleyebilir; yazılı bildirilen eksiklikler 48 saat içinde giderilir.

MADDE 8 - FESİH
Taraflar 1 (bir) ay önceden yazılı ihbarla sözleşmeyi feshedebilir. Eksikliklerin üç kez yazılı ihtara rağmen giderilmemesi halinde Hizmet Alan derhal fesih hakkına sahiptir.

MADDE 9 - SÜRE
Sözleşme 01.11.2026 tarihinde başlar ve 1 yıl sürelidir; itirazsız birer yıl uzar.

MADDE 10 - UYUŞMAZLIK
İstanbul Mahkemeleri ve İcra Daireleri yetkilidir.

İşbu sözleşme 20.10.2026 tarihinde imzalanmıştır.
"""),
    ("eser_sozlesmesi_web_sitesi.docx", """\
ESER SÖZLEŞMESİ (WEB SİTESİ GELİŞTİRME)

TBK eser sözleşmesi hükümlerine tabidir. Taraf bilgileri kurgusaldır.

MADDE 1 - TARAFLAR
Yüklenici: Dijital Atölye Yazılım Ltd. Şti., Karşıyaka/İZMİR.
İş Sahibi: Karaca Mobilya San. Tic. A.Ş., İnegöl/BURSA.

MADDE 2 - ESERİN KONUSU
Kurumsal web sitesi ve yönetim panelinin tasarımı, geliştirilmesi ve yayına alınması; teknik şartname sözleşmenin ekidir.

MADDE 3 - BEDEL VE ÖDEME PLANI
Toplam bedel 250.000 TL + KDV'dir. Yüzde 40'ı imzada peşin, yüzde 30'u tasarım onayında, kalan yüzde 30'u teslimde ödenir.

MADDE 4 - TESLİM SÜRESİ
Eser, sözleşme tarihinden itibaren 90 (doksan) gün içinde teslim edilir.

MADDE 5 - GECİKME CEZASI
Yükleniciden kaynaklanan gecikmelerde her gün için sözleşme bedelinin binde 5'i (yüzde 0,5) oranında ceza uygulanır; toplam ceza bedelin yüzde 10'unu aşamaz.

MADDE 6 - KAYNAK KOD
Bedelin tamamının ödenmesiyle kaynak kodun mülkiyeti ve tüm mali haklar İş Sahibine devredilir.

MADDE 7 - GARANTİ VE BAKIM
Teslimden itibaren 12 ay boyunca hatalar ücretsiz giderilir; kapsam dışı geliştirmeler saatlik 2.500 TL üzerinden ücretlendirilir.

MADDE 8 - KABUL
İş Sahibi, teslimden itibaren 10 iş günü içinde test sonuçlarını bildirir; bildirim yapılmazsa eser kabul edilmiş sayılır.

MADDE 9 - UYUŞMAZLIK
İzmir Mahkemeleri yetkilidir.

İşbu sözleşme 01.10.2026 tarihinde imzalanmıştır.
"""),
    ("arac_satis_sozlesmesi.docx", """\
İKİNCİ EL ARAÇ SATIŞ SÖZLEŞMESİ

Taraf ve araç bilgileri kurgusaldır.

MADDE 1 - TARAFLAR
Satıcı: Murat ÖZ, T.C. No: 66666666660, Çankaya/ANKARA.
Alıcı: Pelin YURT, T.C. No: 77777777770, Keçiören/ANKARA.

MADDE 2 - SATIŞA KONU ARAÇ
2022 model, 06 ABC 123 plakalı, beyaz renkli binek otomobil; şasi no kurgusal olarak XX0000000X0000000 şeklindedir; kilometresi 48.500'dür.

MADDE 3 - SATIŞ BEDELİ
Satış bedeli 1.150.000 TL'dir. 50.000 TL kapora imzada ödenmiş olup bakiye, noter devri sırasında banka blokeli çekle ödenecektir.

MADDE 4 - KAPORA
Alıcı devirden vazgeçerse kapora Satıcıda kalır; Satıcı vazgeçerse kaporayı iki katı olarak iade eder.

MADDE 5 - DEVİR
Noter devri 10 gün içinde yapılır; devir masrafları Alıcıya aittir.

MADDE 6 - AYIPTAN SORUMLULUK
Satıcı, araçta bilinen ağır kusur bulunmadığını, kilometre bilgisinin gerçek olduğunu beyan eder. Ekspertiz raporu sözleşmenin ekidir; raporda belirtilen mevcut kusurlardan Satıcı sorumlu tutulamaz.

MADDE 7 - TESLİM
Araç, devirle birlikte tüm anahtar ve belgeleriyle teslim edilir. Devir tarihine kadarki vergi, ceza ve HGS borçları Satıcıya aittir.

MADDE 8 - UYUŞMAZLIK
Ankara Mahkemeleri yetkilidir.

İşbu sözleşme 18.09.2026 tarihinde iki nüsha imzalanmıştır.
SATICI: Murat ÖZ          ALICI: Pelin YURT
"""),
    ("avukatlik_ucret_sozlesmesi.docx", """\
AVUKATLIK ÜCRET SÖZLEŞMESİ

1136 sayılı Avukatlık Kanunu uyarınca düzenlenmiştir. Taraf bilgileri kurgusaldır.

MADDE 1 - TARAFLAR
Avukat: Av. Seda YILDIRIM, Örnek Barosu sicil 00000, Konak/İZMİR.
İş Sahibi (Müvekkil): Osman ÇELİK, T.C. No: 88888888880, Buca/İZMİR.

MADDE 2 - İŞİN KONUSU
Müvekkilin taraf olduğu alacak davasının açılması ve kesinleşmesine kadar takibi.

MADDE 3 - ÜCRET
Avukatlık ücreti, 60.000 TL sabit ücret ile dava sonunda tahsil edilecek tutarın yüzde 15'i toplamıdır. Sabit ücretin yarısı imzada, kalanı davanın açılmasında ödenir.

MADDE 4 - MASRAFLAR
Harç, bilirkişi, tebligat ve sair yargılama giderleri Müvekkile aittir; avukat tarafından avans olarak talep edilebilir.

MADDE 5 - KARŞI VEKALET ÜCRETİ
Mahkemece hükmedilen karşı vekalet ücreti Avukata aittir.

MADDE 6 - AZİL VE İSTİFA
Haklı sebep olmaksızın azil halinde ücretin tamamı muaccel olur. Avukatın haklı sebeple istifasında o ana kadarki hizmet bedeli ödenir.

MADDE 7 - SÜRE
Sözleşme, davanın kesinleşmesine kadar geçerlidir; icra takibi ayrı ücrete tabidir.

MADDE 8 - UYUŞMAZLIK
İzmir Mahkemeleri yetkilidir.

İşbu sözleşme 25.09.2026 tarihinde imzalanmıştır.
AVUKAT: Av. Seda YILDIRIM          MÜVEKKİL: Osman ÇELİK
"""),
    ("kefalet_sozlesmesi.docx", """\
KEFALET SÖZLEŞMESİ (ADİ KEFALET)

TBK m.581 ve devamı hükümlerine tabidir. Taraf bilgileri kurgusaldır.

MADDE 1 - TARAFLAR
Alacaklı: Örnek Finans A.Ş., Levent/İSTANBUL.
Borçlu: Ege Ticaret Ltd. Şti., Bayraklı/İZMİR.
Kefil: Ali VURAL, T.C. No: 99999999990, Karşıyaka/İZMİR.

MADDE 2 - KEFALETİN KONUSU
Borçlunun, Alacaklı ile imzaladığı 15.09.2026 tarihli kredi sözleşmesinden doğan borçlarına adi kefalettir.

MADDE 3 - AZAMİ SORUMLULUK TUTARI
Kefilin sorumluluğu her halde 300.000 TL (üç yüz bin Türk Lirası) ile sınırlıdır. Bu tutar kefilin el yazısı ile sözleşmeye derç edilmiştir.

MADDE 4 - KEFALET SÜRESİ
Kefalet, imza tarihinden itibaren 2 (iki) yıl süreyle geçerlidir; süre sonunda kendiliğinden sona erer.

MADDE 5 - ADİ KEFALETİN NİTELİĞİ
Alacaklı, önce asıl borçluya başvurmadan ve takip yolları tüketilmeden kefile başvuramaz.

MADDE 6 - EŞ RIZASI
Kefilin eşinin yazılı rızası, TBK m.584 uyarınca sözleşmenin ekinde yer almaktadır.

MADDE 7 - BİLDİRİM
Alacaklı, borçlunun temerrüdünü 30 gün içinde kefile yazılı olarak bildirir.

MADDE 8 - UYUŞMAZLIK
İstanbul Mahkemeleri yetkilidir.

İşbu sözleşme 15.09.2026 tarihinde imzalanmıştır.
"""),
    ("franchise_sozlesmesi.docx", """\
FRANCHISE SÖZLEŞMESİ

Marka ve işletme sistemi kullandırmaya ilişkindir. Taraf bilgileri kurgusaldır.

MADDE 1 - TARAFLAR
Franchise Veren: MokaCafe Gıda İşletmeleri A.Ş., Şişli/İSTANBUL.
Franchise Alan: Yeliz Gıda Ltd. Şti., temsilen Yeliz ACAR, Beşiktaş/İSTANBUL.

MADDE 2 - KONU
MokaCafe markası ve işletme sisteminin, Beşiktaş sınırları içindeki tek şubede kullanım hakkının verilmesidir.

MADDE 3 - GİRİŞ BEDELİ
Franchise Alan, tek seferlik 1.500.000 TL + KDV giriş bedelini imzada öder; bu bedel hiçbir koşulda iade edilmez.

MADDE 4 - ROYALTİ
Franchise Alan, aylık net cirosunun yüzde 6'sını royalti olarak izleyen ayın 10'una kadar öder.

MADDE 5 - REKLAM FONU
Aylık net cironun yüzde 2'si ortak reklam fonuna ayrıca ödenir.

MADDE 6 - BÖLGE KORUMASI
Franchise Veren, sözleşme süresince Beşiktaş ilçesinde başka bir şube veya franchise açmayacaktır.

MADDE 7 - EĞİTİM VE DENETİM
Açılış öncesi 4 haftalık zorunlu eğitim Franchise Verence sağlanır. Franchise Veren, standartlara uyumu habersiz denetleyebilir.

MADDE 8 - SÜRE
Sözleşme 5 (beş) yıl sürelidir; tarafların mutabakatıyla aynı koşullarda 5 yıl uzatılabilir.

MADDE 9 - TEDARİK
Kahve çekirdeği ve ana hammaddeler yalnızca Franchise Verenin onayladığı tedarikçilerden alınır.

MADDE 10 - FESİH VE SONUÇLARI
Royalti ödemelerinin iki ay gecikmesi halinde Franchise Veren sözleşmeyi derhal feshedebilir. Fesihte marka kullanımına son verilir ve tabela 15 gün içinde söktürülür.

MADDE 11 - UYUŞMAZLIK
İstanbul Tahkim Merkezi (İSTAC) kuralları uyarınca tahkim yolu benimsenmiştir.

İşbu sözleşme 01.10.2026 tarihinde imzalanmıştır.
"""),
    ("distributorluk_sozlesmesi.docx", """\
MÜNHASIR DİSTRİBÜTÖRLÜK SÖZLEŞMESİ

Taraf bilgileri kurgusaldır.

MADDE 1 - TARAFLAR
Üretici: Anka Kozmetik San. A.Ş., Gebze/KOCAELİ.
Distribütör: Ege Pazarlama ve Dağıtım Ltd. Şti., Bornova/İZMİR.

MADDE 2 - KONU VE BÖLGE
Üreticinin cilt bakım ürünlerinin, Ege Bölgesi illerinde münhasır dağıtım hakkının Distribütöre verilmesidir.

MADDE 3 - MÜNHASIRLIK
Üretici, sözleşme bölgesinde üçüncü kişilere doğrudan veya dolaylı satış yapamaz; Distribütör de bölge dışına aktif satış yapamaz.

MADDE 4 - ASGARİ ALIM TAAHHÜDÜ
Distribütör, her sözleşme yılında en az 5.000.000 TL tutarında ürün almayı taahhüt eder. Taahhüdün yüzde 70'in altında kalması halinde Üretici münhasırlığı kaldırabilir veya sözleşmeyi feshedebilir.

MADDE 5 - FİYAT VE ÖDEME
Satışlar, Üreticinin yürürlükteki distribütör fiyat listesi üzerinden yapılır; fatura vadesi 60 gündür.

MADDE 6 - REKABET YASAĞI
Distribütör, sözleşme süresince ve sona ermesinden itibaren 1 (bir) yıl boyunca bölgede rakip markaların dağıtımını üstlenemez.

MADDE 7 - SÜRE
Sözleşme 3 (üç) yıl sürelidir; bitiminden 6 ay önce feshi ihbar edilmezse birer yıl uzar.

MADDE 8 - MARKA KULLANIMI
Distribütör, markayı yalnızca ürünlerin tanıtımı amacıyla ve Üreticinin kurumsal kimlik kurallarına uygun kullanabilir.

MADDE 9 - UYUŞMAZLIK
Kocaeli Mahkemeleri yetkilidir.

İşbu sözleşme 10.09.2026 tarihinde imzalanmıştır.
"""),
    ("odunc_karz_sozlesmesi.docx", """\
ÖDÜNÇ (KARZ) SÖZLEŞMESİ

TBK tüketim ödüncü hükümlerine tabidir. Taraf bilgileri kurgusaldır.

MADDE 1 - TARAFLAR
Ödünç Veren: Nurten AK, T.C. No: 12121212120, Üsküdar/İSTANBUL.
Ödünç Alan: Cem AK, T.C. No: 13131313130, Kartal/İSTANBUL.

MADDE 2 - ÖDÜNÇ TUTARI
Ödünç Veren, 750.000 TL'yi (yedi yüz elli bin Türk Lirası) imza tarihinde banka havalesi ile Ödünç Alana teslim etmiştir.

MADDE 3 - FAİZ
Anaparaya yıllık yüzde 30 (otuz) akdi faiz uygulanır.

MADDE 4 - GERİ ÖDEME PLANI
Borç, 18 (on sekiz) ayda, her ayın 1'inde ödenecek eşit taksitlerle geri ödenir. İlk taksit 01.11.2026 tarihindedir.

MADDE 5 - ERKEN ÖDEME
Ödünç Alan, kalan borcu her zaman erken kapatabilir; bu halde işlememiş faiz talep edilmez.

MADDE 6 - TEMERRÜT
İki taksitin üst üste ödenmemesi halinde borcun tamamı muaccel olur; muaccel tutara yıllık yüzde 48 temerrüt faizi uygulanır.

MADDE 7 - TEMİNAT
Borcun teminatı olarak Ödünç Alan, 750.000 TL bedelli bir adet emre muharrer senet vermiştir; borcun kapanmasıyla senet iade edilir.

MADDE 8 - UYUŞMAZLIK
İstanbul Anadolu Mahkemeleri ve İcra Daireleri yetkilidir.

İşbu sözleşme 01.10.2026 tarihinde iki nüsha imzalanmıştır.
"""),
    ("kat_karsiligi_insaat_sozlesmesi.docx", """\
KAT KARŞILIĞI İNŞAAT SÖZLEŞMESİ

Arsa payı karşılığı inşaat esasına dayanır. Taraf bilgileri kurgusaldır.

MADDE 1 - TARAFLAR
Arsa Sahibi: Fatma GÜNEŞ, T.C. No: 14141414140, Çekmeköy/İSTANBUL.
Yüklenici: Yapı Ustası İnşaat A.Ş., Ataşehir/İSTANBUL.

MADDE 2 - KONU
Arsa Sahibine ait Çekmeköy'deki 1.200 m² arsa üzerine, projesine uygun 24 bağımsız bölümlü konut inşaatının yapılmasıdır.

MADDE 3 - PAYLAŞIM ORANI
Bağımsız bölümlerin yüzde 45'i Arsa Sahibine, yüzde 55'i Yükleniciye aittir. Paylaşım listesi ekte belirlenmiştir.

MADDE 4 - TESLİM SÜRESİ
İnşaat, yapı ruhsatının alınmasından itibaren 30 (otuz) ay içinde iskân alınmış olarak teslim edilir.

MADDE 5 - GECİKME CEZASI
Teslimde gecikilen her ay için Yüklenici, Arsa Sahibine aylık 100.000 TL gecikme tazminatı öder.

MADDE 6 - RUHSAT VE HARÇLAR
Ruhsat, iskân ve tüm resmi harç ile giderler Yükleniciye aittir.

MADDE 7 - İNŞAAT KALİTESİ
İnşaat, ekli teknik şartnamede belirtilen birinci sınıf malzeme standartlarına uygun yapılır; şartnameden düşük malzeme kullanımı ayıp hükümlerine tabidir.

MADDE 8 - DEVİR YASAĞI
Yüklenici, kaba inşaat seviyesi tamamlanmadan kendi payına düşen bağımsız bölümleri üçüncü kişilere satamaz.

MADDE 9 - SİGORTA
İnşaat all-risk sigortası Yüklenici tarafından yaptırılır.

MADDE 10 - UYUŞMAZLIK
İstanbul Anadolu Mahkemeleri yetkilidir.

İşbu sözleşme 05.09.2026 tarihinde noter huzurunda düzenlenmiştir.
"""),
    ("adi_ortaklik_sozlesmesi.docx", """\
ADİ ORTAKLIK SÖZLEŞMESİ

TBK m.620 ve devamı hükümlerine tabidir. Taraf bilgileri kurgusaldır.

MADDE 1 - ORTAKLAR
Ortak 1: Barış TAN, T.C. No: 15151515150, Nilüfer/BURSA.
Ortak 2: Cihan ER, T.C. No: 16161616160, Osmangazi/BURSA.

MADDE 2 - KONU
Bursa'da 'Tan & Er Kahvaltı Evi' unvanıyla kafe-restoran işletilmesi amacıyla adi ortaklık kurulmuştur.

MADDE 3 - SERMAYE VE PAYLAR
Toplam sermaye 2.000.000 TL'dir. Barış TAN yüzde 60 (1.200.000 TL), Cihan ER yüzde 40 (800.000 TL) pay sahibidir.

MADDE 4 - KÂR VE ZARAR DAĞILIMI
Kâr ve zarar, sermaye payları oranında paylaşılır. Kâr dağıtımı üçer aylık dönemler halinde yapılır.

MADDE 5 - YÖNETİM VE TEMSİL
Ortaklık, iki ortağın birlikte imzasıyla temsil edilir. 50.000 TL'yi aşan harcamalar için yazılı mutabakat gerekir.

MADDE 6 - EMEK YÜKÜMLÜLÜĞÜ
Her iki ortak da işletmede fiilen çalışır; ayrıca aylık 40.000 TL huzur hakkı alır.

MADDE 7 - ORTAKLIKTAN ÇIKMA
Bir ortak, 6 (altı) ay önceden yazılı ihbarla ortaklıktan çıkabilir; payı, bağımsız değerleme ile belirlenen bedel üzerinden diğer ortağa devredilir.

MADDE 8 - REKABET YASAĞI
Ortaklar, ortaklık süresince Bursa il sınırlarında aynı konuda başka işletme açamaz.

MADDE 9 - UYUŞMAZLIK
Bursa Mahkemeleri yetkilidir.

İşbu sözleşme 15.08.2026 tarihinde imzalanmıştır.
"""),
    ("yazilim_lisans_sozlesmesi.docx", """\
YAZILIM LİSANS SÖZLEŞMESİ

Fikri mülkiyet hakları saklı kalmak üzere düzenlenmiştir. Taraf bilgileri kurgusaldır.

MADDE 1 - TARAFLAR
Lisans Veren: Bilge Yazılım A.Ş., ODTÜ Teknokent/ANKARA.
Lisans Alan: Kuzey Lojistik A.Ş., Trabzon.

MADDE 2 - LİSANSIN KONUSU
'FiloTakip Pro' filo yönetim yazılımının, Lisans Alanın kurumsal operasyonlarında kullanım hakkının verilmesidir.

MADDE 3 - LİSANS KAPSAMI
Lisans; münhasır olmayan, devredilemez nitelikte olup en fazla 50 (elli) eş zamanlı kullanıcı ile sınırlıdır. Kaynak kod lisans kapsamı dışındadır.

MADDE 4 - LİSANS BEDELİ
Yıllık lisans bedeli 200.000 TL + KDV olup her sözleşme yılının başında peşin ödenir.

MADDE 5 - GÜNCELLEME VE DESTEK
Sürüm güncellemeleri ve mesai saatleri içinde uzaktan teknik destek bedele dahildir. Yerinde destek günlük 7.500 TL olarak ayrıca ücretlendirilir.

MADDE 6 - YASAKLAR
Yazılımın kopyalanması, tersine mühendisliğe tabi tutulması, kiralanması veya üçüncü kişilere kullandırılması yasaktır.

MADDE 7 - VERİ SAHİPLİĞİ
Yazılıma girilen operasyonel verilerin mülkiyeti Lisans Alana aittir; sözleşme sonunda veriler standart formatta teslim edilir.

MADDE 8 - SÜRE VE YENİLEME
Sözleşme 1 (bir) yıllıktır; bitiminden 30 gün önce feshedilmezse aynı koşullarla yenilenir. Yenileme dönemlerinde bedel, TÜFE oranında artırılır.

MADDE 9 - SORUMLULUK SINIRI
Lisans Verenin toplam sorumluluğu, son 12 ayda ödenen lisans bedeliyle sınırlıdır.

MADDE 10 - UYUŞMAZLIK
Ankara Mahkemeleri yetkilidir.

İşbu sözleşme 01.09.2026 tarihinde imzalanmıştır.
"""),
    ("arac_kiralama_sozlesmesi.docx", """\
ARAÇ KİRALAMA SÖZLEŞMESİ

Kısa süreli araç kiralamaya ilişkindir. Taraf ve araç bilgileri kurgusaldır.

MADDE 1 - TARAFLAR
Kiralayan: Hızlı Filo Araç Kiralama A.Ş., Havalimanı Şubesi/ANTALYA.
Kiracı: Tolga ŞEN, T.C. No: 17171717170, Ehliyet No: kurgusal-000001.

MADDE 2 - ARAÇ VE SÜRE
2024 model, 07 XYZ 789 plakalı dizel binek araç, 12.10.2026 - 19.10.2026 tarihleri arasında 7 (yedi) gün süreyle kiralanmıştır.

MADDE 3 - KİRA BEDELİ
Günlük kira bedeli 4.500 TL olup toplam 31.500 TL imzada tahsil edilmiştir.

MADDE 4 - DEPOZİTO
Kiracının kredi kartından 30.000 TL provizyon bloke edilmiştir; aracın hasarsız iadesinde bloke kaldırılır.

MADDE 5 - KİLOMETRE SINIRI
Toplam kullanım 2.100 km (günlük ortalama 300 km) ile sınırlıdır; aşım halinde km başına 8 TL ek ücret alınır.

MADDE 6 - YAKIT
Araç dolu depo teslim edilmiştir; dolu depo iade edilmemesi halinde eksik yakıt bedeli yüzde 20 hizmet farkıyla tahsil edilir.

MADDE 7 - SİGORTA VE MUAFİYET
Araç kasko kapsamındadır; ancak her hasar olayında 15.000 TL'ye kadar muafiyet bedeli Kiracıya aittir. Alkollü kullanım ve kurallara aykırılık halinde sigorta koruması geçersizdir.

MADDE 8 - KULLANIM ŞARTLARI
Aracı yalnızca sözleşmede kayıtlı Kiracı kullanabilir; yurt dışına çıkarılamaz.

MADDE 9 - CEZALAR
Kira süresi içindeki trafik cezaları ve köprü/otoyol geçiş ücretleri Kiracıya aittir.

MADDE 10 - UYUŞMAZLIK
Antalya Mahkemeleri yetkilidir.

İşbu sözleşme 12.10.2026 tarihinde imzalanmıştır.
"""),
]


def build() -> None:
    try:
        from docx import Document
    except ImportError:
        sys.exit("python-docx gerekli: pip install python-docx")

    OUT_DIR.mkdir(exist_ok=True)
    for filename, text in CONTRACTS:
        doc = Document()
        for line in text.splitlines():
            doc.add_paragraph(line)
        doc.save(str(OUT_DIR / filename))
        print(f"  ✓ {filename}")
    print(f"\n{len(CONTRACTS)} sözleşme yazıldı → {OUT_DIR}")


if __name__ == "__main__":
    build()
