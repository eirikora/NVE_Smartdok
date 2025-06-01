#!/usr/bin/env python3
import subprocess
import argparse
import pathlib
import os
import sys
import shutil

SCRIPT_DIR = pathlib.Path(__file__).parent.resolve()
STEG1_SCRIPT = SCRIPT_DIR / "steg1_pdf_til_md.py"
STEG2_SCRIPT = SCRIPT_DIR / "steg2_md_tagging.py"
STEG3_SCRIPT = SCRIPT_DIR / "steg3_identifiser_entiteter.py"
STEG4_SCRIPT = SCRIPT_DIR / "steg4_nsd_til_html.py"

NVE_DATA_DIR_DEFAULT = SCRIPT_DIR / "nve_data" 

def run_command(command_parts, step_name, cwd_path=None):
    """Kjører en kommando, logger output, og håndterer feil."""
    print(f"--- Starter steg: {step_name} ---")
    cmd_str_parts = [str(p) for p in command_parts]
    print(f"Kommando: {' '.join(cmd_str_parts)}")
    if cwd_path:
        print(f"Kjører i mappe: {cwd_path}")
    
    try:
        process = subprocess.Popen(
            cmd_str_parts, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True,
            encoding='utf-8',
            errors='replace',
            cwd=cwd_path
        )
        stdout, stderr = process.communicate() 

        if stdout:
            print(f"Output fra {step_name}:\n{stdout.strip()}")
        if stderr:
            if process.returncode != 0:
                print(f"FEILMELDINGER fra {step_name}:\n{stderr.strip()}", file=sys.stderr)
            else:
                print(f"Info fra {step_name} (stderr):\n{stderr.strip()}")

        if process.returncode != 0:
            print(f"FEIL: {step_name} feilet med returkode {process.returncode}.", file=sys.stderr)
            sys.exit(process.returncode)
        
        print(f"--- Fullført steg: {step_name} ---\n")
        return True
        
    except FileNotFoundError:
        print(f"FEIL: Script for {step_name} ble ikke funnet: {command_parts[0]}", file=sys.stderr)
        sys.exit(1)
    except UnicodeDecodeError as ude:
        print(f"FEIL: Unicode-dekodingsfeil under kjøring av {step_name}: {ude}", file=sys.stderr)
        print("Dette indikerer vanligvis at subprosessen ikke produserte gyldig UTF-8 output.", file=sys.stderr)
        if 'stdout' in locals() and stdout: print(f"Delvis stdout (kan være korrupt):\n{stdout}", file=sys.stderr)
        if 'stderr' in locals() and stderr: print(f"Delvis stderr (kan være korrupt):\n{stderr}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"FEIL: En uventet feil oppstod under kjøring av {step_name}: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Kjører hele PDF-til-HTML konverteringspipelinen.")
    parser.add_argument("pdf_file", type=pathlib.Path, help="Sti til input PDF-fil.")
    parser.add_argument(
        "-o", "--output_html_path", 
        type=pathlib.Path, 
        help="Valgfri full sti (inkl. filnavn) for den endelige HTML-filen. "
             "Standard: samme mappe som PDF med <pdf_fil_navn>.html."
    )
    parser.add_argument(
        "--cleanup", 
        action="store_true", 
        default=False,      
        help="Slett mellomliggende filer (.md, .sd, .nsd) etter fullført pipeline."
    )
    # NYTT FLAGG: --force
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Tving kjørsel av alle steg, selv om output-filer allerede eksisterer."
    )
    parser.add_argument(
        "--nve_data_dir", 
        type=pathlib.Path, 
        default=NVE_DATA_DIR_DEFAULT,
        help=f"Sti til mappen med NVEs jsonl-datafiler. Standard: {NVE_DATA_DIR_DEFAULT}"
    )

    args = parser.parse_args()

    pdf_path_input = args.pdf_file.resolve()

    if not pdf_path_input.suffix.lower() == ".pdf":
        print(f"FEIL: Input-filen '{pdf_path_input}' må være en .pdf-fil.", file=sys.stderr)
        sys.exit(1)

    if not pdf_path_input.is_file():
        print(f"FEIL: PDF-filen '{pdf_path_input}' ble ikke funnet.", file=sys.stderr)
        sys.exit(1)

    working_dir = pdf_path_input.parent
    pdf_filename_in_working_dir = pdf_path_input.name 
    base_name = pdf_path_input.stem

    md_file_name = f"{base_name}.md"
    sd_file_name = f"{base_name}.sd"
    nsd_file_name = f"{base_name}.nsd"
    temp_html_file_name = f"{base_name}.html"

    final_html_path = args.output_html_path if args.output_html_path else working_dir / temp_html_file_name
    final_html_path = final_html_path.resolve()

    print(f"Input PDF: {pdf_path_input}")
    print(f"Arbeidsmappe for mellomfiler: {working_dir}")
    print(f"Endelig HTML vil bli lagret som: {final_html_path}")
    if args.force:
        print("Tvinger kjørsel av alle steg (--force er satt).")
    if args.cleanup:
        print(f"Mellomliggende filer vil bli slettet etter fullføring.")
    else:
        print(f"Mellomliggende filer beholdes.")
    print("-" * 30)

    md_file_path = working_dir / md_file_name
    sd_file_path = working_dir / sd_file_name
    nsd_file_path = working_dir / nsd_file_name
    temp_html_file_path = working_dir / temp_html_file_name

    # For å spore om vi faktisk kjørte steg (for cleanup-logikk hvis --force ble brukt på eksisterende filer)
    ran_steg1 = False
    ran_steg2 = False
    ran_steg3 = False
    ran_steg4 = False

    try:
        # Steg 1: PDF til MD
        if args.force or not md_file_path.is_file():
            if md_file_path.is_file() and args.force:
                print(f"Outputfil {md_file_path} eksisterer, men kjører steg 1 på nytt pga. --force.")
            cmd_steg1 = ["python", str(STEG1_SCRIPT), pdf_filename_in_working_dir]
            run_command(cmd_steg1, "PDF til Markdown", cwd_path=working_dir)
            ran_steg1 = True
        else:
            print(f"Skipper steg 1: PDF til Markdown (outputfil {md_file_path} eksisterer allerede).")
        
        if not md_file_path.is_file(): # Sjekk uansett, selv om vi skippet
             print(f"FEIL: Markdown-fil {md_file_path} ble ikke funnet eller opprettet.", file=sys.stderr)
             sys.exit(1)

        # Steg 2: MD til SD (Tagging)
        if args.force or not sd_file_path.is_file():
            if sd_file_path.is_file() and args.force:
                print(f"Outputfil {sd_file_path} eksisterer, men kjører steg 2 på nytt pga. --force.")
            cmd_steg2 = ["python", str(STEG2_SCRIPT), md_file_name]
            run_command(cmd_steg2, "Markdown Tagging (MD -> SD)", cwd_path=working_dir)
            ran_steg2 = True
        else:
            print(f"Skipper steg 2: Markdown Tagging (MD -> SD) (outputfil {sd_file_path} eksisterer allerede).")

        if not sd_file_path.is_file():
             print(f"FEIL: Smart Dokument (SD) fil {sd_file_path} ble ikke funnet eller opprettet.", file=sys.stderr)
             sys.exit(1)

        # Steg 3: SD til NSD (Berikelse)
        if args.force or not nsd_file_path.is_file():
            if nsd_file_path.is_file() and args.force:
                print(f"Outputfil {nsd_file_path} eksisterer, men kjører steg 3 på nytt pga. --force.")
            cmd_steg3 = ["python", str(STEG3_SCRIPT), sd_file_name, "--data-dir", str(args.nve_data_dir.resolve())]
            run_command(cmd_steg3, "Entitetsberikelse (SD -> NSD)", cwd_path=working_dir)
            ran_steg3 = True
        else:
            print(f"Skipper steg 3: Entitetsberikelse (SD -> NSD) (outputfil {nsd_file_path} eksisterer allerede).")

        if not nsd_file_path.is_file():
             print(f"FEIL: NVE Smart Dokument (NSD) fil {nsd_file_path} ble ikke funnet eller opprettet.", file=sys.stderr)
             sys.exit(1)

        # Steg 4: NSD til HTML (Rendring)
        # For HTML, sjekker vi mot den *endelige* filstien hvis -o er brukt.
        # Hvis --force, eller hvis den *endelige* HTML-filen ikke finnes, kjør steget.
        # Steg 4 lager alltid temp_html_file_path først.
        run_steg4_condition = args.force
        if not run_steg4_condition:
            # Hvis -o er brukt, og den filen finnes, skipper vi med mindre --force
            if args.output_html_path and final_html_path.is_file():
                print(f"Skipper steg 4: HTML Rendring (NSD -> HTML) (endelig outputfil {final_html_path} eksisterer allerede).")
            # Hvis -o ikke er brukt, og temp-filen finnes i working_dir, skipper vi.
            elif not args.output_html_path and temp_html_file_path.is_file():
                 print(f"Skipper steg 4: HTML Rendring (NSD -> HTML) (outputfil {temp_html_file_path} eksisterer allerede).")
            else: # Endelig fil finnes ikke, så vi må kjøre steg 4
                run_steg4_condition = True
        
        if run_steg4_condition:
            if final_html_path.is_file() and args.force: # Dekker tilfellet der -o er brukt, filen finnes, men vi forcer.
                print(f"Endelig outputfil {final_html_path} eksisterer, men kjører steg 4 på nytt pga. --force.")
            elif temp_html_file_path.is_file() and args.force and not args.output_html_path:
                print(f"Outputfil {temp_html_file_path} eksisterer, men kjører steg 4 på nytt pga. --force.")

            cmd_steg4 = ["python", str(STEG4_SCRIPT), nsd_file_name]
            run_command(cmd_steg4, "HTML Rendring (NSD -> HTML)", cwd_path=working_dir)
            ran_steg4 = True
        
        if not temp_html_file_path.is_file(): 
             print(f"FEIL: HTML-fil {temp_html_file_path} ble ikke opprettet av steg 4.", file=sys.stderr)
             sys.exit(1)

        if temp_html_file_path != final_html_path:
            # Flytt selv om steg4 ble skippet, hvis den midlertidige filen finnes men ikke den endelige
            if temp_html_file_path.is_file(): # Sjekk at kilden faktisk finnes
                print(f"Flytter/kopierer HTML-fil fra {temp_html_file_path} til {final_html_path}")
                try:
                    final_html_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(temp_html_file_path), str(final_html_path))
                    # Hvis vi har flyttet temp_html_file_path, og --cleanup er satt,
                    # skal den ikke slettes dobbelt (shutil.move fjerner kilden).
                except Exception as e:
                    print(f"FEIL: Kunne ikke flytte HTML-fil til {final_html_path}: {e}", file=sys.stderr)
            elif not final_html_path.is_file(): # Kilden finnes ikke, og målet finnes heller ikke
                print(f"FEIL: Endelig HTML-fil {final_html_path} ble ikke funnet, og midlertidig fil {temp_html_file_path} ble ikke opprettet/funnet for flytting.", file=sys.stderr)
                sys.exit(1)
        elif not final_html_path.is_file(): # temp_html_file_path ER final_html_path, men den finnes ikke
            print(f"FEIL: Endelig HTML-fil {final_html_path} ble ikke funnet eller opprettet.", file=sys.stderr)
            sys.exit(1)


        print("-" * 30)
        print(f"Pipeline fullført! HTML-fil generert: {final_html_path}")

    except SystemExit: 
        print("Pipeline avbrutt på grunn av feil i et av stegene.", file=sys.stderr)
    finally:
        if args.cleanup: 
            print("Utfører opprydding av mellomliggende filer...")
            # Filer som skal vurderes for sletting
            potential_intermediate_files = []
            if ran_steg1 or md_file_path.is_file(): potential_intermediate_files.append(md_file_path)
            if ran_steg2 or sd_file_path.is_file(): potential_intermediate_files.append(sd_file_path)
            if ran_steg3 or nsd_file_path.is_file(): potential_intermediate_files.append(nsd_file_path)
            
            # Hvis HTML-filen ble opprettet i working_dir og deretter flyttet (og flyttingen var vellykket),
            # så er temp_html_file_path allerede borte.
            # Hvis steg 4 kjørte og output ikke ble flyttet (final_html_path == temp_html_file_path),
            # skal den IKKE slettes her som en mellomfil.
            if ran_steg4 and temp_html_file_path.is_file() and temp_html_file_path != final_html_path:
                potential_intermediate_files.append(temp_html_file_path)
            
            for f_path in potential_intermediate_files:
                if f_path.is_file():
                    try:
                        f_path.unlink()
                        print(f"  Slettet: {f_path}")
                    except Exception as e:
                        print(f"  Kunne ikke slette {f_path}: {e}", file=sys.stderr)
        else:
            # Sjekk om noen mellomfiler ble laget for å informere brukeren
            created_intermediate_files = [f for f in [md_file_path, sd_file_path, nsd_file_path, temp_html_file_path if temp_html_file_path != final_html_path and temp_html_file_path.is_file() else None] if f and f.is_file()]
            if created_intermediate_files:
                 print("Beholder mellomliggende filer som spesifisert.")
            else:
                 print("Ingen mellomliggende filer å beholde (eller de ble ikke opprettet).")


if __name__ == "__main__":
    main()