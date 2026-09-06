"""Erisim posta kutusu izleyicisi — cevap ve BOUNCE yakalar.

NEDEN VAR
Gmail zaten "yeni mail" diye bildirim gonderiyor. Bu onu tekrarlamiyor.
Iki farkli sey yapiyor:

  1. 4.780 okunmamis mailin icinden HEDEF LISTEMIZDEN gelen cevabi ayirir
  2. GERI DONEN mailleri yakalar

Ikincisi asil mesele. Zaten bir bounce yasadik: info@qgroup.nl, 550 5.1.1,
ve bunu ancak elle bakinca gorduk. 14 mail gonderildi; ucu geri dondiyse
haberimiz yok. Bounce, hata vermeyen degil SESSIZCE olan arizadir — bu
reponun tamamiyla ayni konu.

GUVENLIK
- Kimlik bilgileri yalnizca ortam degiskeninden okunur, koda yazilmaz,
  ekrana basilmaz, log'a dusmez.
- IMAP salt-okunur acilir (readonly=True). Hicbir mail silinmez,
  tasinmaz, okundu isaretlenmez.
- Yalnizca hedef listesindeki alan adlarindan gelenler ve bounce
  bildirimleri islenir; digerlerine bakilmaz.

GMAIL ICIN
Iki adimli dogrulama acik olmali, sonra bir "uygulama sifresi" uretilir
(hesap sifresi DEGIL). Ortam degiskenleri:
    POSTA_KULLANICI = sezerkiras28@gmail.com
    POSTA_SIFRE     = uygulama sifresi (16 karakter)
"""
from __future__ import annotations

import email
import imaplib
import os
import re
import sys
from datetime import datetime, timedelta
from email.header import decode_header, make_header

import httpx

SUNUCU = os.environ.get("POSTA_SUNUCU", "imap.gmail.com")

# Gonderdigimiz maillerin gittigi alan adlari. Bu listeden gelen her sey onemli.
HEDEFLER = [
    "diqq.com", "iqstaffing.nl", "independentrecruiters.nl",
    "signify-tech.com", "signifytechnology.com",
    "talentsboutique.com", "luckyhunter.io", "emerald-technology.com",
    "appsit.com", "gap-technical.com", "gap-personnel.com",
    "technicalresources.co.uk", "questechrecruitment.com",
    "buckleyfrayne.co.uk", "georgeadamsestateagents.co.uk",
    "verohr.co.uk", "blackpointrecruitment.co.uk",
    "andersonhoare.co.uk", "seedrecruitment.com",
    "butcherlawoffice.com",
    "community.n8n.io", "discoursemail.com",   # n8n forum bildirimleri
]

# Geri donen mail imzalari. Farkli saglayicilar farkli yazar; hepsi yakalanmali.
BOUNCE_GONDEREN = re.compile(
    r"mailer-daemon|postmaster|mail delivery (subsystem|system)|"
    r"microsoftexchange|delivery status", re.I)
BOUNCE_KONU = re.compile(
    r"undeliverable|delivery (has )?failed|returned to sender|"
    r"delivery status notification|mail delivery failed|"
    r"could not be delivered|address not found", re.I)
KOD = re.compile(r"\b(5\.[0-7]\.\d|4\.[0-7]\.\d|55\d|45\d)\b")


def _coz(ham: str | None) -> str:
    if not ham:
        return ""
    try:
        return str(make_header(decode_header(ham)))
    except (UnicodeDecodeError, LookupError, ValueError):
        return ham


def telegram(mesaj: str) -> bool:
    jeton = os.environ.get("TELEGRAM_BOT_TOKEN")
    sohbet = os.environ.get("TELEGRAM_CHAT_ID")
    if not (jeton and sohbet):
        return False
    try:
        r = httpx.post(f"https://api.telegram.org/bot{jeton}/sendMessage",
                       json={"chat_id": sohbet, "text": mesaj}, timeout=20)
        return r.status_code == 200
    except httpx.HTTPError:
        return False


def main() -> None:
    gun = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    kullanici = os.environ.get("POSTA_KULLANICI")
    sifre = os.environ.get("POSTA_SIFRE")
    if not (kullanici and sifre):
        sys.exit("POSTA_KULLANICI ve POSTA_SIFRE ortam degiskenleri gerekli.\n"
                 "Gmail icin hesap sifresi DEGIL, uygulama sifresi kullan.")

    beri = (datetime.now() - timedelta(days=gun)).strftime("%d-%b-%Y")
    cevaplar, bouncelar, bakilan = [], [], 0

    try:
        m = imaplib.IMAP4_SSL(SUNUCU)
        m.login(kullanici, sifre)
    except imaplib.IMAP4.error:
        # Hata metni kimlik bilgisi icerebilir; ayrintiyi basmiyoruz.
        sys.exit("IMAP girisi basarisiz. Uygulama sifresini ve 2FA'yi kontrol et.")

    try:
        m.select("INBOX", readonly=True)          # salt okunur: hicbir sey degismez
        tip, veri = m.search(None, f'(SINCE "{beri}")')
        if tip != "OK":
            sys.exit("IMAP arama basarisiz.")
        kimlikler = veri[0].split()
        print(f"son {gun} gunde {len(kimlikler)} mail taraniyor\n")

        for kid in kimlikler:
            tip, parca = m.fetch(kid, "(BODY.PEEK[HEADER])")   # PEEK: okundu isaretlemez
            if tip != "OK" or not parca or not isinstance(parca[0], tuple):
                continue
            bakilan += 1
            basliklar = email.message_from_bytes(parca[0][1])
            gonderen = _coz(basliklar.get("From"))
            konu = _coz(basliklar.get("Subject"))
            tarih = _coz(basliklar.get("Date"))[:31]

            if BOUNCE_GONDEREN.search(gonderen) or BOUNCE_KONU.search(konu):
                bouncelar.append((tarih, gonderen, konu))
                continue
            dusuk = gonderen.lower()
            for h in HEDEFLER:
                if h in dusuk:
                    cevaplar.append((tarih, gonderen, konu, h))
                    break
    finally:
        try:
            m.close()
        except imaplib.IMAP4.error:
            pass
        m.logout()

    print(f"=== {len(cevaplar)} CEVAP · {len(bouncelar)} GERI DONEN ===\n")

    for t, g, k, h in cevaplar:
        print(f"CEVAP  [{h}]\n  {g}\n  {k}\n  {t}\n")
    for t, g, k in bouncelar:
        print(f"GERI DONDU\n  {g}\n  {k}\n  {t}\n")

    if cevaplar:
        telegram("CEVAP GELDI\n\n" + "\n\n".join(
            f"{h}\n{g}\n{k}" for _, g, k, h in cevaplar[:5]))
    if bouncelar:
        telegram("MAIL GERI DONDU\n\n" + "\n\n".join(
            f"{g}\n{k}" for _, g, k in bouncelar[:5]))

    if bakilan == 0:
        # Sessizce sifir donmek en tehlikeli sonuc: "cevap yok" diye okunur.
        print("!! HIC BASLIK OKUNAMADI. Bu 'cevap yok' DEGIL, 'kutuya "
              "bakilamadi' demek. Baglanti ya da izin sorunu olabilir.")
        telegram("POSTA IZLEYICI: hic baslik okunamadi, kontrol et.")


if __name__ == "__main__":
    main()
