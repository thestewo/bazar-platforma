import os
import google.generativeai as genai
from ddgs import DDGS
from PIL import Image

def ziskaj_ai_analyzu(inzerat):
    api_key = os.getenv("GEMINI_API_KEY")
    
    # 1. Lokalizované vyhľadávanie (region 'sk-sk' a pridanie "cena v eurach")
    search_query = f"{inzerat.nazov} cena v eurach slovensko"
    web_context = ""
    
    try:
        # Region 'sk-sk' povie DuckDuckGo, aby preferoval slovenské stránky (Heureka, Nay, Alza atď.)
        with DDGS() as ddgs:
            results = list(ddgs.text(search_query, region='sk-sk', max_results=3))
            for r in results:
                web_context += f"\nZdroj: {r['title']} - {r['body']}"
    except Exception as e:
        print(f"DEBUG: Chyba DuckDuckGo: {e}")
        web_context = "Nepodarilo sa získať aktuálne slovenské dáta z webu."

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        'models/gemini-3.1-flash-lite',
        generation_config={"temperature": 0.2}
    )
    
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
       - Pri oblečení/obuvi hľadaj známky nosenia (napr. "creases" na teniskách, žmolky, stav podrážky).
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
        except:
            pass

    try:
        response = model.generate_content(content)
        return response.text
    except Exception as e:
        print(f"DEBUG: Chyba Gemini: {e}")
        return "AI analýza momentálne nie je k dispozícii."
    
def vygeneruj_skryte_tagy(inzerat):
    if not inzerat.popis or len(inzerat.popis) < 150:
        print(f"DEBUG: Popis je krátky ({len(inzerat.popis if inzerat.popis else '')} zn.), preskakujem AI tagy.")
        return ""

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return ""

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('models/gemini-3.1-flash-lite')

    prompt = f"""
    Si pomocník pre slovenský bazár. Na základe názvu "{inzerat.nazov}" a popisu vygeneruj 
    zoznam slovenských synoným a súvisiacich výrazov, ktoré by ľudia mohli hľadať.
    
    Príklad: Pre "Nike Phantom" pridaj "kopačky, futbalová obuv, lisovky, šport".
    Príklad: Pre "iPhone" pridaj "mobil, telefón, smartphone, apple".

    Popis: {inzerat.popis[:300]}
    
    Vráť IBA kľúčové slová oddelené čiarkou, nič iné.
    """

    try:
        response = model.generate_content(prompt)
        tagy = response.text.strip()
        print(f"DEBUG: AI vygenerovalo tagy: {tagy}")
        return tagy
    except Exception as e:
        print(f"DEBUG: Chyba pri generovaní tagov: {e}")
        return ""