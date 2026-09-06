# Fırsat İzleyici

Yeni iş ilanlarını iki kaynaktan toplar, **kazanma ihtimaline** göre puanlar,
eşiği geçenleri Telegram'a atar.

```bash
py izle.py          # eşik 20 (varsayılan)
py izle.py 40       # sadece güçlü fırsatlar
```

---

## Neden var

Otomasyon satıyoruz ama kendi iş aramamız tamamen elleydi. Panoda 107 cevaplı
ilanlar var ve ilanı açan kişi ilk beş cevabı okur, gerisini okumaz.
**Kaçıncı sırada olduğun, ne yazdığın kadar önemli.**

Bu, uyurken de çalışması gereken iş.

---

## Puanlama neden böyle

### Anahtar kelimeler tahminle değil, ölçümle seçildi

126 alıcı ilanının metni tarandı ve **alıcıların kendi kelimeleri** sayıldı:

| Terim | İlanların yüzdesi |
|---|---|
| production | %25 |
| maintenance | %18 |
| reliability | %17 |
| error handling | %14 |
| monitoring · retries · broken/fix | %7 |

`broken` ve `debug` en yüksek puanı alıyor çünkü sattığımız şey tam olarak o —
ve panoda **en az rastlanan** istek o, yani rakip de en az orada.

### Rakip sayısı puanın parçası

İlk sürümde değildi ve sonuç kullanılamazdı: 81 ilanın 21'i eşiği geçti, yani
hiçbir şey elemiyordu. 278 teklifli 103 puanlık bir iş, 5 teklifli 66 puanlıktan
**kötüdür.** Uygunluk, kazanma ihtimali değildir.

| Rakip | Puan |
|---|---|
| ≤5 | +30 |
| ≤15 | +15 |
| ≤30 | 0 |
| ≤60 | −25 |
| ≤120 | −45 |
| 120+ | −70 |

Ölçüldü: Freelancer.com'da bir n8n işine **medyan 101 teklif** geliyor. Orada
1/101 olmak, panoda 1/5 olmakla aynı şey değil.

---

## Bulunan ve düzeltilen üç hata

Hepsi çıktıyı gözle okurken çıktı. Üçü de aynı aileden.

### 1 · Bağlamsız kelime eşleşmesi

`Comprehensive Shopify & Ads Management` **103 puan** aldı — metninde "broken",
"debug", "reliable" geçtiği için. Jenerik proje metninde bu kelimeler zaten
bulunur.

Düzeltme: güçlü terimlerin **otomasyon bağlamına yakın** geçmesi şart
(`workflow|automation|n8n|integration|api|webhook|pipeline`, ±120 karakter).

### 2 · `intern` → `internal`

`[HIRING] Infra-only n8n work — **paid trial**` ilanı `-30 unpaid` cezası yedi.
Desen `\bintern` yazılmıştı, "internal" kelimesine takılıyordu. Ücretli bir işi
ücretsiz sanıp eledi.

### 3 · `script` → `de-SCRIPT-ion`

İlgisiz ilanları eleyen filtrede `script` vardı. **Her ilan metninde
"description" geçer**, dolayısıyla filtre hiçbir şey elemiyordu. Hintçe bir
atıştırmalık ilanı 43 puanla listeye girdi.

> Substring araması bir filtre değildir. Sınır konmadan yazılan her desen, er ya
> da geç kendisini içeren daha uzun bir kelimeye takılır.

---

## Kaynaklar

| Kaynak | Erişim | Ölçülen |
|---|---|---|
| n8n Community `/c/jobs.json` | Açık JSON, robots izinli | 126 alıcı ilanı · ilan başına ~10 rakip |
| Freelancer.com açık API | Anahtarsız | n8n için 17 aktif ilan · **medyan 101 teklif** |

### Ölçülüp elenenler

| Kaynak | Neden |
|---|---|
| **Fiverr** | **18.000+ n8n gigi**, medyan €73, üst satıcılarda 309 yorum. Sıfır yorumla görünmezsin |
| Make Community | "Hire a Pro" kategorisinde **2 konu** |
| Upwork | 403 · hesap zaten kullanılamıyor |
| Reddit | 403 |

Yeni kaynak eklenmeden önce ölçülür. Yıldız vermek ölçmek değildir.

---

## Sessiz başarısızlık

İki kaynak da boş dönerse betik bunu **"iş yok" diye yorumlamaz.** Ekrana ve
Telegram'a "kaynaklara ulaşılamadı, kontrol et" yazar.

Bir izleme aracının en tehlikeli davranışı, bulamadığında sessiz kalmaktır —
kullanıcı boş listeyi "ortalık sakin" diye okur.

İlk koşuda hiç bildirim gönderilmez; mevcut ilanlar depoya yazılır. Bildirim
yalnızca **yeni** ilanlar için gider.

---

## Kurulum

```bash
pip install httpx
```

Telegram için iki ortam değişkeni:

```
TELEGRAM_BOT_TOKEN   BotFather'dan alınır
TELEGRAM_CHAT_ID     kendi sohbet kimliğin
```

Tanımlı değilse betik çalışır, yalnızca ekrana yazar.

### Windows'ta zamanlanmış çalıştırma

```powershell
schtasks /create /tn "FirsatIzleyici" /tr "py C:\...\firsat-izleyici\izle.py 30" /sc hourly
```

---

## Bilinen sınırlar

- **Puanlama kelime tabanlı.** İlanın niyetini anlamıyor, kelimelerini sayıyor.
  Yanlış pozitif kalır; o yüzden her satırın yanında **puanın gerekçesi** yazılı.
- Freelancer'ın teklif sayısı anlık; ilan yeniyse düşük görünüp hızla artabilir.
- n8n panosunda "rakip" = konudaki cevap sayısı. Bazı cevaplar soru olabilir.
- İlanı yorumlamaz, sıraya koyar. **Karar insanda.**

---

## `posta.py` — cevap ve bounce izleyici

Gmail zaten "yeni mail" bildirimi gönderiyor. Bu onu tekrarlamıyor, iki farklı
şey yapıyor:

| Sorun | Gmail çözüyor mu |
|---|---|
| Birisi cevap verdi | ✅ |
| **4.780 okunmamışın içinde 14 hedefimizden biri mi** | ❌ |
| **Mail geri döndü mü** | ❌ — sessizce olur |

İkincisi asıl mesele. Zaten bir bounce yaşandı — `info@qgroup.nl`, 550 5.1.1 —
ve ancak elle bakınca görüldü. **Bounce, hata veren değil sessizce olan
arızadır**; bu reponun tamamıyla aynı konu.

### Güvenlik

- Kimlik bilgileri yalnızca ortam değişkeninden okunur. Koda yazılmaz, ekrana
  basılmaz, log'a düşmez. IMAP giriş hatası bile ayrıntısız basılır çünkü hata
  metni kimlik bilgisi içerebilir.
- IMAP **salt-okunur** açılır (`readonly=True`) ve başlıklar `BODY.PEEK` ile
  çekilir: hiçbir mail silinmez, taşınmaz, okundu işaretlenmez.
- Yalnızca hedef listesindeki alan adlarından gelenler ve bounce bildirimleri
  işlenir. Diğer maillerin içeriğine bakılmaz.

### Gmail kurulumu

İki adımlı doğrulama açık olmalı, sonra **uygulama şifresi** üretilir —
hesap şifresi değil.

```powershell
setx POSTA_KULLANICI "sezerkiras28@gmail.com"
setx POSTA_SIFRE     "<16 karakterlik uygulama sifresi>"
```

### Neden müşteriye satılmıyor

Müşterinin posta kutusuna erişim tutmak, onun kimlik bilgilerini saklamak
demek. Sıfır referanslı tek kişilik bir operasyon için bu ciddi bir sorumluluk
ve KVKK/GDPR yükü. Önce kendimize kuruyoruz; çalıştığını gösterdikten sonra
satmak konuşulur.
