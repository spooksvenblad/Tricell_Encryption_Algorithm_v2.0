import math
import secrets
from itertools import product

# Majini Caesar Cipher (Mod47), version 2
#   Osaltat: 'a' + styrtecken + meddelande
#   Saltat:  [block 1] + del1 + [block 2] + del2 + [block 3] + styrtecken
#   Ett saltblock är: längdtecken (ALFABET[n]) + n slumptecken

Alfabetet = [
    "a", "b", "c", "d", "e", "f", "g", "h", "i", "j",
    "k", "l", "m", "n", "o", "p", "q", "r", "s", "t",
    "u", "v", "w", "x", "y", "z", "å", "ä", "ö", " ",
    "1", "2", "3", "4", "5", "6", "7", "8", "9", "0",
    ".", ",", "!", "?", "-", "_", "@"
]
Modulo = len(Alfabetet)  # 47
JA = ["ja", "j", "yes", "y"]

# Alla kombinationer av saltplatser: 1 = början, 2 = mitten, 3 = slutet
Kombinationer = [
    ["1", "2", "3"], ["1", "3"], ["1", "2"], ["2", "3"], ["1"], ["2"], ["3"]
]

# Vanliga bokstavspar i svenska, används för att ranka kandidater
Svenska_par = [
    "er", "en", "et", "de", "an", "ar", "ti", "ng", "än", "ra", "at", "or",
    "nd", "ll", "st", "va", "ad", "me", "li", "ni", "in", "är", "ö", "på",
]


# ---------------------------------------------------------------- grundfunktioner

def kryptera_tecken(tecken, shift_steg):
    # Förskjuter ett tecken med shift_steg i vårt 47-teckens alfabet.
    tecken_lower = tecken.lower()
    if tecken_lower in Alfabetet:
        return Alfabetet[(Alfabetet.index(tecken_lower) + shift_steg) % Modulo]
    return tecken


def skifta_text(text, shift_steg):
    return "".join(kryptera_tecken(t, shift_steg) for t in text)


def okända_tecken(text):
    # Tecken som inte finns i alfabetet (skulle annars skickas okodade).
    return sorted({t for t in text.lower() if t not in Alfabetet})


def slumpa_salt(antal):
    # secrets ger kryptografiskt säkrare slump än random.
    return "".join(secrets.choice(Alfabetet) for _ in range(antal))


def styrtecken_for_skift(skift):
    # Behåller tecknet (+5 och -5 ger olika styrtecken).
    return Alfabetet[skift % Modulo]


def bokstavsandel(text):
    # Andel tecken som är bokstäver eller mellanslag (slumpsalt ligger runt 60 %).
    t = text.lower()
    if not t:
        return 0.0
    return sum(1 for x in t if x.isalpha() or x == " ") / len(t)


def svensk_poäng(text):
    # Poäng PER TECKEN: bokstavsandel + tätheten av vanliga svenska bokstavspar.
    # Poäng per tecken gör att en lång text med salt inte slår den rena texten.
    t = text.lower()
    if not t:
        return 0.0
    par = sum(t.count(p) for p in Svenska_par)
    return 100 * bokstavsandel(t) + 100 * par / len(t)


# Sannolikhetsmodell för att skilja text från salt:
#   Text är nästan bara bokstäver/mellanslag, medan slumpsalt (47 tecken) är
#   bokstäver eller mellanslag i ca 64 % av fallen.
LOG_TEXT_BOKSTAV = math.log(0.97)
LOG_TEXT_ANNAT = math.log(0.03)
LOG_SALT_BOKSTAV = math.log(30 / 47)
LOG_SALT_ANNAT = math.log(17 / 47)


def kandidat_poäng(behallet, borttaget):
    # Poäng för en tolkning: hur text-likt det behållna är + hur salt-likt det
    # bortrensade är. Det straffar falska träffar som klipper bort riktig text
    # eller lämnar kvar salt.
    poang = 0.0
    for x in behallet.lower():
        poang += LOG_TEXT_BOKSTAV if (x.isalpha() or x == " ") else LOG_TEXT_ANNAT
    for x in borttaget.lower():
        poang += LOG_SALT_BOKSTAV if (x.isalpha() or x == " ") else LOG_SALT_ANNAT
    poang += 0.5 * sum(behallet.lower().count(par) for par in Svenska_par)
    return poang


def lika_salt_bonus(salt):
    # Förhandsförväntan: salt brukar vara lika stort på alla platser (som i menyn).
    # Ger en liten bonus som hjälper vid osäkra fall. Olika mängder är tillåtna.
    return 3.0 if len(salt) > 1 and len(set(salt.values())) == 1 else 0.0


def bygg_struktur(meddelande, skift, salt_per_plats):
    # salt_per_plats: t.ex. {"1": 21, "3": 21} (tomt = inget salt)
    styr_shift = styrtecken_for_skift(skift)

    if not salt_per_plats:
        return Alfabetet[0] + styr_shift + meddelande

    block = {
        plats: Alfabetet[n] + slumpa_salt(n) for plats, n in salt_per_plats.items()
    }
    mitten_idx = len(meddelande) // 2
    del1, del2 = meddelande[:mitten_idx], meddelande[mitten_idx:]
    return (
        block.get("1", "") + del1 + block.get("2", "")
        + del2 + block.get("3", "") + styr_shift
    )


def kryptera(meddelande, skift, salt_per_plats):
    struktur = bygg_struktur(meddelande.lower(), skift, salt_per_plats)
    return struktur, skifta_text(struktur, skift)


def styrtecken_index_for_avkodning(avkod_skift):
    # Kodningsskiftet är -avkod_skift. Version 1 använde abs(skift), så både
    # (-d) % 47 och d % 47 godtas för att gamla meddelanden ska fungera.
    return {(-avkod_skift) % Modulo, avkod_skift % Modulo}


def hitta_saltade(struktur):
    # struktur: avkodad text UTAN sista styrtecknet.
    # Testar varje kombination av saltplatser och validerar att längdtecknen
    # faktiskt står på de förväntade positionerna. Salt per plats får variera.
    kandidater = []
    langd = len(struktur)
    if langd == 0:
        return kandidater

    for kombo in Kombinationer:
        if "1" in kombo:
            n1_val = [Alfabetet.index(struktur[0])] if struktur[0] in Alfabetet else []
        else:
            n1_val = [None]
        if "3" in kombo:
            n3_val = [
                n for n in range(Modulo)
                if 1 + n <= langd and struktur[-(1 + n)] == Alfabetet[n]
            ]
        else:
            n3_val = [None]
        n2_val = list(range(Modulo)) if "2" in kombo else [None]

        for n1, n2, n3 in product(n1_val, n2_val, n3_val):
            langder = {"1": n1, "2": n2, "3": n3}
            blocklangd = {p: 1 + n for p, n in langder.items() if n is not None}
            ren_langd = langd - sum(blocklangd.values())
            if ren_langd <= 0:
                continue

            start = blocklangd.get("1", 0)
            positioner = {}
            if "1" in kombo:
                positioner["1"] = 0
            if "2" in kombo:
                positioner["2"] = start + ren_langd // 2
            if "3" in kombo:
                positioner["3"] = langd - blocklangd["3"]

            # Validera positioner och saltlängder utan typvarningar från Pylance
            giltig = True
            for p, pos in positioner.items():
                n = langder.get(p)
                if pos >= len(struktur) or n is None or struktur[pos] != Alfabetet[n]:
                    giltig = False
                    break
            if not giltig:
                continue

            # Bygg rent meddelande genom att stryka blocken
            ta_bort = set()
            for p, pos in positioner.items():
                ta_bort.update(range(pos, pos + blocklangd[p]))
            ren = "".join(t for i, t in enumerate(struktur) if i not in ta_bort)
            borttaget = "".join(t for i, t in enumerate(struktur) if i in ta_bort)
            kandidater.append({
                "kombo": kombo,
                "salt": {p: n for p, n in langder.items() if n is not None},
                "meddelande": ren,
                "borttaget": borttaget,
            })
    return kandidater


def avkoda_auto(kodat):
    # Testar alla 47 skift och returnerar alla giltiga kandidater, bäst först.
    if not kodat or okända_tecken(kodat):
        return []

    resultat = []
    for d in range(Modulo):
        struktur = skifta_text(kodat, d)
        idx = styrtecken_index_for_avkodning(d)

        # Osaltat: 'a' + styrtecken + meddelande
        if len(struktur) >= 3 and struktur[0] == "a" and Alfabetet.index(struktur[1]) in idx:
            m = struktur[2:]
            resultat.append({
                "skift": d, "typ": "osaltat", "salt": {}, "meddelande": m,
                "poang": kandidat_poäng(m, struktur[:2]), "andel": bokstavsandel(m),
            })

        # Saltat: sista tecknet är styrtecknet
        if len(struktur) > 2 and Alfabetet.index(struktur[-1]) in idx:
            for k in hitta_saltade(struktur[:-1]):
                m = k["meddelande"]
                resultat.append({
                    "skift": d, "typ": "saltat", "salt": k["salt"], "meddelande": m,
                    "poang": kandidat_poäng(m, k["borttaget"] + struktur[-1])
                    + lika_salt_bonus(k["salt"]),
                    "andel": bokstavsandel(m),
                })

    resultat.sort(key=lambda r: r["poang"], reverse=True)
    return resultat


def rensa_salt_manuellt(struktur, salt_per_plats, valda_platser):
    # Struktur minus sista styrtecknet
    if not struktur:
        return "Kunde inte rensa saltet (tom struktur)."
    temp = struktur[:-1]

    # Beräkna blocklängder för varje vald plats: 1 (längdtecken) + n (salt)
    # Om salt_per_plats är en int (bakåtkompatibilitet) eller dict
    if isinstance(salt_per_plats, int):
        salt_dict = {p: salt_per_plats for p in valda_platser}
    else:
        salt_dict = salt_per_plats

    blocklangd = {p: 1 + n for p, n in salt_dict.items() if p in valda_platser}
    total_salt_tecken = sum(blocklangd.values())

    if total_salt_tecken >= len(temp):
        return "Kunde inte rensa saltet (för mycket salt jämfört med texten)."

    # För att ta bort blocken rent matematiskt utan att indexen förskjuts fel
    # när vi klipper i strängen, sorterar vi borttagningen eller bygger en ny sträng:
    ta_bort_index = set()
    
    # För att räkna ut positioner exakt som vid kryptering:
    # 1. Om plats 1 finns: den börjar på index 0 och tar blocklangd["1"] steg.
    # 2. Om plats 3 finns: den ligger i slutet av temp.
    # 3. Om plats 2 finns: den ligger i mitten av det som blir kvar.
    
    # Vi simulerar var blocken sitter i 'temp':
    nuvarande_temp = temp
    
    # Om plats 1 finns i början
    if "1" in valda_platser:
        bl1 = blocklangd["1"]
        ta_bort_index.update(range(0, bl1))

    # Om plats 3 finns i slutet
    if "3" in valda_platser:
        bl3 = blocklangd["3"]
        start_slut = len(temp) - bl3
        ta_bort_index.update(range(start_slut, len(temp)))

    # Om plats 2 finns i mitten (beräknat på resterande längd efter 1 och 3)
    if "2" in valda_platser:
        bl2 = blocklangd["2"]
        # Räkna ut var mitten är exklusive 1 och 3
        kvarvarande_indices = [i for i in range(len(temp)) if i not in ta_bort_index]
        if kvarvarande_indices:
            mitten_pos_i_kvar = len(kvarvarande_indices) // 2
            # Hitta startindex för mittenblock
            start_mitten = kvarvarande_indices[mitten_pos_i_kvar - bl2 // 2] if bl2 <= len(kvarvarande_indices) else kvarvarande_indices[0]
            # Enklare exakt mittreducering:
            mitten_idx = len(kvarvarande_indices) // 2
            # Vi markerar för borttagning kring mitten
            # Vi kan använda samma logik som i kryptering/hitta_saltade:
        
    # Använd en renare variant via enumerate:
    ren_meddelande = []
    
    # Vi kan bygga en exakt positionstabell baserat på bygg_struktur-logiken:
    # Låt oss räkna ut reell längd på meddelandet:
    ren_langd = len(temp) - total_salt_tecken
    if ren_langd <= 0:
        return "Kunde inte rensa saltet (saltet är större än hela meddelandet)."

    mitten_idx_meddelande = ren_langd // 2
    
    # Bygg upp positioner för blocken i temp
    # Vi vet att strukturen är uppbyggd som: [block1] + [del1] + [block2] + [del2] + [block3]
    # Del1 + Del2 utgör meddelandet (längd ren_langd)
    
    # Vi kan återskapa positionerna på samma sätt som i hitta_saltade:
    start1 = blocklangd.get("1", 0)
    # Om vi räknar ut var del1 och del2 hamnar:
    # Index-mappning:
    pos_1 = 0 if "1" in valda_platser else None
    
    # Vi samlar alla positioner som ska bort:
    bort = set()
    # P1
    if "1" in valda_platser:
        bort.update(range(0, blocklangd["1"]))
    
    # P3 (ligger näst sist innan styrtecknet)
    if "3" in valda_platser:
        bort.update(range(len(temp) - blocklangd["3"], len(temp)))
        
    # P2 (ligger mitt i det som blir kvar mellan P1 och P3)
    if "2" in valda_platser:
        # Delarna emellan
        kvar = [i for i in range(len(temp)) if i not in bort]
        mid_kvar = len(kvar) // 2
        bort.update(kvar[mid_kvar - blocklangd["2"] // 2 : mid_kvar - blocklangd["2"] // 2 + blocklangd["2"]])

    return "".join(t for i, t in enumerate(temp) if i not in bort)


def fråga_heltal(text, minimum=None, maximum=None):
    while True:
        try:
            v = int(input(text).replace("+", "").strip())
        except ValueError:
            print("⚠️ Skriv ett heltal.")
            continue
        if minimum is not None and v < minimum:
            print(f"⚠️ Minst {minimum}.")
        elif maximum is not None and v > maximum:
            print(f"⚠️ Högst {maximum}.")
        else:
            return v


def fråga_platser():
    while True:
        print("\nVar vill du salta? (t.ex. '1, 2, 3')")
        print("1 = I början av meddelandet")
        print("2 = I mitten av meddelandet")
        print("3 = I slutet av meddelandet")
        val_input = input("Dina val: ").strip()
        valda = sorted(set(
            p for p in val_input.replace(",", " ").split() if p in ["1", "2", "3"]
        ))
        if valda:
            return valda
        print("\n⚠️ Ogiltigt val! Välj minst en av siffrorna 1, 2 eller 3.")


def fråga_platser_avkrypt():
    while True:
        print("\nVar saltades meddelandet? (t.ex. '1, 2, 3')")
        print("1 = I början av meddelandet")
        print("2 = I mitten av meddelandet")
        print("3 = I slutet av meddelandet")
        val_input = input("Dina val: ").strip()
        valda = sorted(set(
            p for p in val_input.replace(",", " ").split() if p in ["1", "2", "3"]
        ))
        if valda:
            return valda
        print("\n⚠️ Ogiltigt val! Välj minst en av siffrorna 1, 2 eller 3.")


def kryptera_meny():
    print("\n--- KRYPTERA MEDDELANDE ---")
    meddelande = input("Skriv ditt okodade meddelande: ").lower()

    okanda = okända_tecken(meddelande)
    if okanda:
        print(f"\n⚠️ Dessa tecken finns inte i alfabetet: {okanda}")
        print("De skulle skickas okodade. Ta bort dem?")
        if input("(ja/nej): ").strip().lower() in JA:
            meddelande = "".join(t for t in meddelande if t in Alfabetet)
        else:
            print("Avbryter.")
            return

    skift = fråga_heltal("Ange förskjutning (t.ex. -1, +0 eller +27): ")

    salt_per_plats = {}
    if input("Vill du salta? (ja/nej): ").strip().lower() in JA:
        platser = fråga_platser()
        lika = input("Samma mängd salt på alla platser? (ja/nej): ").strip().lower() in JA
        if lika:
            n = fråga_heltal("Hur mycket salt (0-46)? ", 0, Modulo - 1)
            salt_per_plats = {p: n for p in platser}
        else:
            for p in platser:
                salt_per_plats[p] = fråga_heltal(
                    f"Hur mycket salt på plats {p} (0-46)? ", 0, Modulo - 1
                )

    struktur, kodat = kryptera(meddelande, skift, salt_per_plats)

    print("\n========================================")
    print(f"Klartext-struktur:   {struktur}")
    print(f"Tillämpat skift:     {skift:+d}")
    print(f"KODAT MEDDELANDE:    {kodat}")
    print("========================================")


def dekryptera_man_meny():
    print("\n--- DEKRYPTERA MEDDELANDE (MANUELL NYCKEL) ---")
    kodat = input("Klistra in det kodade meddelandet: ").lower()
    skift = fråga_heltal("\nAnge skift som ska tillämpas vid avkodning (t.ex. -17, 0 eller +9): ")

    struktur = skifta_text(kodat, skift)
    print("\n----------------------------------------")
    print(f"AVKODAD KLARTEXT-STRUKTUR: {struktur}")
    print("----------------------------------------")

    if input("Innehåller meddelandet ovan salt? (ja/nej): ").strip().lower() in JA:
        valda_platser = fråga_platser_avkrypt()
        lika = input("Samma mängd salt på alla platser? (ja/nej): ").strip().lower() in JA
        
        salt_per_plats = {}
        if lika:
            n = fråga_heltal("Hur mycket salt lades till per plats (0-46)?: ", 0, Modulo - 1)
            salt_per_plats = {p: n for p in valda_platser}
        else:
            for p in valda_platser:
                salt_per_plats[p] = fråga_heltal(
                    f"Hur mycket salt på plats {p} (0-46)?: ", 0, Modulo - 1
                )

        rensade = rensa_salt_manuellt(struktur, salt_per_plats, valda_platser)
        print(f"\nRENSAT MEDDELANDE: {rensade}")


def dekryptera_auto_meny():
    print("\n--- DEKRYPTERA MEDDELANDE (BRUTE FORCE METOD) ---")
    kodat = input("Klistra in det kodade meddelandet: ").lower()

    print("\nVälj Brute-Force metod:")
    print("1. Helautomatisk avkodning (validerar styrtecken och salt, rankar svar)")
    print("2. Semi-automatisk avkodning (listar alla 47 skift)")
    print("3. Ranka alla 47 skift efter hur svensk texten ser ut")
    val = input("Ditt val (1, 2 eller 3): ").strip()

    if val == "1":
        okanda = okända_tecken(kodat)
        if okanda:
            print(f"\n⚠️ Meddelandet innehåller tecken utanför alfabetet: {okanda}")
            return
        print("\nTestar alla 47 förskjutningar...")
        resultat = avkoda_auto(kodat)
        if not resultat:
            print("\n[!] Hittade ingen giltig struktur. Testa metod 2 eller 3.")
            print("    (Meddelandet kan ha en annan struktur än vårt standardformat.)")
            return
        for i, r in enumerate(resultat[:3], 1):
            salt = ", ".join(f"plats {p}: {n}" for p, n in r["salt"].items()) or "inget"
            print(f"\n[{i}] {r['typ'].upper()}  skift {r['skift']:+d} (= {r['skift'] - Modulo:+d})")
            print(f"    Salt:       {salt}")
            print(f"    Meddelande: {r['meddelande']}")
        if resultat[0]["andel"] < 0.85:
            print("\nOBS: Osäkert resultat. Bästa kandidaten innehåller mycket siffror/tecken,")
            print("     så meddelandet har troligen ett annat format. Prova metod 2 eller 3.")
        elif len(resultat) > 1 and resultat[0]["poang"] - resultat[1]["poang"] < 3:
            print("\nOBS: Flera liknande kandidater. Läs dem själv och välj den som ser rätt ut.")

    elif val == "2":
        print("\n=== SEMI-AUTOMATISK BRUTE FORCE-ANALYS ===")
        for d in range(Modulo):
            print(f"Skift {d:+03d} (= {d - Modulo:+03d}): {skifta_text(kodat, d)}")

    elif val == "3":
        rader = [(svensk_poäng(skifta_text(kodat, d)), d) for d in range(Modulo)]
        rader.sort(reverse=True)
        print("\n=== RANKADE KANDIDATER (mest svensk först) ===")
        for poang, d in rader[:5]:
            print(f"Skift {d:+03d} (= {d - Modulo:+03d}) poäng {poang:5.1f}: {skifta_text(kodat, d)}")
    else:
        print("\n⚠️ Ogiltigt val! Återvänder till huvudmenyn.")


def main():
    while True:
        print("\n====================")
        print("MAJINI CAESAR CIPHER")
        print("====================")
        print("TRICELL INCORPORATED")
        print("====================")
        print("1. Kryptera")
        print("2. Dekryptera Man")
        print("3. Dekryptera Auto")
        print("4. Avsluta")

        val = input("\nVälj ett alternativ (1-4): ").strip()

        if val == "1":
            kryptera_meny()
        elif val == "2":
            dekryptera_man_meny()
        elif val == "3":
            dekryptera_auto_meny()
        elif val == "4":
            print("\nHejdå!")
            break
        else:
            print("\n⚠️ Ogiltigt val! Välj en siffra mellan 1 och 4.")


if __name__ == "__main__":
    main()

# Tyrant Cyber  (Creator of this script)
# BD-1          (Groupmember)
# Silverhand    (Groupmember)

# Majini testlab
# TRICELL Incorporated