"""Firsat izleyici — yeni is ilanlarini yakalar, uygunluk puani verir, Telegram'a atar.

NEDEN VAR
Otomasyon satiyoruz ama kendi is aramamiz tamamen elle. Panoda 107 cevapli
ilanlar var; ilani acan ilk bes cevabi okur, gerisini okumaz. Kacinci sirada
oldugun, ne yazdigin kadar onemli. Uyurken de calismasi gereken is bu.

KAYNAKLAR — ikisi de olculdu ve gercekten calisiyor
  n8n Community  /c/jobs.json   · 126 alici ilani, ilan basina ortalama 10 rakip
  Freelancer.com acik API       · n8n icin 17 aktif ilan, medyan 101 teklif

PUANLAMA — tahminle degil, olcumle
126 alici ilaninin metni tarandi ve alicilarin KENDI kelimeleri sayildi:
  production %25 · maintenance %18 · reliability %17 · error handling %14
  monitoring %7 · retries %7 · broken/fix %7
  CRM %22 · randevu %20 · lead %12
Asagidaki agirliklar o olcumden geliyor. "broken/fix" en yuksek puani aliyor
cunku bizim urunumuz tam olarak o — ve panoda en az rastlanan istek o, yani
rakip de en az orada.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

import httpx

UA = "FirsatIzleyici/1.0 (+iletisim: sezerkiras28@gmail.com)"
DEPO = Path(__file__).with_name("gorulen.json")

N8N = "https://community.n8n.io"
FL = "https://www.freelancer.com/api/projects/0.1/projects/active/"

ALICI_DESENI = re.compile(r"\[?\s*(hiring|looking for|need|seeking|wanted)", re.I)

# --- puanlama ------------------------------------------------------------
# ILK SURUM BOZUKTU ve bozuklugun sekli taniciydi: 81 ilanin 21'i esigi gecti,
# yani hicbir sey elemiyordu. Iki sebep vardi.
#
# 1) Kelimeler BAGLAMSIZ esleisiyordu. "Comprehensive Shopify & Ads Management"
#    103 puan aldi cunku metninde "broken", "debug", "reliable" geciyordu.
#    Jenerik proje metninde bu kelimeler zaten bulunur. Simdi bu kelimelerin
#    otomasyon baglaminda gecmesi sart: ayni cumlede workflow/automation/n8n/
#    integration/api gecmiyorsa sayilmiyor.
#
# 2) RAKIP SAYISI puana hic girmiyordu. 278 teklifli 103 puanlik bir is,
#    5 teklifli 66 puanliktan kotudur. Uygunluk kazanma ihtimali degildir.
#    Freelancer'da olculen medyan 101 teklif; oradaki isler pratikte kapali.

BAGLAM = r"(workflow|automation|automat|n8n|zapier|make\.com|integration|api|webhook|pipeline|scenario)"


def _yakin(metin: str, desen: str, pencere: int = 120) -> bool:
    """Desen, otomasyon baglamina YAKIN mi geciyor.

    Ayni cumlede degil ama ayni komsulukta aramak yeterli: ilan metinleri
    madde madde yazildigi icin cumle siniri guvenilir degil.
    """
    for m in re.finditer(desen, metin):
        bas = max(0, m.start() - pencere)
        if re.search(BAGLAM, metin[bas:m.end() + pencere]):
            return True
    return False


GUCLU = {                      # bizim urunumuz tam olarak bu — baglam sart
    r"\bbroken\b|not working|\bfailing\b|stopped working": 30,
    r"\bdebug|troubleshoot": 25,
    r"\baudit\b|\breview\b": 20,
    r"\breliab|\bmonitor": 20,
    r"error handling|edge case|\bretr(y|ies)\b": 18,
    r"\bmaintain|\bmaintenance\b|\bretainer\b": 20,
}
ORTA = {                       # yapabiliriz, rekabet daha yuksek — baglam sart
    r"\bproduction\b": 8,
    r"\bwebhook": 8,
    r"\bcrm\b|hubspot|pipedrive|gohighlevel": 6,
    r"\bscrap|data extraction": 8,
    r"\bpostgres|\bsupabase\b": 6,
    r"\bdocumentation\b|\bhandover\b": 6,
}
ZAYIF = {                      # baglam ARANMAZ: tuzak her yerde tuzaktir
    r"\bai agent\b|\bagentic\b": -5,
    r"build from scratch|from the ground up": -5,
    # DIKKAT: burada bir zamanlar "\bintern" yaziyordu ve "internal",
    # "international", "internet" kelimelerine takiliyordu. "Infra-only n8n
    # work — PAID trial" ilani bu yuzden -30 yedi. excel/excellent hatasinin
    # aynisi. Kelime sonu da baglanmali.
    r"\bunpaid\b|\bequity\b|\bintern(ship|s)?\b": -30,
    r"\bfree\b[^.]{0,15}(trial|task|test|pilot)": -30,
}

# Ilan otomasyonla ILGILI mi. Ilgisizse hic puanlanmaz.
# Olculen hata: Hintce bir atistirmalik ilani 43 puan aldi cunku metninde
# "maintain" geciyordu ve rakibi azdi. Dusuk rekabet, alakasiz isi iyi
# firsat yapmaz — sadece kimsenin istemedigini gosterir.
#
# KELIME SINIRI. Bu oturumda ayni hatanin UCUNCU ornegi:
#   "excel"  -> "excellent"
#   "intern" -> "internal"
#   "script" -> "de-SCRIPT-ion"   <- her ilan metninde gecer, her ilani ilgili yapar
# Substring araması bir filtre degildir. Sinir konmadan yazilan her desen,
# er ya da gec kendisini iceren daha uzun bir kelimeye takilir.
ILGILI = re.compile(
    r"\bn8n\b|\bzapier\b|make\.com|integromat|\bautomat\w*|\bworkflows?\b|"
    r"\bwebhooks?\b|\bapi\b|\bintegration\b|\bpipelines?\b|\bscrap\w*|"
    r"\bcrm\b|\bopenai\b|\bgpt\b|\bllm\b|\bchatbots?\b|\bairtable\b|"
    r"\bsupabase\b|\bbots?\b|\bscript(ing|s)?\b", re.I)

# BASKA BIRININ YIGINI. "Otomasyon" kelimesi bizim yaptigimiz sey demek degil.
# Olculen hata: "SharePoint Powered Canvas App & Workflow" 99 puanla ikinci
# siraya cikti — metninde workflow, integration, api geciyordu ve rakibi azdi.
# Gercekte Microsoft Power Platform isi: Power Apps + Power Automate + SharePoint.
# Bizim yigimizla hicbir ilgisi yok. Power Automate'in "workflow"u ile n8n'in
# "workflow"u ayni kelime, farkli teknoloji.
#
# Bu ilanlar elenmez, ISARETLENIR: bir gun o tarafi ogrenmeye karar verirsek
# listede dursun. Ama simdi teklif yazmak, sahip olmadigimiz uzmanligi iddia
# etmek olur.
BASKA_YIGIN = re.compile(
    r"power ?apps|power ?automate|power ?platform|\bsharepoint\b|\bdataverse\b|"
    r"\bsalesforce (flow|apex)\b|\bmulesoft\b|\bboomi\b|\bworkato\b|"
    r"\boutsystems\b|\bmendix\b|\bappian\b|\bpega\b|\bservicenow\b|"
    r"\bwordpress\b|\bwix\b|\bsquarespace\b|\bshopify (theme|liquid)\b|"
    r"\bunity\b|\bunreal\b|\bandroid studio\b|\bswiftui\b|\bflutter\b", re.I)

# Rakip sayisi: kazanma ihtimalinin en guclu tek gostergesi.
# Freelancer'da n8n isine medyan 101 teklif geliyor; orada 1/101 olmak,
# panoda 1/5 olmakla ayni sey degil.
RAKIP_PUANI = [(5, 30), (15, 15), (30, 0), (60, -25), (120, -45), (10**9, -70)]
BUTCE = re.compile(r"[\$£€]\s?([0-9][0-9,.]{1,6})")


def rakip_puani(n: int) -> tuple[int, str]:
    for esik, puan in RAKIP_PUANI:
        if n <= esik:
            return puan, f"{puan:+d} rakip:{n}"
    return -70, f"-70 rakip:{n}"


def gorulenler() -> set[str]:
    if DEPO.exists():
        try:
            return set(json.loads(DEPO.read_text(encoding="utf-8")))
        except (ValueError, OSError):
            return set()
    return set()


def kaydet(s: set[str]) -> None:
    DEPO.write_text(json.dumps(sorted(s)), encoding="utf-8")


def puanla(baslik: str, metin: str, rakip: int) -> tuple[int, list[str]]:
    m = (baslik + " " + metin).lower()
    if not ILGILI.search(m):
        return -999, ["ilgisiz: otomasyon/entegrasyon gecmiyor"]
    yabanci = BASKA_YIGIN.search(m)
    puan, sebep = 0, []
    if yabanci:
        sebep.append(f"?? BASKA YIGIN: {yabanci.group(0)}")

    # GUCLU ve ORTA icin baglam sart; ZAYIF her yerde gecerli
    for grup, isaret, baglam_gerek in ((GUCLU, "!", True), (ORTA, "+", True),
                                       (ZAYIF, "", False)):
        for desen, agirlik in grup.items():
            varmi = _yakin(m, desen) if baglam_gerek else bool(re.search(desen, m))
            if varmi:
                puan += agirlik
                ad = desen.split("|")[0].replace(r"\b", "").strip()
                sebep.append(f"{isaret}{agirlik:+d} {ad}")

    rp, rs = rakip_puani(rakip)
    puan += rp
    sebep.append(rs)

    if yabanci:
        puan -= 45      # elemiyoruz, siranin sonuna atiyoruz
        sebep.append("-45 baska yigin")

    b = BUTCE.findall(m)
    if b:
        try:
            en = max(float(x.replace(",", "")) for x in b)
            if en >= 1000:
                puan += 15; sebep.append("+15 butce>=1000")
            elif en >= 300:
                puan += 8; sebep.append("+8 butce>=300")
            elif en < 100:
                puan -= 10; sebep.append("-10 butce<100")
        except ValueError:
            pass
    return puan, sebep


def n8n_ilanlar(c: httpx.Client) -> list[dict]:
    y = c.get(f"{N8N}/c/jobs.json")
    if y.status_code != 200:
        print(f"  !! n8n panosu HTTP {y.status_code}")
        return []
    cikti = []
    for k in y.json().get("topic_list", {}).get("topics", [])[:30]:
        if not ALICI_DESENI.search(k["title"]):
            continue
        cikti.append({"kaynak": "n8n", "id": f"n8n:{k['id']}",
                      "baslik": k["title"], "url": f"{N8N}/t/{k['id']}",
                      "rakip": max(k.get("posts_count", 1) - 1, 0)})
    return cikti


def n8n_metin(c: httpx.Client, ilan_id: str) -> str:
    y = c.get(f"{N8N}/t/{ilan_id.split(':')[1]}.json")
    if y.status_code != 200:
        return ""
    g = y.json().get("post_stream", {}).get("posts", [])
    return re.sub(r"<[^>]+>", " ", g[0].get("cooked", "")) if g else ""


def fl_ilanlar(c: httpx.Client) -> list[dict]:
    cikti, gorulen = [], set()
    for q in ("n8n", "workflow automation", "zapier", "make.com"):
        try:
            y = c.get(FL, params={"query": q, "limit": 30, "full_description": "true"})
        except httpx.HTTPError:
            continue
        if y.status_code != 200:
            print(f"  !! freelancer '{q}' HTTP {y.status_code}")
            continue
        for p in y.json().get("result", {}).get("projects", []) or []:
            if p["id"] in gorulen:
                continue
            gorulen.add(p["id"])
            b = p.get("budget") or {}
            para = (p.get("currency") or {}).get("code", "")
            cikti.append({
                "kaynak": "freelancer", "id": f"fl:{p['id']}",
                "baslik": p.get("title", ""),
                "url": f"https://www.freelancer.com/projects/{p.get('seo_url', p['id'])}",
                "rakip": (p.get("bid_stats") or {}).get("bid_count", 0),
                "metin": (p.get("description") or p.get("preview_description") or "")
                         + f" {b.get('minimum','')}-{b.get('maximum','')} {para}",
            })
        time.sleep(1.5)
    return cikti


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
    esik = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    gor = gorulenler()
    ilk_kosu = not DEPO.exists()

    with httpx.Client(headers={"User-Agent": UA}, timeout=45,
                      follow_redirects=True) as c:
        ilanlar = n8n_ilanlar(c) + fl_ilanlar(c)
        if not ilanlar:
            # Sessizce bos donmek en tehlikeli davranis: kullanici bunu
            # "yeni is yok" diye okur. Iki kaynak da bos donduyse sorun bizde.
            print("!! HIC ILAN GELMEDI — iki kaynak da bos. Bu 'is yok' DEGIL,")
            print("   'kaynaklara ulasilamadi' demek. API degismis olabilir.")
            telegram("FIRSAT IZLEYICI: iki kaynak da bos dondu. Kontrol et.")
            return
        yeni = [i for i in ilanlar if i["id"] not in gor]
        for i in yeni:
            if i["kaynak"] == "n8n":
                i["metin"] = n8n_metin(c, i["id"])
                time.sleep(1.2)

    for i in yeni:
        i["puan"], i["sebep"] = puanla(i["baslik"], i.get("metin", ""), i["rakip"])
    yeni.sort(key=lambda x: -x["puan"])

    print(f"{len(ilanlar)} ilan tarandi · {len(yeni)} yeni\n")
    gonderilen = 0
    for i in yeni:
        isaret = "***" if i["puan"] >= esik else "   "
        print(f"{isaret} {i['puan']:4} puan · {i['rakip']:3} rakip · "
              f"{i['kaynak']:11} {i['baslik'][:62]}")
        if i["sebep"]:
            print(f"            {'  '.join(i['sebep'][:5])}")
        if i["puan"] >= esik and not ilk_kosu:
            mesaj = (f"{i['puan']} PUAN · {i['rakip']} rakip · {i['kaynak']}\n\n"
                     f"{i['baslik']}\n\n{'  '.join(i['sebep'][:4])}\n\n{i['url']}")
            if telegram(mesaj):
                gonderilen += 1

    kaydet(gor | {i["id"] for i in ilanlar})

    if ilk_kosu:
        print(f"\nILK KOSU: {len(ilanlar)} ilan depoya yazildi, bildirim gonderilmedi.")
        print("Bundan sonra yalnizca YENI ilanlar bildirilir.")
    else:
        print(f"\n{gonderilen} bildirim gonderildi (esik {esik})")
    if not os.environ.get("TELEGRAM_BOT_TOKEN"):
        print("NOT: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID tanimli degil — "
              "yalnizca ekrana yazildi.")


if __name__ == "__main__":
    main()
