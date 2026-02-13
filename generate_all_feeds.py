#!/usr/bin/env python3
"""
Generator wielu RSS feedów na podstawie pliku konfiguracyjnego
"""

import os
import sys
import re
from pathlib import Path
from generate_rss_feed import generate_rss_feed, Auth, TOKEN_FILE, get_program_info
import argparse
import getpass

def load_program_ids(config_file):
    """Wczytaj listę ID programów z pliku tekstowego"""
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            program_ids = []
            for line in f:
                line = line.strip()
                # Pomiń puste linie i komentarze
                if not line or line.startswith('#'):
                    continue
                # Weź tylko ID (same cyfry)
                if line.isdigit():
                    program_ids.append(line)
            return program_ids
    except FileNotFoundError:
        print(f"✗ Nie znaleziono pliku konfiguracyjnego: {config_file}")
        sys.exit(1)

def slugify(text):
    """Konwertuj tekst na slug (nazwa_pliku)"""
    # Polskie znaki na ASCII
    replacements = {
        'ą': 'a', 'ć': 'c', 'ę': 'e', 'ł': 'l', 'ń': 'n', 
        'ó': 'o', 'ś': 's', 'ź': 'z', 'ż': 'z',
        'Ą': 'A', 'Ć': 'C', 'Ę': 'E', 'Ł': 'L', 'Ń': 'N',
        'Ó': 'O', 'Ś': 'S', 'Ź': 'Z', 'Ż': 'Z'
    }
    for pl, ascii in replacements.items():
        text = text.replace(pl, ascii)
    
    # Usuń znaki specjalne, zostaw tylko litery, cyfry, spacje i myślniki
    text = re.sub(r'[^\w\s-]', '', text)
    # Spacje i myślniki na podkreślenia
    text = re.sub(r'[\s-]+', '_', text)
    # Lowercase
    text = text.lower()
    # Usuń podkreślenia z początku i końca
    text = text.strip('_')
    
    return text

def ensure_directory(filepath):
    """Upewnij się, że katalog dla pliku istnieje"""
    directory = os.path.dirname(filepath)
    if directory:
        Path(directory).mkdir(parents=True, exist_ok=True)

def main():
    parser = argparse.ArgumentParser(
        description='Generowanie wielu RSS feedów na podstawie pliku konfiguracyjnego',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Plik konfiguracyjny zawiera ID programów (jeden per linia):
  # Komentarze zaczynają się od #
  100037114
  100064080
  130265
        '''
    )
    parser.add_argument('-c', '--config', default='config.txt', help='Plik konfiguracyjny (domyślnie: config.txt)')
    parser.add_argument('-o', '--output-dir', default='feeds', help='Katalog dla plików RSS (domyślnie: feeds/)')
    parser.add_argument('-n', '--max-episodes', type=int, default=50, help='Maksymalna liczba odcinków (domyślnie: 50)')
    parser.add_argument('--all', action='store_true', help='Pobierz wszystkie dostępne odcinki (ignoruje -n)')
    parser.add_argument('--free-only', action='store_true', help='Pobierz tylko darmowe odcinki (bez treści dla patronów)')
    parser.add_argument('--login', action='store_true', help='Zaloguj się (dla treści tylko dla patronów)')
    parser.add_argument('--email', help='Email do logowania')
    parser.add_argument('--password', help='Hasło')
    parser.add_argument('--token-file', help=f'Plik z tokenami (domyślnie: {TOKEN_FILE})')
    
    args = parser.parse_args()
    
    # Wczytaj listę ID programów
    program_ids = load_program_ids(args.config)
    
    if not program_ids:
        print("✗ Brak programów w pliku konfiguracyjnym")
        sys.exit(1)
    
    # Upewnij się, że katalog wyjściowy istnieje
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    
    # Inicjalizuj autoryzację
    token_file = Path(args.token_file) if args.token_file else TOKEN_FILE
    auth = Auth(token_file)
    
    # Logowanie
    if args.login:
        email = args.email or input("Email: ")
        password = args.password or getpass.getpass("Hasło: ")
        
        if auth.login(email, password):
            print("✓ Zalogowano pomyślnie\n")
        else:
            print("✗ Logowanie nie powiodło się\n")
            auth = None
    
    # Ustal parametry
    if args.all:
        max_episodes = 99999
    else:
        max_episodes = args.max_episodes
    
    include_exclusive = not args.free_only
    
    print(f"\n{'='*60}")
    print(f"Znaleziono {len(program_ids)} programów do wygenerowania")
    print(f"Katalog wyjściowy: {args.output_dir}")
    if args.free_only:
        print(f"Tryb: tylko darmowe odcinki")
    else:
        print(f"Tryb: wszystkie odcinki (włącznie z treściami dla patronów)")
    print(f"{'='*60}\n")
    
    # Generuj feedy
    success_count = 0
    error_count = 0
    
    for i, program_id in enumerate(program_ids, 1):
        # Pobierz informacje o programie
        try:
            program_info = get_program_info(program_id)
            program_name = program_info.get("name", f"Program {program_id}")
        except Exception as e:
            print(f"[{i}/{len(program_ids)}] ✗ Błąd pobierania info dla ID {program_id}: {e}\n")
            error_count += 1
            continue
        
        # Wygeneruj nazwę pliku
        filename_slug = slugify(program_name)
        if not filename_slug:
            filename_slug = f"program_{program_id}"
        output_file = os.path.join(args.output_dir, f"{filename_slug}.xml")
        
        print(f"[{i}/{len(program_ids)}] {program_name} (ID: {program_id})")
        print(f"  └─ Plik: {output_file}")
        
        # Generuj feed
        try:
            success = generate_rss_feed(
                program_id,
                output_file,
                max_episodes=max_episodes,
                include_exclusive=include_exclusive,
                auth=auth
            )
            if success:
                success_count += 1
            else:
                error_count += 1
        except Exception as e:
            print(f"  └─ ✗ Błąd: {e}\n")
            error_count += 1
            continue
        
        print()
    
    # Podsumowanie
    print(f"{'='*60}")
    print(f"PODSUMOWANIE")
    print(f"{'='*60}")
    print(f"✓ Wygenerowano pomyślnie: {success_count}")
    if error_count > 0:
        print(f"✗ Błędy: {error_count}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
