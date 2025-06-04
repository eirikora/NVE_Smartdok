# NVE Smartdok

Dette prosjektet er et eksperiment i bruk av LLM-teknologi (Gemini 2.5) for å konvertere PDF-baserte konsesjonsdokumenter til strukturerte og interaktive "NVE Smart dokumenter". Disse dokumentene beholder originalteksten, men utvider den med "tags" som inneholder NVE metadata for alle identifiserte entiteter (f.eks. elver, innsjøer, anlegg), hvor metadata hentet fra NVE sine offentlige datasett.

Ideen bak konseptet "NVE Smart dokumenter" er:

* **Mye enklere å lese for mennesker enn dårlig lesbare scanned PDF dokumenter** (søkbart og interaktivt)
* **Strukturerte dokumenter for enkel maskinell bruk** (data eksport, analyse, migrering m.m.)

---

## Innhold

* [Forutsetninger](#forutsetninger)
* [Installasjon](#installasjon)
* [Bruk](#bruk)
* [Filstruktur](#filstruktur)

---

## Forutsetninger

* Python 3.11.9 anbefales (testet versjon)
* En aktiv Google API-nøkkel for Gemini 2.5 (hent fra [aistudio.google.com](https://aistudio.google.com/prompts/new_chat))

Opprett en `.env`-fil i rotmappen med:

```env
GOOGLE_API_KEY=<din_nøkkel_her>
```

---

## Installasjon

1. **Klon/last ned repositoriet**:

```bash
git clone https://github.com/eirikora/NVE_Smartdok.git
cd NVE_Smartdok
```

2. **Opprett et virtuelt Python miljø (valgfritt, men anbefalt)**:

```bash
python -m venv venv
source venv/bin/activate       # Linux/macOS
venv\Scripts\activate          # Windows
```

3. **Installer alle nødvendige biblioteker**:

```bash
pip install -r requirements.txt
```

4. **Lag en fil i rotkataloge med navn .env og følgende innhold**:

```env
GOOGLE_API_KEY=<din_Google_API_nøkkel_hentet på aistudio.google.com>
```

---

## Bruk

### 1. Last ned NVE-data

Gå inn i `nve_data/`-mappen og kjør alle skriptene for å hente ned og lagre alle metadata om elver, innsjøer og anlegg i både .csv og .jsonl format:

```bash
cd nve_data
python lastned_nve_solkraft.py
python lastned_nve_vannkraftverk.py
python lastned_nve_varme.py
python lastned_nve_vindkraftverk.py
python lastned_nve_elvenett_del1.py
python lastned_nve_elvenett_del2.py
python lastned_nve_havvind.py
python lastned_nve_innsjøer.py
cd ..
```

### 2. Generer et Smart dokument

Kjør pipeline-skriptet fra hovedmappen med en offentlig PDF-fil hentet fra nve.no som input:

```bash
python kjør_pipeline_smartdok.py konsesjonsdok.pdf
```

Dette vil generere:

* En `.nsd`-fil (NVE Smart Dokument, tekstdokument i markdown format med <> tags for alle identifiserte entiteter og deres metadata)
* En `.html`-fil for interaktiv visning i nettleser av samme Smart-dokument


Alternativt kan du kjøre hvert steg i pipeline manuelt:
```bash
python steg1_pdf_til_md.py konsesjonsdok.pdf            # skaper markdown-fil med .md extension
python steg2_md_tagging.py konsesjonsdok.md             # skaper tagget markdown-fil med .sd extension
python steg3_identifiser_entiteter.py konsesjonsdok.sd  # skaper metadata utøkt smart dokument-fil med .nsd extension
python steg4_nsd_til_html.py konsesjonsdok.nsd          # skaper interaktiv webside med .html extension for bedre lesbarhet
```

---

## Filstruktur

```
NVE_Smartdok/
|
|-- kjør_pipeline_smartdok.py       # Hovedpipeline
|-- steg1_pdf_til_md.py             # PDF → Markdown vha Gemini LLM
|-- steg2_md_tagging.py             # Tagging av entiteter vha Gemini LLM
|-- steg3_identifiser_entiteter.py  # Matcher entitetene mot NVE-data og legger til metadata
|-- steg4_nsd_til_html.py           # HTML-visning av NVE Smart Dokumentet for enkel aksess
|-- .env                            # (din API-nøkkel spesifiseres her)
|-- requirements.txt                # Nødvendige python biblioteker
|-- nve_data/                       # Nedlastning av NVEs offentlige datasett
    |-- lastned_nve_elvenett_del1.py # Henter rådata for elver
    |-- lastned_nve_elvenett_del2.py # Trekker ut alle navngitte elver
    |-- lastned_nve_havvind.py
    |-- lastned_nve_innsjøer.py
    |-- lastned_nve_solkraft.py
    |-- lastned_nve_vannkraftverk.py
    |-- lastned_nve_varme.py
    |-- lastned_nve_vindkraftverk.py
```

---

## Lisens og status

Dette er et eksperimentelt prosjekt utviklet av [Eirik Y. Øra](https://github.com/eirikora).
Ingen garantier for at scriptene er feilfrie på dette tidspunkt.
Bidrag og forslag til forbedringer er velkomne!
