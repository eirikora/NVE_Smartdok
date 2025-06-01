#!/usr/bin/env python3
import argparse
import pathlib
import sys
import re
import html

# NYTT: Importer markdown-it-py for robust Markdown-konvertering
from markdown_it import MarkdownIt
from markdown_it.token import Token
from markdown_it.renderer import RendererProtocol
from markdown_it.utils import OptionsDict
from markdown_it.rules_inline import StateInline

# --- Logikk for å bygge HTML for en custom tag (hentet fra originalt script) ---
# Denne logikken er nå mer gjenbrukbar.
def _build_interactive_tag_html(attributes: dict, tag_type: str) -> str:
    """Bygger den endelige HTML-en for en parset custom tag."""
    display_name = attributes.get("navn", "Ukjent Navn")
    metadata_table_rows = []
    
    key_display_order = {
        "navn": "Navn", "id": "ID", "eier": "Eier", "kommune": "Kommune", 
        "status": "Status", "ytelse_MW": "Ytelse (MW)", "vassdragsNr": "Vassdragsnr.", 
        "magasinNr": "Magasinnr.", "areal_km2": "Areal (km²)", 
        "center_lat": "Latitude", "center_lon": "Longitude",
        "lat": "Latitude", "lon": "Longitude",
    }

    final_type_value = attributes.get('type', tag_type).capitalize()
    metadata_table_rows.append(f"<tr><td>Type</td><td>{html.escape(final_type_value)}</td></tr>")

    processed_keys = set(['type'])

    for key, display_text in key_display_order.items():
        if key in processed_keys: continue
        if key in attributes and attributes[key] is not None and str(attributes[key]).strip() != "":
            value = attributes[key]
            
            # Spesialhåndtering for posisjon
            is_lat = key in ["center_lat", "lat"]
            is_lon = key in ["center_lon", "lon"]
            
            if is_lat:
                lon_key_to_use = "center_lon" if "center_lon" in attributes else "lon"
                if lon_key_to_use in attributes:
                    lat_val = value
                    lon_val = attributes.get(lon_key_to_use)
                    if lat_val and lon_val:
                        try: 
                            float(lat_val); float(lon_val)
                            metadata_table_rows.append(f"<tr><td>Posisjon</td><td>Lat: {html.escape(lat_val)}, Lon: {html.escape(lon_val)}</td></tr>")
                        except ValueError: pass
                    processed_keys.add(lat_val)
                    processed_keys.add(lon_key_to_use)
                continue
            elif is_lon:
                # Dette håndteres allerede av lat-sjekken, så vi skipper.
                continue
            
            metadata_table_rows.append(f"<tr><td>{html.escape(display_text)}</td><td>{html.escape(str(value))}</td></tr>")
            processed_keys.add(key)
            
    gmaps_link = ""
    lat_val_for_map = attributes.get("center_lat", attributes.get("lat"))
    lon_val_for_map = attributes.get("center_lon", attributes.get("lon"))
    if lat_val_for_map and lon_val_for_map:
        try:
            float(lat_val_for_map); float(lon_val_for_map)
            gmaps_link = f"https://www.google.com/maps?q={html.escape(lat_val_for_map)},{html.escape(lon_val_for_map)}"
            metadata_table_rows.append(f'<tr><td>Kart</td><td><a href="{gmaps_link}" target="_blank" class="map-link-in-tooltip">Vis på Google Maps</a></td></tr>')
        except ValueError: gmaps_link = ""

    tooltip_html = f'<div class="tooltip-content"><table>{"".join(metadata_table_rows)}</table></div>'
    data_gmaps_attr = f'data-gmaps-link="{gmaps_link}"' if gmaps_link else ""
    
    s = f'<span class="custom-tag-container" {data_gmaps_attr} tabindex="0">'
    s += html.escape(display_name)
    s += f'<span class="tooltip">{tooltip_html}</span>'
    s += '</span>'
    return s

# --- Nytt system for Markdown-konvertering ---

def _parse_attributes(tag_content: str) -> dict:
    """Parser en attributt-streng som 'key="value" key2='value2'' til et dict."""
    attributes = {}
    attr_regex = r'([\w_:-]+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s>]+))'
    for attr_match in re.finditer(attr_regex, tag_content):
        key = attr_match.group(1)
        value = next(g for g in attr_match.groups()[1:] if g is not None)
        attributes[key] = value
    return attributes

def nsd_tag_plugin(md: MarkdownIt):
    """En plugin for markdown-it-py for å håndtere [[...]]-syntaksen."""
    
    def nsd_tag_rule(state: "StateInline", silent: bool): # Bruker streng-hint
        # ... (koden for nsd_tag_rule er uendret)
        if state.src[state.pos:state.pos + 2] != '[[':
            return False
        
        search_start_pos = state.pos + 2
        if search_start_pos >= len(state.src):
            return False

        match_end_bracket = state.src.find(']]', search_start_pos)
        
        if match_end_bracket == -1:
            return False
        
        tag_full_content = state.src[search_start_pos:match_end_bracket]
        
        parts = tag_full_content.strip().split(maxsplit=1)
        if not parts:
            return False
        tag_type = parts[0]
        attr_string = parts[1] if len(parts) > 1 else ""
        
        if not silent:
            attributes = _parse_attributes(attr_string)
            
            token = state.push("nsd_tag", "", 0) 
            token.meta["attributes"] = attributes
            token.meta["tag_type"] = tag_type
        
        state.pos = match_end_bracket + 2
        return True

    # KORRIGERT SIGNATUR HER:
    # Fjern 'self' og type-hint RendererProtocol hvis den ikke brukes
    def render_nsd_tag(tokens: list[Token], idx: int, options: OptionsDict, env: dict) -> str:
        token = tokens[idx]
        attributes = token.meta.get("attributes", {})
        tag_type = token.meta.get("tag_type", "ukjent")
        return _build_interactive_tag_html(attributes, tag_type)

    md.inline.ruler.before("escape", "nsd_tag", nsd_tag_rule)
    md.renderer.rules["nsd_tag"] = render_nsd_tag

def preprocess_nsd_to_commonmark(nsd_content: str) -> str:
    """
    Konverterer custom <tag ...> til [[tag ...]] for å unngå konflikt med HTML
    og for å gjøre det lettere for markdown-parseren.
    """
    # Regex for å finne en custom tag. \w+ sikrer at det er et ord som tag-navn.
    custom_tag_regex = r"<(\w+\s+[^>]*?)>"
    
    # \1 er en back-reference til den første capture-gruppen (innholdet inni <...>)
    # Dette bytter <elv ...> til [[elv ...]] på en sikker måte.
    return re.sub(custom_tag_regex, r"[[\1]]", nsd_content)

def nsd_to_html_content(nsd_content: str) -> str:
    """
    Hovedfunksjon for konvertering. Bruker nå en fullverdig Markdown-parser.
    """
    # 1. Pre-prosesser innholdet for å bytte ut <tag> med [[tag]]
    preprocessed_content = preprocess_nsd_to_commonmark(nsd_content)

    # 2. Sett opp markdown-parseren med vår custom plugin
    md = MarkdownIt("commonmark").use(nsd_tag_plugin)
    
    # 3. Konverter hele dokumentet til HTML.
    #    md.render() tar seg av alt: overskrifter, lister, avsnitt, og våre custom tags via plugin-en.
    html_output = md.render(preprocessed_content)
    
    # Etter markdown-konvertering er avsnitt pakket i <p>. Vi bytter dette til
    # <div class="text-block"> for å matche den gamle klassestrukturen om ønskelig.
    html_output = html_output.replace("<p>", '<div class="text-block">').replace("</p>", "</div>")
    
    return html_output

# Funksjonene `generate_full_html` og `main` er uendret, da de kun jobber med
# det ferdige HTML-innholdet eller filhåndtering. Vi limer dem inn her for kompletthet.

def generate_full_html(body_content, title="Smart Dokument"):
    css_styles = """
    body { 
        font-family: sans-serif; 
        line-height: 1.6; 
        margin: 20px auto; /* Sentrer innholdet */
        max-width: 800px;  /* Bedre lesbarhet */
        font-size: 16px;
    }
    h1, h2, h3 { color: #333; }
    h1 { font-size: 2em; }
    h2 { font-size: 1.5em; }
    h3 { font-size: 1.17em; }

    .text-block {
        margin-bottom: 1em; 
    }
    hr { margin: 20px 0; }
    
    /* Legg til stiler for lister og annen markdown-syntaks */
    ul, ol {
        padding-left: 2em;
    }
    blockquote {
        border-left: 4px solid #ccc;
        padding-left: 1em;
        margin-left: 0;
        color: #666;
    }
    code {
        background-color: #f0f0f0;
        padding: 2px 4px;
        border-radius: 3px;
        font-family: monospace;
    }
    pre > code {
        display: block;
        padding: 1em;
        overflow-x: auto;
    }


    .custom-tag-container {
        position: relative; 
        display: inline;         
        border-bottom: 1px dotted blue; 
        cursor: default; 
    }
    .custom-tag-container[data-gmaps-link] {
        cursor: pointer;
        color: navy; /* Farge for klikkbare tagger */
    }

    .tooltip {
        visibility: hidden;
        width: auto; 
        min-width: 250px;
        max-width: 400px;
        background-color: #f9f9f9;
        color: #333;
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
        font-family: sans-serif;
        font-size: 0.9rem;
        font-weight: normal;
        line-height: 1.4;
        color: #222;
    }
    .tooltip a, .tooltip a:visited {
        color: navy;
        text-decoration: underline;
    }
    .tooltip a:hover { color: darkblue; }

    .custom-tag-container:hover .tooltip,
    .custom-tag-container:focus .tooltip,
    .custom-tag-container.tooltip-active .tooltip {
        visibility: visible;
        opacity: 1;
        transition: opacity 0.3s;
        z-index: 10; 
    }
    .tooltip table {
        width: 100%;
        border-collapse: collapse;
    }
    .tooltip th, .tooltip td {
        padding: 5px;
        border: 1px solid #eee;
        text-align: left;
    }
    .tooltip th { 
        background-color: #e9e9e9; 
        font-weight: bold;
    }
    """
    javascript_code = """
    document.addEventListener('DOMContentLoaded', function() {
        const containers = document.querySelectorAll('.custom-tag-container');
        containers.forEach(container => {
            const gmapsLink = container.getAttribute('data-gmaps-link');
            if (gmapsLink) {
                container.addEventListener('click', function(event) {
                    if (event.target.closest('a.map-link-in-tooltip')) { return; }
                    window.open(gmapsLink, '_blank');
                });
            }
            let enterTimeout, leaveTimeout;
            const tooltipElement = container.querySelector('.tooltip'); 
            container.addEventListener('mouseenter', function() {
                clearTimeout(leaveTimeout); 
                enterTimeout = setTimeout(() => this.classList.add('tooltip-active'), 150); 
            });
            container.addEventListener('mouseleave', function() {
                clearTimeout(enterTimeout); 
                leaveTimeout = setTimeout(() => this.classList.remove('tooltip-active'), 250); 
            });
            container.addEventListener('focus', function() { this.classList.add('tooltip-active'); });
            container.addEventListener('blur', function() { this.classList.remove('tooltip-active'); });
            if (tooltipElement) { 
                tooltipElement.addEventListener('mouseenter', () => clearTimeout(leaveTimeout));
                tooltipElement.addEventListener('mouseleave', () => {
                    leaveTimeout = setTimeout(() => container.classList.remove('tooltip-active'), 250);
                });
            }
        });
    });
    """

    html_template = f"""<!DOCTYPE html>
<html lang="no">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(title)}</title>
    <style>{css_styles}</style>
</head>
<body>
    {body_content}
    <script>{javascript_code}</script>
</body>
</html>"""
    return html_template

def main():
    parser = argparse.ArgumentParser(
        description="Konverterer et .nsd (NVE Smart Dokument) til en interaktiv HTML-fil med full Markdown-støtte.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("input_file", type=pathlib.Path, help="Sti til input .nsd-fil")
    parser.add_argument("-o", "--output", type=pathlib.Path, help="Valgfri sti for output HTML-fil. Standard: <input_fil_navn>.html")
    parser.add_argument("--stdout", action="store_true", help="Skriv HTML-output til stdout i stedet for en fil.")
    parser.add_argument("--title", type=str, default=None, help="Tittel for HTML-dokumentet.")

    args = parser.parse_args()
    input_path: pathlib.Path = args.input_file

    if not input_path.is_file():
        print(f"Feil: Input-filen '{input_path}' ble ikke funnet.", file=sys.stderr)
        sys.exit(1)

    try:
        nsd_content = input_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"Feil under lesing av filen '{input_path}': {e}", file=sys.stderr)
        sys.exit(1)

    if not nsd_content.strip():
        # Håndterer tom fil som før
        empty_html_body = "<p>Dokumentet er tomt.</p>"
        doc_title = args.title if args.title else input_path.stem
        full_empty_html = generate_full_html(empty_html_body, title=doc_title)
        if args.stdout: print(full_empty_html)
        else:
            output_path = args.output if args.output else input_path.with_suffix(".html")
            output_path.write_text(full_empty_html, encoding="utf-8")
            print(f"Tom HTML skrevet til '{output_path}'", file=sys.stderr)
        sys.exit(0)

    html_body = nsd_to_html_content(nsd_content)
    doc_title = args.title if args.title else input_path.stem
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