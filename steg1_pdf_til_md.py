import argparse
import os
import pypdf # Tidligere PyPDF2
import google.generativeai as genai
from openai import AzureOpenAI
from dotenv import load_dotenv
import pathlib # For å jobbe med filstier på en objektorientert måte

def extract_text_from_pdf(pdf_path):
    """Trekker ut all tekst fra en PDF-fil."""
    print(f"Trekker ut tekst fra: {pdf_path}...")
    try:
        with open(pdf_path, 'rb') as file:
            reader = pypdf.PdfReader(file)
            text_parts = []
            for page_num in range(len(reader.pages)):
                page = reader.pages[page_num]
                text_parts.append(page.extract_text())
            
            full_text = "\n".join(filter(None, text_parts)) # Filter(None, ...) fjerner tomme strenger
            if not full_text.strip():
                print("ADVARSEL: Ingen tekst ble trukket ut fra PDF-en. Er den bildebasert eller passordbeskyttet?")
                return None
            print(f"Tekstuthenting fullført. Antall tegn: {len(full_text)}")
            return full_text
    except FileNotFoundError:
        print(f"FEIL: Filen '{pdf_path}' ble ikke funnet.")
        return None
    except pypdf.errors.PdfReadError as e:
        print(f"FEIL: Kunne ikke lese PDF-filen '{pdf_path}'. Er den korrupt eller passordbeskyttet? Feil: {e}")
        return None
    except Exception as e:
        print(f"FEIL: En uventet feil oppstod under tekstuthenting: {e}")
        return None

def get_ai_provider():
    """Henter AI-provider fra miljøvariabler."""
    return os.getenv("AI_PROVIDER", "gemini").lower()

def convert_text_to_markdown_azure_openai(text_content):
    """Konverterer gitt tekst til Markdown ved hjelp av Azure OpenAI API."""
    print("Konverterer tekst til Markdown med Azure OpenAI...")

    # Hent konfigurasjonsvariabler
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION")

    if not all([api_key, endpoint, deployment]):
        print("FEIL: Azure OpenAI-konfigurasjonsvariabler mangler. Sjekk AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT og AZURE_OPENAI_DEPLOYMENT i .env-filen.")
        return None

    try:
        client = AzureOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version=api_version or "2024-02-01"
        )

        # Samme detaljerte prompt som for Gemini
        prompt = f"""
Du er en ekspert på å konvertere tekstinnhold, ofte fra OCR (Optical Character Recognition), til perfekt Markdown.
Din oppgave er å ta følgende tekst og formatere den som Markdown, og følge disse reglene nøye:

1.  **Nøyaktighet:** Behold all tekst nøyaktig slik den er. Ikke endre, legg til eller fjern ord med mindre det er for å korrigere åpenbare OCR-feil som er tydelig ulogiske (men vær forsiktig med dette).
2.  **Struktur:** Identifiser overskrifter (H1, H2, etc.), lister (nummererte og punktmerkede), fet tekst, kursiv tekst, og bruk passende Markdown-syntaks.
3.  **Linjeskift:**
    *   For linjeskift innad i det som ser ut som et sammenhengende avsnitt, spesielt etter korte linjer som i adresser eller metadata-blokker, bruk to mellomrom på slutten av linjen for å tvinge frem et linjeskift (`  \\n`).
    *   Bruk standard Markdown-avsnitt (en tom linje mellom avsnitt) for større tekstblokker.
4.  **Horisontale linjer:** For horisontale linjer (`---` eller `***`), sørg for at det er en tom linje *før* dem for å unngå at linjen over blir tolket som en H2-overskrift.
5.  **Kodeblokker/Sitater:** Hvis du ser noe som ligner på kode eller lengre sitater, bruk passende Markdown (f.eks. ``` for kode, > for sitater).
6.  **Tabeller:** Hvis det er tabulære data, prøv å formatere dem som Markdown-tabeller hvis mulig. Dette kan være vanskelig med ren tekst fra OCR.
7.  **Spesialtegn:** Behandle spesialtegn korrekt (f.eks. escape dem om nødvendig, men behold dem som de er hvis de er en del av innholdet).
8.  **Sideindikatorer:** Hvis du ser klare sideindikatorer som "Side X" eller lignende, kan du vurdere å lage en `---` (horisontal linje) før dem for å skille sider, men inkluder selve sideindikatoren i Markdown-outputen.

Vennligst konverter følgende tekst til Markdown:

--- START PÅ TEKST ---
{text_content}
--- SLUTT PÅ TEKST ---
"""

        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.1
        )

        markdown_output = response.choices[0].message.content

        if not markdown_output or not markdown_output.strip():
            print("ADVARSEL: Azure OpenAI returnerte tom Markdown. Sjekk prompt eller input-tekst.")
            return None

        print("Markdown-konvertering fullført.")
        return markdown_output

    except Exception as e:
        print(f"FEIL: En feil oppstod under kommunikasjon med Azure OpenAI API: {e}")
        return None

def convert_text_to_markdown_gemini(text_content, model_name="gemini-1.5-flash-latest"):
    """Konverterer gitt tekst til Markdown ved hjelp av Gemini API."""
    print(f"Konverterer tekst til Markdown med Gemini (modell: {model_name})...")
    
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("FEIL: GOOGLE_API_KEY ble ikke funnet. Sørg for at den er satt i .env-filen eller som en miljøvariabel.")
        return None

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)

        # Detaljert prompt basert på vår tidligere samtale
        prompt = f"""
Du er en ekspert på å konvertere tekstinnhold, ofte fra OCR (Optical Character Recognition), til perfekt Markdown.
Din oppgave er å ta følgende tekst og formatere den som Markdown, og følge disse reglene nøye:

1.  **Nøyaktighet:** Behold all tekst nøyaktig slik den er. Ikke endre, legg til eller fjern ord med mindre det er for å korrigere åpenbare OCR-feil som er tydelig ulogiske (men vær forsiktig med dette).
2.  **Struktur:** Identifiser overskrifter (H1, H2, etc.), lister (nummererte og punktmerkede), fet tekst, kursiv tekst, og bruk passende Markdown-syntaks.
3.  **Linjeskift:**
    *   For linjeskift innad i det som ser ut som et sammenhengende avsnitt, spesielt etter korte linjer som i adresser eller metadata-blokker, bruk to mellomrom på slutten av linjen for å tvinge frem et linjeskift (`  \\n`).
    *   Bruk standard Markdown-avsnitt (en tom linje mellom avsnitt) for større tekstblokker.
4.  **Horisontale linjer:** For horisontale linjer (`---` eller `***`), sørg for at det er en tom linje *før* dem for å unngå at linjen over blir tolket som en H2-overskrift.
5.  **Kodeblokker/Sitater:** Hvis du ser noe som ligner på kode eller lengre sitater, bruk passende Markdown (f.eks. ``` for kode, > for sitater).
6.  **Tabeller:** Hvis det er tabulære data, prøv å formatere dem som Markdown-tabeller hvis mulig. Dette kan være vanskelig med ren tekst fra OCR.
7.  **Spesialtegn:** Behandle spesialtegn korrekt (f.eks. escape dem om nødvendig, men behold dem som de er hvis de er en del av innholdet).
8.  **Sideindikatorer:** Hvis du ser klare sideindikatorer som "Side X" eller lignende, kan du vurdere å lage en `---` (horisontal linje) før dem for å skille sider, men inkluder selve sideindikatoren i Markdown-outputen.

Vennligst konverter følgende tekst til Markdown:

--- START PÅ TEKST ---
{text_content}
--- SLUTT PÅ TEKST ---
"""
        # Sikkerhetsinnstillinger kan justeres ved behov
        # Se: https://ai.google.dev/docs/safety_setting_gemini
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        
        response = model.generate_content(prompt, safety_settings=safety_settings)
        
        # Sjekk for blokkering pga. prompt eller respons
        if response.prompt_feedback and response.prompt_feedback.block_reason:
            print(f"FEIL: Prompten ble blokkert. Årsak: {response.prompt_feedback.block_reason}")
            if response.prompt_feedback.safety_ratings:
                print("Sikkerhetsvurderinger for prompt:")
                for rating in response.prompt_feedback.safety_ratings:
                    print(f"  - {rating.category}: {rating.probability}")
            return None

        # For å få tak i teksten fra responsen
        if not response.parts:
             print("FEIL: Gemini returnerte ingen deler i responsen. Responsen var:")
             try:
                 print(response) # Prøver å printe hele responsen for feilsøking
             except Exception as e_print:
                 print(f"Kunne ikke printe hele responsen: {e_print}")

             # Sjekk finish_reason for kandidater om de finnes
             if response.candidates:
                 for candidate in response.candidates:
                     print(f"  Kandidat finish_reason: {candidate.finish_reason}")
                     if candidate.safety_ratings:
                         for rating in candidate.safety_ratings:
                             print(f"    - {rating.category}: {rating.probability}")
             return None


        markdown_output = "".join(part.text for part in response.parts if hasattr(part, 'text'))

        if not markdown_output.strip():
            print("ADVARSEL: Gemini returnerte tom Markdown. Sjekk prompt eller input-tekst.")
            print("Full respons fra Gemini:")
            try:
                print(response)
            except Exception:
                pass # Hvis responsen ikke kan printes direkte
            return None
            
        print("Markdown-konvertering fullført.")
        return markdown_output

    except Exception as e:
        print(f"FEIL: En feil oppstod under kommunikasjon med Gemini API: {e}")
        return None

def convert_text_to_markdown(text_content, model_name="gemini-1.5-flash-latest"):
    """Konverterer tekst til Markdown ved å bruke den konfigurerte AI-provideren."""
    provider = get_ai_provider()

    if provider == "azure_openai":
        return convert_text_to_markdown_azure_openai(text_content)
    elif provider == "gemini":
        return convert_text_to_markdown_gemini(text_content, model_name)
    else:
        print(f"FEIL: Ukjent AI-provider '{provider}'. Bruk 'gemini' eller 'azure_openai'.")
        return None

def main():
    # Load .env from script directory first, then current directory
    script_dir_env = pathlib.Path(__file__).parent / ".env"
    current_dir_env = pathlib.Path.cwd() / ".env"

    if script_dir_env.is_file():
        load_dotenv(dotenv_path=script_dir_env, override=True)
    elif current_dir_env.is_file():
        load_dotenv(dotenv_path=current_dir_env, override=True)
    else:
        load_dotenv()  # Fallback to default behavior

    parser = argparse.ArgumentParser(description="Konverterer en PDF-fil til Markdown ved hjelp av konfigurert AI-provider.")
    parser.add_argument("pdf_filepath", help="Stien til PDF-filen som skal konverteres.")
    parser.add_argument(
        "-o", "--output", 
        help="Valgfri: Sti til output Markdown-fil. "
             "Hvis ikke gitt, lagres output som '<pdf_filnavn_uten_ending>.md' i samme mappe som PDF-en."
    )
    parser.add_argument(
        "--model", 
        default="gemini-1.5-flash-latest", 
        help="Valgfri: Gemini-modellen som skal brukes (f.eks. 'gemini-1.5-flash-latest', 'gemini-pro'). Standard: gemini-1.5-flash-latest"
    )
    parser.add_argument(
        "--stdout",
        action="store_true", # Lager en boolean flagg
        help="Valgfri: Hvis satt, printes output til konsollen (stdout) istedenfor å lagre til fil. Overstyrer -o og standard filnavn."
    )

    args = parser.parse_args()

    pdf_text = extract_text_from_pdf(args.pdf_filepath)

    if pdf_text:
        markdown_result = convert_text_to_markdown(pdf_text, model_name=args.model)
        if markdown_result:
            if args.stdout:
                print("\n--- MARKDOWN RESULTAT (STDOUT) ---")
                print(markdown_result)
                print("--- SLUTT PÅ MARKDOWN ---")
            else:
                output_filepath = args.output
                if not output_filepath:
                    # Lag standard output filnavn hvis -o ikke er gitt
                    pdf_path_obj = pathlib.Path(args.pdf_filepath)
                    # pdf_path_obj.with_suffix('.md') erstatter .pdf med .md
                    output_filepath = pdf_path_obj.with_suffix('.md')
                
                try:
                    with open(output_filepath, 'w', encoding='utf-8') as f:
                        f.write(markdown_result)
                    print(f"Markdown lagret til: {output_filepath}")
                except IOError as e:
                    print(f"FEIL: Kunne ikke skrive til filen {output_filepath}. Feil: {e}")
                    print("\nMarkdown-resultat (prøver å printe til konsoll):\n")
                    print(markdown_result)
    else:
        print("Konvertering avbrutt på grunn av feil under tekstuthenting.")

if __name__ == "__main__":
    main()