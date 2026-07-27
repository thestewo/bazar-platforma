import os
import json
import re
from PIL import Image
from ddgs import DDGS
from google import genai
from google.genai import types

# Globálna inicializácia nového klienta (automaticky si vezme GEMINI_API_KEY z prostredia)
client = genai.Client()

def ziskaj_ai_analyzu(inzerat):
    # 1. Lokalizované vyhľadávanie
    search_query = f"{inzerat.nazov} cena v eurach slovensko"
    web_context = ""
    
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(search_query, region='sk-sk', max_results=3))
            for r in results:
                web_context += f"\nZdroj: {r['title']} - {r['body']}"
    except Exception as e:
        print(f"DEBUG: Chyba DuckDuckGo: {e}")
        web_context = "Nepodarilo sa získať aktuálne slovenské dáta z webu."

    prompt = f"""
    Si prísny analytik pre slovenský bazárový trh so špecializáciou na zberateľské predmety a nedostatkový tovar.
    Tvojou úlohou je chrániť kupujúceho, ale zároveň objektívne rozpoznať hodnotu vzácnych kúskov.

    ÚDAJE O INZERÁTE:
    - Názov: "{inzerat.nazov}"
    - Cena v inzeráte: {inzerat.cena} EUR
    - Kategória: {inzerat.kategoria.nazov if inzerat.kategoria else 'Neznáma'}
    - Popis (dôležitý pre stav): {inzerat.popis[:600]}

    DÁTA Z WEBU (Aktuálny trh v SR/EÚ):
    {web_context}

    STRUKTÚRA ODPOVEDE:
    
    1. ANALÝZA TRHU A CENY: 
       - Najprv zisti, či ide o bežne dostupný tovar alebo "vypredaný/zberateľský" (Niche/Rare) produkt.
       - Ak je tovar v obchodoch VYPREDANÝ, porovnávaj cenu {inzerat.cena} EUR s aktuálnymi "Resell" cenami na trhoch ako eBay (EÚ verzia), StockX alebo špecializované fóra.
       - Ak ide o bežný tovar, ignoruj ceny mimo SR/EÚ a porovnávaj s Alza/Heureka.
       PRI OBLEČENÍ/OBUVI: Identifikuj veľkosť z popisu. Ak ide o žiadanú veľkosť (napr. tenisky US 9-11) alebo naopak o "vypredaný size", zober to do úvahy pri hodnotení ceny.
       - Verdikt: Je cena vzhľadom na (ne)dostupnosť a stav (podľa popisu) férová?

    2. VIZUÁLNY STAV A POPIS:
       - Skontroluj fotku (reálna vs. katalógová).
       - Pri oblečení/obuvi hľadaj známky nosenia (napr. "creases" na teniskách, žmolky, stav dodgy).
       - Porovnaj popis (napr. "MISB", "nové", "použité") s cenou. Ak predajca pýta resell cenu za poškodený kus, upozorni na to.

    3. NA ČO SI DAŤ POZOR (3 body):
       - Pridaj emotikony (✅, ⚠️, ❌, ℹ️).
       - Ak ide o vzácnu vec, jeden bod venuj overeniu originality (napr. kontrola pečatí, loga na kockách, sériové čísla).

    PRAVIDLÁ:
    - Odpovedaj v slovenčine, buď profesionálny a vecný.
    - Ak v popise vidíš kľúčové slová ako "vypredané", "raritné", "zberateľské", over si toto tvrdenie v dátach z webu.
    """

    content = [prompt]
    if inzerat.obrazok:
        try:
            img = Image.open(inzerat.obrazok.path)
            content.append(img)
        except Exception as e:
            print(f"DEBUG: Nepodarilo sa otvoriť obrázok pre analýzu: {e}")

    for dodatocny in inzerat.dodatocne_obrazky.all():
        if dodatocny.obrazok:
            try:
                img_dodatocna = Image.open(dodatocny.obrazok.path)
                content.append(img_dodatocna)
            except Exception as e:
                print(f"DEBUG: Nepodarilo sa otvoriť dodatočný obrázok pre analýzu: {e}")

    try:
        # Volanie cez novú knižnicu google-genai
        response = client.models.generate_content(
            model='gemini-3.1-flash-lite',
            contents=content,
            config=types.GenerateContentConfig(temperature=0.2)
        )
        return response.text
    except Exception as e:
        print(f"DEBUG: Chyba Gemini pri analýze: {e}")
        return "AI analýza momentálne nie je k dispozícii kvôli vyčerpaniu limitov."

def vygeneruj_skryte_tagy(inzerat):
    if not inzerat.popis or len(inzerat.popis) < 150:
        print(f"DEBUG: Popis je krátky ({len(inzerat.popis if inzerat.popis else '')} zn.), preskakujem AI tagy.")
        return ""

    prompt = f"""
    Si pomocník pre slovenský bazár. Na základe názvu "{inzerat.nazov}" a popisu vygeneruj 
    zoznam slovenských synoným a súvisiacich výrazov, ktoré by ľudia mohli hľadať.
    
    Príklad: Pre "Nike Phantom" pridaj "kopačky, futbalová obuv, lisovky, šport".
    Príklad: Pre "iPhone" pridaj "mobil, telefón, smartphone, apple".

    Popis: {inzerat.popis[:300]}
    
    Vráť IBA kľúčové slová oddelené čiarkou, nič iné.
    """

    try:
        response = client.models.generate_content(
            model='gemini-3.1-flash-lite',
            contents=prompt
        )
        tagy = response.text.strip()
        print(f"DEBUG: AI vygenerovalo tagy: {tagy}")
        return tagy
    except Exception as e:
        print(f"DEBUG: Chyba pri generovaní tagov: {e}")
        return ""

# INTERNÝ BLACKLIST
LOKALNY_BLACKLIST = [
    'marihuana', 'tráva', 'piko', 'pervitín', 'kokain', 'heroin', 'extaza', 'mdma', 'drogy',
    'samopal', 'pištol', 'zbraň', 'granát', 'výbušnina', 'ak47',
    'xanax', 'neurol', 'tramal', 'fentanyl',
    'kokot', 'piča', 'jebať', 'vyjeban', 'čurák'
]

def obsahuje_zakazane_slova(text: str) -> bool:
    if not text:
        return False
    text_lower = text.lower()
    for slovo in LOKALNY_BLACKLIST:
        if slovo in text_lower:
            return True
    return False

# BACKEND MODERÁCIA
SYSTEM_PROMPT = """
Si nekompromisný automatický moderator slovenského online bazáru a chatovacieho systému "Novu". 
Tvojou úlohou je analyzovať text a priložené obrázky.

Hľadáš nasledujúci zakázaný obsah:
1. Drogy a omamné látky.
2. Zbrane, strelivo, výbušniny.
3. Podvody (Scam), phishing.
4. Vulgarizmy, urážky.
5. Iná nelegálna činnosť.

Odpovedaj STRIKTNE vo formáte JSON:
{{
  "schvalene": true/false,
  "status": "Schválený" / "Zamietnutý" / "Karanténa",
  "dovod": "Stručné zdôvodnenie v slovenčine",
  "kategoria_problemu": "drogy" / "zbrane" / "scam" / "vulgarizmy" / "ine" / "ziadna"
}}
"""

def skontroluj_obsah_cez_gemini(text: str, obrazky_list: list = None) -> dict:
    obsah_pre_gemini = [f"Text na analýzu:\n{text}"]
    
    if obrazky_list:
        for img_file in obrazky_list:
            if img_file:
                try:
                    img = Image.open(img_file)
                    obsah_pre_gemini.append(img)
                except Exception as e:
                    print(f"Chyba spracovania obrázka pre Gemini: {e}")

    try:
        response = client.models.generate_content(
            model='gemini-3.1-flash-lite',
            contents=obsah_pre_gemini,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
            ),
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Gemini API zlyhalo (Tokeny minulé alebo výpadok): {e}")
        # BEZPEČNOSTNÁ POISTKA: Ak minieš tokeny, inzerát ide automaticky do Karantény a NESCHVÁLI sa!
        return {
            "schvalene": False,
            "status": "Karanténa",
            "dovod": "Chyba systému kontroly (API nedostupné).",
            "kategoria_problemu": "ine"
        }

def hlavna_kontrola_obsahu(text: str, obrazky_list: list = None) -> dict:
    if obsahuje_zakazane_slova(text):
        return {
            "schvalene": False,
            "status": "Zamietnutý",
            "dovod": "Obsahuje slovo z interného zoznamu zakázaných výrazov.",
            "kategoria_problemu": "vulgarizmy_alebo_drogy"
        }
    
    return skontroluj_obsah_cez_gemini(text, obrazky_list)