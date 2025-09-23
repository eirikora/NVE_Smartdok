#!/usr/bin/env python3
import argparse
import pathlib
import os
import sys
import google.generativeai as genai
from openai import AzureOpenAI
from dotenv import load_dotenv # <-- Ny import

def get_ai_provider():
    """Henter AI-provider fra miljøvariabler."""
    return os.getenv("AI_PROVIDER", "gemini").lower()

def get_api_key():
    """
    Henter API-nøkkel i følgende prioriteringsrekkefølge:
    1. GOOGLE_API_KEY fra .env-fil i nåværende arbeidsmappe.
    2. GEMINI_API_KEY fra miljøvariabler.
    3. Spør brukeren.
    """
    # Prøv å laste .env-fil fra script-mappen først, deretter nåværende arbeidsmappe
    # load_dotenv() vil ikke overskrive eksisterende miljøvariabler som standard
    # Hvis .env-filen ikke finnes, skjer ingenting (ingen feil)
    script_dir_env = pathlib.Path(__file__).parent / ".env"
    current_dir_env = pathlib.Path.cwd() / ".env"

    if script_dir_env.is_file():
        load_dotenv(dotenv_path=script_dir_env, override=True) # Override for å la .env prioriteres
        # print(f"Lastet .env fra {script_dir_env}", file=sys.stderr) # For debugging
    elif current_dir_env.is_file():
        load_dotenv(dotenv_path=current_dir_env, override=True) # Override for å la .env prioriteres
        # print(f"Lastet .env fra {current_dir_env}", file=sys.stderr) # For debugging

    api_key = os.environ.get("GOOGLE_API_KEY")

    if not api_key:
        # Fallback til GEMINI_API_KEY hvis GOOGLE_API_KEY ikke er satt (f.eks. fra .env)
        api_key = os.environ.get("GEMINI_API_KEY")
        if api_key:
            print("Bruker GEMINI_API_KEY fra miljøvariabler.", file=sys.stderr)

    if not api_key:
        print("API-nøkkel ikke funnet i .env (GOOGLE_API_KEY) eller som miljøvariabel (GEMINI_API_KEY).", file=sys.stderr)
        api_key = input("Vennligst skriv inn din Google/Gemini API-nøkkel: ").strip()

    return api_key

def tag_markdown_with_azure_openai(markdown_content: str) -> str:
    """
    Bruker Azure OpenAI API til å tagge Markdown-innhold.

    Args:
        markdown_content: Innholdet i Markdown-filen som en streng.

    Returns:
        Den taggede Markdown-strengen.
    """
    # Hent konfigurasjonsvariabler
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION")

    if not all([api_key, endpoint, deployment]):
        print("FEIL: Azure OpenAI-konfigurasjonsvariabler mangler. Sjekk AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT og AZURE_OPENAI_DEPLOYMENT i .env-filen.", file=sys.stderr)
        sys.exit(1)

    try:
        client = AzureOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version=api_version or "2024-02-01"
        )

        prompt_template = """
Du er en ekspert i å identifisere viktige entiteter som elv, innsjø, kraftverk, dam, vannvei i markdown dokumenter.
Du skal returnere ALL tekst du mottar, men tagg alle entiteter med <elv navn="Storelva"> eller <kraftverk navn="Stordalen kraftverk">.

VIKTIG - Korrekte navn i tags:
- Bruk KUN egennavnet i 'navn' attributtet, IKKE entitetstypen
- RIKTIG: <dam navn="Hunderfossen"> (ikke "dam Hunderfossen")
- RIKTIG: <kraftverk navn="Luster kraftverk">
- RIKTIG: <elv navn="Fortunselva"> (ikke "elva Fortunselva")
- FEIL: <dam navn="dam Hunderfossen">, <elv navn="elva Storelva">

Eksempler:
- "Hunderfossen dam" → <dam navn="Hunderfossen"> dam
- "dam Hunderfossen" → dam <dam navn="Hunderfossen">
- "Luster kraftverk" → <kraftverk navn="Luster kraftverk">
- "kraftverket Luster" → kraftverket <kraftverk navn="Luster kraftverk">

Presiseringer:
- Vannvei er en menneskebygd vei for vann (et rør eller en kanal for å lede vann).
- Du skal bare tagge navngitte elver, innsjøer, kraftverk, dammer og vannveier som omtales i teksten.
- Innsjø kan bli omtalt som vatn eller magasin.
- Elv kan også bli omtalt som bekk eller vassdrag.
- Står det to entiteter etter hverandre skilt med / er det to tags <..>/<...>.
- Returner KUN den taggede markdown-teksten, uten noen introduksjon, forklaring eller annen tekst rundt. Ikke pakk inn svaret i ```markdown ... ```.

Her er teksten i markdown format som du skal tagge på denne måten:
--- START OF MARKDOWN CONTENT ---
{content}
--- END OF MARKDOWN CONTENT ---
"""
        prompt = prompt_template.format(content=markdown_content)

        print("Sender innhold til Azure OpenAI for tagging... Dette kan ta et øyeblikk.", file=sys.stderr)

        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.1
        )

        tagged_text = response.choices[0].message.content

        # Fjern eventuelle markdown-kodeblokker
        if tagged_text.strip().startswith("```markdown") and tagged_text.strip().endswith("```"):
            tagged_text = tagged_text.strip()[len("```markdown"):-len("```")].strip()
        elif tagged_text.strip().startswith("```") and tagged_text.strip().endswith("```"):
             tagged_text = tagged_text.strip()[len("```"):-len("```")].strip()

        return tagged_text

    except Exception as e:
        print(f"Feil under kommunikasjon med Azure OpenAI API: {e}", file=sys.stderr)
        sys.exit(1)

def tag_markdown_with_gemini(markdown_content: str, api_key: str) -> str:
    """
    Bruker Gemini API til å tagge Markdown-innhold.

    Args:
        markdown_content: Innholdet i Markdown-filen som en streng.
        api_key: Gemini API-nøkkel.

    Returns:
        Den taggede Markdown-strengen.
    """
    genai.configure(api_key=api_key)

    model = genai.GenerativeModel('gemini-1.5-flash-latest')

    prompt_template = """
Du er en ekspert i å identifisere viktige entiteter som elv, innsjø, kraftverk, dam, vannvei i markdown dokumenter.
Du skal returnere ALL tekst du mottar, men tagg alle entiteter med <elv navn="Storelva"> eller <kraftverk navn="Stordalen kraftverk">.

VIKTIG - Korrekte navn i tags:
- Bruk KUN egennavnet i 'navn' attributtet, IKKE entitetstypen
- RIKTIG: <dam navn="Hunderfossen"> (ikke "dam Hunderfossen")
- RIKTIG: <kraftverk navn="Luster kraftverk">
- RIKTIG: <elv navn="Fortunselva"> (ikke "elva Fortunselva")
- FEIL: <dam navn="dam Hunderfossen">, <elv navn="elva Storelva">

Eksempler:
- "Hunderfossen dam" → <dam navn="Hunderfossen"> dam
- "dam Hunderfossen" → dam <dam navn="Hunderfossen">
- "Luster kraftverk" → <kraftverk navn="Luster kraftverk">
- "kraftverket Luster" → kraftverket <kraftverk navn="Luster">

Presiseringer:
- Vannvei er en menneskebygd vei for vann (et rør eller en kanal for å lede vann).
- Du skal bare tagge navngitte elver, innsjøer, kraftverk, dammer og vannveier som omtales i teksten.
- Innsjø kan bli omtalt som vatn eller magasin.
- Elv kan også bli omtalt som bekk eller vassdrag.
- Står det to entiteter etter hverandre skilt med / er det to tags <..>/<...>.
- Returner KUN den taggede markdown-teksten, uten noen introduksjon, forklaring eller annen tekst rundt. Ikke pakk inn svaret i ```markdown ... ```.

Her er teksten i markdown format som du skal tagge på denne måten:
--- START OF MARKDOWN CONTENT ---
{content}
--- END OF MARKDOWN CONTENT ---
"""
    prompt = prompt_template.format(content=markdown_content)

    print("Sender innhold til Gemini for tagging... Dette kan ta et øyeblikk.", file=sys.stderr)
    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.1
            )
        )
        tagged_text = response.text
        if tagged_text.strip().startswith("```markdown") and tagged_text.strip().endswith("```"):
            tagged_text = tagged_text.strip()[len("```markdown"):-len("```")].strip()
        elif tagged_text.strip().startswith("```") and tagged_text.strip().endswith("```"):
             tagged_text = tagged_text.strip()[len("```"):-len("```")].strip()
        return tagged_text
    except Exception as e:
        print(f"Feil under kommunikasjon med Gemini API: {e}", file=sys.stderr)
        # Prøv å få mer detaljer fra responsen hvis mulig
        if 'response' in locals() and hasattr(response, 'prompt_feedback'):
            print(f"Prompt feedback: {response.prompt_feedback}", file=sys.stderr)
        if 'response' in locals() and hasattr(response, 'candidates') and response.candidates:
             for candidate in response.candidates:
                if candidate.finish_reason != genai.types.Candidate.FinishReason.STOP:
                    print(f"Kandidat avsluttet med årsak: {candidate.finish_reason.name}", file=sys.stderr)
                    if hasattr(candidate, 'safety_ratings'):
                         print(f"Sikkerhetsvurderinger: {candidate.safety_ratings}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Tagger en Markdown-fil (.md) ved hjelp av Gemini API og lagrer resultatet som en .sd-fil.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "input_file",
        type=pathlib.Path,
        help="Sti til input Markdown-fil (.md)"
    )
    parser.add_argument(
        "-o", "--output",
        type=pathlib.Path,
        help="Valgfri sti for output .sd-fil. Hvis ikke spesifisert, lages filen ved siden av input-filen med .sd-ending."
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Skriv output til stdout i stedet for en fil."
    )

    args = parser.parse_args()

    input_path: pathlib.Path = args.input_file

    if not input_path.is_file():
        print(f"Feil: Input-filen '{input_path}' ble ikke funnet.", file=sys.stderr)
        sys.exit(1)

    if input_path.suffix.lower() != ".md":
        print(f"Advarsel: Input-filen '{input_path}' har ikke .md-ending.", file=sys.stderr)

    try:
        markdown_content = input_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"Feil under lesing av filen '{input_path}': {e}", file=sys.stderr)
        sys.exit(1)

    if not markdown_content.strip():
        print(f"Filen '{input_path}' er tom eller inneholder bare mellomrom.", file=sys.stderr)
        if args.stdout:
            print("", end="")
        else:
            output_path = args.output if args.output else input_path.with_suffix(".sd")
            try:
                output_path.write_text("", encoding="utf-8")
                print(f"Tom output skrevet til '{output_path}'", file=sys.stderr)
            except Exception as e:
                print(f"Kunne ikke skrive tom output til '{output_path}': {e}", file=sys.stderr)
        sys.exit(0)

    provider = get_ai_provider()

    if provider == "azure_openai":
        tagged_content = tag_markdown_with_azure_openai(markdown_content)
    elif provider == "gemini":
        api_key = get_api_key()
        if not api_key:
            print("API-nøkkel er påkrevd for å fortsette.", file=sys.stderr)
            sys.exit(1)
        tagged_content = tag_markdown_with_gemini(markdown_content, api_key)
    else:
        print(f"FEIL: Ukjent AI-provider '{provider}'. Bruk 'gemini' eller 'azure_openai'.", file=sys.stderr)
        sys.exit(1)

    if args.stdout:
        print(tagged_content)
    else:
        output_path = args.output if args.output else input_path.with_suffix(".sd")
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(tagged_content, encoding="utf-8")
            print(f"Tagget innhold lagret til: {output_path}", file=sys.stderr)
        except Exception as e:
            print(f"Feil under skriving til output-filen '{output_path}': {e}", file=sys.stderr)
            sys.exit(1)

if __name__ == "__main__":
    main()