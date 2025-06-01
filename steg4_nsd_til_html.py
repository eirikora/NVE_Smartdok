#!/usr/bin/env python3
import argparse
import pathlib
import sys
import re
import html # For html.escape

def escape_attr(value):
    return html.escape(str(value), quote=True)

def parse_custom_tag(match_obj): # Antar at denne er definert og fungerer
    tag_type = match_obj.group(1)
    all_attributes_str = match_obj.group(2)
    attributes = {}
    attr_regex = r'([\w_:-]+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s>]+))'
    for attr_match in re.finditer(attr_regex, all_attributes_str):
        key = attr_match.group(1)
        value = next(g for g in attr_match.groups()[1:] if g is not None)
        attributes[key] = value
    display_name = attributes.get("navn", "Ukjent Navn")
    metadata_table_rows = []
    key_display_order = {
        "navn": "Navn",
        "id": "ID", "eier": "Eier", "kommune": "Kommune", "status": "Status", 
        "ytelse_MW": "Ytelse (MW)", "vassdragsNr": "Vassdragsnr.", 
        "magasinNr": "Magasinnr.", "areal_km2": "Areal (km²)", 
        "center_lat": "Latitude", "center_lon": "Longitude",
        "lat": "Latitude", "lon": "Longitude",
    }
    type_to_display = ""
    if 'type' in attributes: # Sjekk om 'type' attributt finnes
        type_to_display = attributes['type'].capitalize()
    # Hvis ikke 'type' attributt, bruk tag_type (men sjekk om det allerede er lagt til for å unngå duplikat)
    # Dette bør ideelt sett håndteres bedre slik at "Type" bare legges til én gang.
    # For nå, la oss anta at key_display_order ikke har "type" hvis vi vil at tag_type skal brukes.
    # Eller, vi kan ha en logikk som:
    final_type_value = attributes.get('type', tag_type).capitalize()
    metadata_table_rows.append(f"<tr><td>Type</td><td>{escape_attr(final_type_value)}</td></tr>")


    for key, display_text in key_display_order.items():
        if key == 'type': continue # Allerede håndtert
        if key in attributes and attributes[key] is not None and str(attributes[key]).strip() != "":
            value = attributes[key]
            if key in ["center_lat", "lat"] and ("center_lon" in attributes or "lon" in attributes):
                continue
            if key in ["center_lon", "lon"] and ("center_lat" in attributes or "lat" in attributes):
                lat_key_to_use = "center_lat" if "center_lat" in attributes else "lat"
                lon_key_to_use = "center_lon" if "center_lon" in attributes else "lon"
                lat_val = attributes.get(lat_key_to_use)
                lon_val = attributes.get(lon_key_to_use)
                if lat_val and lon_val:
                    try: 
                        float(lat_val); float(lon_val)
                        metadata_table_rows.append(f"<tr><td>Posisjon</td><td>Lat: {escape_attr(lat_val)}, Lon: {escape_attr(lon_val)}</td></tr>")
                    except ValueError: pass 
                continue
            metadata_table_rows.append(f"<tr><td>{escape_attr(display_text)}</td><td>{escape_attr(value)}</td></tr>")
    gmaps_link = ""
    lat_val_for_map = attributes.get("center_lat", attributes.get("lat"))
    lon_val_for_map = attributes.get("center_lon", attributes.get("lon"))
    if lat_val_for_map and lon_val_for_map:
        try:
            float(lat_val_for_map); float(lon_val_for_map)
            gmaps_link = f"https://www.google.com/maps?q={escape_attr(lat_val_for_map)},{escape_attr(lon_val_for_map)}"
            metadata_table_rows.append(f'<tr><td>Kart</td><td><a href="{gmaps_link}" target="_blank" class="map-link-in-tooltip">Vis på Google Maps</a></td></tr>')
        except ValueError: gmaps_link = ""
    tooltip_html = f'<div class="tooltip-content"><table>{"".join(metadata_table_rows)}</table></div>'
    data_gmaps_attr = f'data-gmaps-link="{gmaps_link}"' if gmaps_link else ""
    
    s = '<span class="custom-tag-container" '
    s += data_gmaps_attr
    s += ' tabindex="0">'
    s += escape_attr(display_name)
    s += '<span class="tooltip">'
    s += tooltip_html
    s += '</span></span>'
    return s

# NY: Hjelpefunksjon for å prosessere en enkelt linje (eller heading-innhold)
def process_text_with_inline_tags(text_line):
    custom_tag_regex_for_split = r"(<\w+\s+[^>]+?>)" # Matcher våre custom tags
    single_tag_parse_regex = r"<(\w+)\s+([^>]+?)>"
    
    parts = re.split(custom_tag_regex_for_split, text_line)
    processed_parts = []
    for i, part_str in enumerate(parts):
        if not part_str: continue
        if i % 2 == 1: # Custom tag string
            match = re.fullmatch(single_tag_parse_regex, part_str)
            if match:
                processed_parts.append(parse_custom_tag(match))
            else: 
                processed_parts.append(html.escape(part_str)) 
        else: # Vanlig tekst
            processed_parts.append(html.escape(part_str))
    return "".join(processed_parts)

def nsd_to_html_content(nsd_content):
    output_html_blocks = []
    current_paragraph_lines_raw = [] # Samler RÅ tekstlinjer for ett avsnitt

    def flush_paragraph_to_div():
        nonlocal current_paragraph_lines_raw
        if current_paragraph_lines_raw:
            # Prosesser hver linje for inline tags, og join deretter med <br />
            processed_html_lines_for_paragraph = []
            for raw_line in current_paragraph_lines_raw:
                processed_html_lines_for_paragraph.append(process_text_with_inline_tags(raw_line))
            
            final_paragraph_html = "<br />\n".join(processed_html_lines_for_paragraph)
            
            if final_paragraph_html.strip():
                 output_html_blocks.append(f'<div class="text-block">{final_paragraph_html}</div>')
            current_paragraph_lines_raw = []

    lines = nsd_content.splitlines()
    
    for line_idx, line_text in enumerate(lines):
        stripped_line = line_text.strip()

        is_block_element_line = (
            line_text.startswith("# ") or
            line_text.startswith("## ") or
            line_text.startswith("### ") or
            re.fullmatch(r"-{3,}", stripped_line) or
            re.fullmatch(r"\*{3,}", stripped_line)
        )

        if is_block_element_line:
            flush_paragraph_to_div()
            # For headinger, prosesser innholdet for inline tags
            if line_text.startswith("# "): 
                output_html_blocks.append(f"<h1>{process_text_with_inline_tags(line_text[2:])}</h1>")
            elif line_text.startswith("## "): 
                output_html_blocks.append(f"<h2>{process_text_with_inline_tags(line_text[3:])}</h2>")
            elif line_text.startswith("### "): 
                output_html_blocks.append(f"<h3>{process_text_with_inline_tags(line_text[4:])}</h3>")
            else: # Må være HR
                output_html_blocks.append("<hr>")
        elif not stripped_line: 
            flush_paragraph_to_div()
            # output_html_blocks.append('<div class="text-block"> </div>') # Valgfritt
        else: 
            current_paragraph_lines_raw.append(line_text) # Legg til RÅ linje
    
    flush_paragraph_to_div() 

    return "\n".join(output_html_blocks)

def generate_full_html(body_content, title="Smart Dokument"):
    css_styles = f"""
    body {{ 
        font-family: sans-serif; 
        line-height: 1.6; 
        margin: 20px; 
        font-size: 16px; /* Sett en grunnleggende fontstørrelse for body */
    }}
    h1, h2, h3 {{ color: #333; }}
    /* Standard heading-størrelser (kan justeres) */
    h1 {{ font-size: 2em; }}
    h2 {{ font-size: 1.5em; }}
    h3 {{ font-size: 1.17em; }}

    .text-block {{
        margin-bottom: 1em; 
    }}
    hr {{ margin: 20px 0; }}

    .custom-tag-container {{
        position: relative; 
        display: inline;         
        border-bottom: 1px dotted blue; 
        cursor: default; 
    }}
    .custom-tag-container[data-gmaps-link] {{
        cursor: pointer;
        color: navy; /* Farge for klikkbare tagger */
    }}

    .tooltip {{
        visibility: hidden;
        width: auto; 
        min-width: 250px;
        max-width: 400px;
        background-color: #f9f9f9;
        color: #333; /* Standard tekstfarge for tooltip-innhold */
        text-align: left;
        border-radius: 6px;
        padding: 10px;
        position: absolute;
        z-index: 1; 
        top: 100%; 
        left: 0;   
        opacity: 0;
        transition: opacity 0.3s, visibility 0s linear 0.3s; 
        box-shadow: 0px 0px 10px rgba(0,0,0,0.1);
        border: 1px solid #ddd;
        
        /* --- NYTT: Overstyr fontstiler for tooltip-innhold --- */
        font-family: sans-serif; /* Eller en annen basefont du foretrekker */
        font-size: 0.9rem;       /* En mindre, fast størrelse (rem er relativt til root font-size) */
                                 /* Alternativt: font-size: 14px; (pikselbasert) */
        font-weight: normal;
        line-height: 1.4;      /* Justert linjehøyde for tooltip */
        /* Sikre at tekstfargen ikke arves fra heading */
        color: #222; /* En mørk gråfarge, juster etter ønske */
    }}

    /* Sørg for at linker inne i tooltipen også får standard farge og ikke arver heading-farge */
    .tooltip a, .tooltip a:visited {{
        color: navy; /* Eller en annen standard linkfarge */
        text-decoration: underline;
    }}
    .tooltip a:hover {{
        color: darkblue;
    }}


    .custom-tag-container:hover .tooltip,
    .custom-tag-container:focus .tooltip,
    .custom-tag-container.tooltip-active .tooltip {{
        visibility: visible;
        opacity: 1;
        transition: opacity 0.3s;
        z-index: 10; 
    }}
    .tooltip table {{
        width: 100%;
        border-collapse: collapse;
        /* Arver fontstiler fra .tooltip, men vi kan være mer spesifikke hvis nødvendig */
    }}
    .tooltip th, .tooltip td {{
        padding: 5px;
        border: 1px solid #eee;
        text-align: left;
        /* font-size er allerede satt av .tooltip, men kan overstyres her om ønskelig */
        /* f.eks. font-size: 1em; for å være relativ til tooltipens font-size (0.9rem) */
    }}
    .tooltip th {{ 
        background-color: #e9e9e9; 
        font-weight: bold; /* Sørg for at th er fet */
    }}
    """
    # ... (JavaScript og HTML-mal forblir den samme) ...
    javascript_code = """
    document.addEventListener('DOMContentLoaded', function() {
        console.log("DOM geladen, starter JS for tooltips.");
        const containers = document.querySelectorAll('.custom-tag-container');
        console.log(`Fant ${containers.length} custom-tag-container elementer.`);

        containers.forEach((container, index) => {
            const currentDisplayName = container.firstChild && container.firstChild.nodeType === Node.TEXT_NODE ? container.firstChild.textContent.trim() : "Ukjent_Navn_JS";
            // console.log(`Setter opp container ${index}, Navn: ${JSON.stringify(currentDisplayName)}`); // Kan kommenteres ut for mindre støy

            const gmapsLink = container.getAttribute('data-gmaps-link');
            if (gmapsLink) {
                container.addEventListener('click', function(event) {
                    if (event.target.closest('a.map-link-in-tooltip')) {
                        return;
                    }
                    // console.log(`Container ${index} (Navn: ${JSON.stringify(currentDisplayName)}) klikket, åpner: ${gmapsLink}`);
                    window.open(gmapsLink, '_blank');
                });
            }

            let enterTimeout;
            let leaveTimeout;
            const tooltipElement = container.querySelector('.tooltip'); 

            if (!tooltipElement) {
                console.error(`FEIL: Fant IKKE .tooltip inne i container ${index} (Navn: ${JSON.stringify(currentDisplayName)})`);
            } else {
                // console.log(`OK: Fant .tooltip inne i container ${index} (Navn: ${JSON.stringify(currentDisplayName)})`);
            }

            container.addEventListener('mouseenter', function(event) {
                // console.log(`Mouseenter på container ${index} (Navn: ${JSON.stringify(currentDisplayName)})`);
                clearTimeout(leaveTimeout); 
                enterTimeout = setTimeout(() => {
                    // console.log(`Timeout for å vise tooltip for container ${index} (Navn: ${JSON.stringify(currentDisplayName)})`);
                    this.classList.add('tooltip-active');
                }, 150); 
            });

            container.addEventListener('mouseleave', function() {
                // console.log(`Mouseleave fra container ${index} (Navn: ${JSON.stringify(currentDisplayName)})`);
                clearTimeout(enterTimeout); 
                leaveTimeout = setTimeout(() => {
                    // console.log(`Timeout for å skjule tooltip for container ${index} (Navn: ${JSON.stringify(currentDisplayName)})`);
                    this.classList.remove('tooltip-active');
                }, 250); 
            });
            
            container.addEventListener('focus', function() {
                // console.log(`Focus på container ${index} (Navn: ${JSON.stringify(currentDisplayName)})`);
                this.classList.add('tooltip-active');
            });
            container.addEventListener('blur', function() {
                // console.log(`Blur fra container ${index} (Navn: ${JSON.stringify(currentDisplayName)})`);
                if (!this.contains(document.activeElement) || document.activeElement === this) {
                    this.classList.remove('tooltip-active');
                }
            });

            if (tooltipElement) { 
                tooltipElement.addEventListener('mouseenter', function() {
                    // console.log(`Mouseenter på SELVE tooltipen for container ${index} (Navn: ${JSON.stringify(currentDisplayName)})`);
                    clearTimeout(leaveTimeout); 
                    container.classList.add('tooltip-active'); 
                });
                tooltipElement.addEventListener('mouseleave', function() {
                    // console.log(`Mouseleave fra SELVE tooltipen for container ${index} (Navn: ${JSON.stringify(currentDisplayName)})`);
                    leaveTimeout = setTimeout(() => {
                        container.classList.remove('tooltip-active');
                    }, 250);
                });
            }
        });
        console.log("JS for tooltips ferdig satt opp.");
    });
    """

    html_template = f"""<!DOCTYPE html>
<html lang="no">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(title)}</title>
    <style>
{css_styles}
    </style>
</head>
<body>
    {body_content}
    <script>
{javascript_code}
    </script>
</body>
</html>"""
    return html_template

def main():
    parser = argparse.ArgumentParser(
        description="Konverterer et .nsd (NVE Smart Dokument) til en interaktiv HTML-fil.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "input_file",
        type=pathlib.Path,
        help="Sti til input .nsd-fil"
    )
    parser.add_argument(
        "-o", "--output",
        type=pathlib.Path,
        help="Valgfri sti for output HTML-fil. Standard: <input_fil_navn>.html"
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Skriv HTML-output til stdout i stedet for en fil."
    )
    parser.add_argument(
        "--title",
        type=str,
        default=None, # Vil bruke filnavnet hvis ikke satt
        help="Tittel for HTML-dokumentet."
    )

    args = parser.parse_args()

    input_path: pathlib.Path = args.input_file

    if not input_path.is_file():
        print(f"Feil: Input-filen '{input_path}' ble ikke funnet.", file=sys.stderr)
        sys.exit(1)

    if input_path.suffix.lower() != ".nsd":
        print(f"Advarsel: Input-filen '{input_path}' har ikke .nsd-ending, men fortsetter.", file=sys.stderr)

    try:
        nsd_content = input_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"Feil under lesing av filen '{input_path}': {e}", file=sys.stderr)
        sys.exit(1)

    if not nsd_content.strip():
        print(f"Filen '{input_path}' er tom.", file=sys.stderr)
        # Håndter tom output for HTML også
        empty_html_body = "<p>Dokumentet er tomt.</p>"
        doc_title = args.title if args.title else input_path.stem
        full_empty_html = generate_full_html(empty_html_body, title=doc_title)
        if args.stdout:
            print(full_empty_html)
        else:
            output_path = args.output if args.output else input_path.with_suffix(".html")
            output_path.write_text(full_empty_html, encoding="utf-8")
            print(f"Tom HTML skrevet til '{output_path}'", file=sys.stderr)
        sys.exit(0)

    html_body = nsd_to_html_content(nsd_content)
    
    doc_title = args.title if args.title else input_path.stem # Bruk filstammen som tittel hvis ikke gitt

    full_html_output = generate_full_html(html_body, title=doc_title)

    if args.stdout:
        print(full_html_output)
    else:
        output_path = args.output if args.output else input_path.with_suffix(".html")
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(full_html_output, encoding="utf-8")
            print(f"HTML-innhold lagret til: {output_path}", file=sys.stderr)
        except Exception as e:
            print(f"Feil under skriving til output-filen '{output_path}': {e}", file=sys.stderr)
            sys.exit(1)

if __name__ == "__main__":
    main()