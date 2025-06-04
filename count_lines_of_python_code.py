import os

def count_lines_in_file(filepath):
    """Teller antall linjer i en gitt fil."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return len(f.readlines())
    except Exception as e:
        print(f"Kunne ikke lese filen {filepath}: {e}")
        return 0

def find_py_files_and_count_lines(start_folder="."):
    """
    Finner alle .py-filer i start_folder og dens undermapper,
    teller linjer i hver, og summerer totalen.
    """
    total_lines = 0
    file_count = 0

    print("Linjetelling per .py-fil:")
    for foldername, subfolders, filenames in os.walk(start_folder):
        # Ignorer vanlige virtuelle miljø-mapper for å unngå å telle bibliotekskode
        # Du kan legge til flere mappenavn her om nødvendig
        if any(ignored_folder in foldername for ignored_folder in ['.venv', 'venv', 'env', '__pycache__']):
            continue

        for filename in filenames:
            if filename.endswith(".py"):
                filepath = os.path.join(foldername, filename)
                lines = count_lines_in_file(filepath)
                print(f"- {filepath}: {lines} linjer")
                total_lines += lines
                file_count += 1
    
    print(f"\n--- Oppsummering ---")
    if file_count > 0:
        print(f"Fant {file_count} .py-filer.")
        print(f"Totalt antall linjer i alle .py-filer: {total_lines}")
    else:
        print("Ingen .py-filer funnet.")

if __name__ == "__main__":
    # Kjør funksjonen for gjeldende mappe
    current_directory = os.getcwd()
    print(f"Søker etter .py-filer i: {current_directory} og undermapper...\n")
    find_py_files_and_count_lines(current_directory)