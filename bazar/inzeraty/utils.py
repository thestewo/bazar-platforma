import os
import json
import re
from PIL import Image
from duckduckgo_search import DDGS
from google import genai
from google.genai import types
from google.genai.types import HarmCategory, HarmBlockThreshold

# Globálna inicializácia klienta
client = genai.Client()

# Nastavenie bezpečnostných filtrov, aby AI neodmietala spracovať fotky/text
SAFETY_SETTINGS = [
    types.SafetySetting(
        category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        threshold=HarmBlockThreshold.BLOCK_NONE,
    ),
    types.SafetySetting(
        category=HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        threshold=HarmBlockThreshold.BLOCK_NONE,
    ),
    types.SafetySetting(
        category=HarmCategory.HARM_CATEGORY_HARASSMENT,
        threshold=HarmBlockThreshold.BLOCK_NONE,
    ),
    types.SafetySetting(
        category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        threshold=HarmBlockThreshold.BLOCK_NONE,
    ),
]

def zavolaj_gemini_s_fallbackom(contents, config=None):
    """
    Bezpečne zavolá primárny alebo záložný model.
    """
    # Použijeme overené stabilné názvy modelov
    primarny_model = 'gemini-3.5-flash-lite'
    zalozny_model = 'gemini-3.1-flash-lite'

    if config is None:
        config = types.GenerateContentConfig(
            temperature=0.2,
            safety_settings=SAFETY_SETTINGS
        )
    else:
        # Pridáme safety_settings do existujúcej konfigurácie, ak tam chýbajú
        if not getattr(config, 'safety_settings', None):
            config.safety_settings = SAFETY_SETTINGS

    # 1. Pokus: Primárny model
    try:
        res = client.models.generate_content(model=primarny_model, contents=contents, config=config)
        if res and hasattr(res, 'text') and res.text:
            return res.text
    except Exception as e:
        print(f"DEBUG: Primárny model ({primarny_model}) zlyhal: {e}. Skúšam záložný...")

    # 2. Pokus: Záložný model
    try:
        res = client.models.generate_content(model=zalozny_model, contents=contents, config=config)
        if res and hasattr(res, 'text') and res.text:
            return res.text
    except Exception as e2:
        print(f"DEBUG: Aj záložný model ({zalozny_model}) zlyhal: {e2}")

    return None

def ziskaj_ai_analyzu(inzerat):
    search_query = f"{inzerat.nazov} cena v eurach slovensko"
    web_context = ""
    
    # Bezpečné získanie dát z DuckDuckGo
    try:
        with DDGS(timeout=5) as ddgs:
            results = list(ddgs.text(search_query, region='sk-sk', max_results=2))
            if results:
                for r in results:
                    web_context += f"\nZdroj: {r.get('title', '')} - {r.get('body', '')}"
            else:
                web_context = "Žiadne výsledky z vyhľadávania."
    except Exception as e:
        print(f"DEBUG: Chyba/Timeout DuckDuckGo: {e}")
        web_context = "Nepodarilo sa získať aktuálne slovenské dáta z webu."

    popis_inzeratu = inzerat.popis if inzerat.popis else "Bez popisu"

    prompt = f"""
    Si prísny analytik pre slovenský bazárový trh so špecializáciou na zberateľské predmety a nedostatkový tovar.
    Tvojou úlohou je chrániť kupujúceho, ale zároveň objektívne rozpoznať hodnotu vzácnych kúskov.

    ÚDAJE O INZERÁTE:
    - Názov: "{inzerat.nazov}"
    - Cena v inzeráte: {inzerat.cena} EUR
    - Kategória: {inzerat.kategoria.nazov if inzerat.kategoria else 'Neznáma'}
    - Popis (dôležitý pre stav): {popis_inzeratu[:600]}

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

    text_odpoved = zavolaj_gemini_s_fallbackom(
        contents=content,
        config=types.GenerateContentConfig(
            temperature=0.2,
            safety_settings=SAFETY_SETTINGS
        )
    )

    if text_odpoved:
        return text_odpoved
    
    return "AI analýza momentálne nie je k dispozícii kvôli chybe na strane modelu."

def vygeneruj_skryte_tagy(inzerat):
    popis_text = inzerat.popis if inzerat.popis else ""
    
    prompt = f"""
    Si pomocník pre slovenský bazár. Na základe názvu "{inzerat.nazov}" a popisu vygeneruj 
    zoznam slovenských synoným a súvisiacich výrazov, ktoré by ľudia mohli hľadať.
    
    Príklad: Pre "Nike Phantom" pridaj "kopačky, futbalová obuv, lisovky, šport".
    Príklad: Pre "iPhone" pridaj "mobil, telefón, smartphone, apple".

    Popis: {popis_text[:300]}
    
    Vráť IBA kľúčové slová oddelené čiarkou, nič iné.
    """

    try:
        text_odpoved = zavolaj_gemini_s_fallbackom(contents=prompt)
        if text_odpoved:
            tagy = text_odpoved.strip()
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
Si nekompromisný automatický moderátor slovenského online bazáru "Novu".
Tvojou úlohou je analyzovať text aj priložené obrázky.

PRÍSNE KONTROLUJ OBRÁZKY (OCR DETEKCIA):
- Skontroluj VŠETOK text zobrazený na obrázkoch (oblečenie, tričká, plachty, papiere).
- Ak sa na fotke nachádza akýkoľvek vulgarizmus, nadávka alebo nenávistný prejav (napr. "kokot", "píča", "jebať" a pod.), inzerát MUSÍŠ ZAMIETNUŤ!

PRÍSNE KONTROLUJ TEXT:
- Deteguj aj zamaskované vulgarizmy, skratky alebo nedokončené slová (napr. "kok", "kkt", "pč" a pod.), ak z kontextu jednoznačne vyplýva ich vulgárny význam.

Zakázaný obsah:
1. Vulgarizmy, urážky, skryté/zamaskované nadávky a vulgárny text na fotkách.
2. Drogy a omamné látky.
3. Zbrane, strelivo, výbušniny.
4. Podvody (Scam), phishing.
5. Iná nelegálna činnosť.
6. Pornografia a náznaky pornografie(všetky inzeráty čo nejako môžu naznačovat sexuálne aktivity, hračky a tak)
7. Nereálne/ilogické inzeráty(nedávajú zmysel, napríklad inzerát s názvom lopta má fotku mesiaca alebo názov nesedí s popiskom a tak)

Odpovedaj STRIKTNE vo formáte JSON:
{
  "schvalene": false,
  "status": "Zamietnutý",
  "dovod": "Inzerát obsahuje vulgarizmy v texte alebo priamo na obrázku.",
  "kategoria_problemu": "vulgarizmy"
}
"""

def skontroluj_obsah_cez_gemini(text: str, obrazky_list: list = None) -> dict:
    obsah_pre_gemini = [f"Text na analýzu:\n{text if text else 'Bez textu'}"]
    
    if obrazky_list:
        for img_file in obrazky_list:
            if img_file:
                try:
                    img = Image.open(img_file)
                    obsah_pre_gemini.append(img)
                except Exception as e:
                    print(f"Chyba spracovania obrázka pre Gemini: {e}")

    try:
        text_odpoved = zavolaj_gemini_s_fallbackom(
            contents=obsah_pre_gemini,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
            )
        )
        if text_odpoved:
            return json.loads(text_odpoved)
    except Exception as e:
        print(f"Gemini API / JSON parse zlyhalo: {e}")

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