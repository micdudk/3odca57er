#!/usr/bin/env python3
"""
Generator RSS dla wszystkich autorów z Radia 357
Skanuje wszystkie programy, zbiera listę autorów i generuje osobne feedy
"""

import requests
import json
from datetime import datetime
import argparse
import getpass
import os
from pathlib import Path
import re
from generate_author_feed_by_id import (
    Auth, TOKEN_FILE, API_BASE, load_program_ids, load_author_ids,
    get_program_info, fetch_all_episodes_from_program,
    generate_author_rss_feed, get_audio_url, slugify, fetch_all_programs
)

def collect_all_authors(program_ids):
    """Zbierz listę wszystkich autorów ze wszystkich programów (używając email jako ID)"""
    authors_dict = {}  # {email: {name, episode_count, programs}}
    
    print(f"Skanowanie programów w poszukiwaniu autorów...")
    print(f"Programy do przeskanowania: {len(program_ids)}\n")
    
    for i, program_id in enumerate(program_ids, 1):
        # Pobierz info o programie
        try:
            program_info = get_program_info(program_id)
            program_name = program_info.get("name", f"Program {program_id}")
        except Exception as e:
            print(f"[{i}/{len(program_ids)}] ⚠ Błąd pobierania info dla programu {program_id}: {e}")
            continue
        
        print(f"[{i}/{len(program_ids)}] {program_name}")
        
        # Pobierz odcinki z programu
        episodes = fetch_all_episodes_from_program(program_id, max_episodes_per_program=500)
        
        # Zbierz autorów z odcinków
        for episode in episodes:
            team = episode.get("team") or []
            for member in team:
                if not member:  # Null check
                    continue
                author_name = member.get("name", "").strip()
                author_email = member.get("id", "").strip()  # ID = email
                
                if author_email and author_name:
                    if author_email not in authors_dict:
                        authors_dict[author_email] = {
                            'name': author_name,
                            'email': author_email,
                            'episode_count': 0,
                            'programs': set()
                        }
                    
                    authors_dict[author_email]['episode_count'] += 1
                    authors_dict[author_email]['programs'].add(program_name)
    
    # Konwertuj do listy
    authors_list = []
    for email, data in authors_dict.items():
        authors_list.append({
            'name': data['name'],
            'email': email,
            'episode_count': data['episode_count'],
            'programs': list(data['programs'])
        })
    
    # Sortuj po liczbie odcinków (malejąco)
    authors_list.sort(key=lambda x: x['episode_count'], reverse=True)
    
    return authors_list

def collect_episodes_by_author_optimized(author_email, program_ids, all_episodes_cache, max_total_episodes=100, include_exclusive=False):
    """Zbierz odcinki konkretnego autora po email (używając cache)"""
    author_episodes = []
    
    for program_id in program_ids:
        if program_id not in all_episodes_cache:
            continue
        
        episodes_data = all_episodes_cache[program_id]
        episodes = episodes_data['episodes']
        
        # Filtruj odcinki po autorze (po email)
        for episode in episodes:
            # Sprawdź autorów w team
            team = episode.get("team") or []
            has_author = False
            
            for member in team:
                if not member:
                    continue
                member_email = member.get("id", "")
                if member_email == author_email:
                    has_author = True
                    break
            
            if has_author:
                # Sprawdź czy to darmowy odcinek
                is_free = episode.get("isFree", True)
                
                if is_free or include_exclusive:
                    # Odcinek już ma informacje o programie z cache
                    author_episodes.append(episode)
        
        # Jeśli mamy już wystarczająco dużo odcinków, możemy przerwać
        if len(author_episodes) >= max_total_episodes:
            break
    
    # Sortuj odcinki po dacie publikacji (od najnowszych)
    author_episodes.sort(key=lambda x: x.get("publishedAt", 0), reverse=True)
    
    # Ogranicz do max_total_episodes
    author_episodes = author_episodes[:max_total_episodes]
    
    return author_episodes

def build_episodes_cache(program_ids):
    """Zbuduj cache wszystkich odcinków ze wszystkich programów"""
    cache = {}
    
    print(f"\nBudowanie cache odcinków...")
    print(f"Programy do przeskanowania: {len(program_ids)}\n")
    
    for i, program_id in enumerate(program_ids, 1):
        # Pobierz info o programie
        try:
            program_info = get_program_info(program_id)
            program_name = program_info.get("name", f"Program {program_id}")
            program_image = program_info.get("image", "")
        except Exception as e:
            print(f"[{i}/{len(program_ids)}] ⚠ Błąd pobierania info dla programu {program_id}: {e}")
            continue
        
        print(f"[{i}/{len(program_ids)}] {program_name}")
        
        # Pobierz odcinki z programu
        episodes = fetch_all_episodes_from_program(program_id, max_episodes_per_program=500)
        
        # Dodaj informacje o programie do każdego odcinka
        for episode in episodes:
            episode["_program_name"] = program_name
            episode["_program_id"] = program_id
            episode["_program_image"] = program_image
        
        cache[program_id] = {
            'program_name': program_name,
            'program_image': program_image,
            'episodes': episodes
        }
        
        print(f"  └─ Pobrano: {len(episodes)} odcinków")
    
    print(f"\n{'='*60}")
    print(f"Cache zbudowany dla {len(cache)} programów")
    print(f"{'='*60}\n")
    
    return cache

def main():
    parser = argparse.ArgumentParser(
        description='Generowanie RSS feedów dla wszystkich autorów z Radia 357',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Ten skrypt:
1. Skanuje wszystkie programy (domyślnie: wszystkie z API)
2. Zbiera listę autorów (wszystkich lub z pliku)
3. Generuje osobny feed RSS dla każdego autora

Przykłady:
  %(prog)s                              # Generuj dla wszystkich autorów
  %(prog)s -a authors_config.txt        # Generuj tylko dla autorów z pliku
  %(prog)s -p config.txt                # Ogranicz programy do skanowania
        '''
    )
    parser.add_argument('-a', '--authors-file', help='Plik z listą autorów (emaile) - generuj tylko dla nich')
    parser.add_argument('-p', '--programs-file', help='Plik z ID programów do przeszukania (domyślnie: wszystkie programy z API)')
    parser.add_argument('-o', '--output-dir', default='feeds/authors', help='Katalog dla plików RSS autorów (domyślnie: feeds/authors/)')
    parser.add_argument('-n', '--max-episodes', type=int, default=50, help='Maksymalna liczba odcinków na autora (domyślnie: 50)')
    parser.add_argument('--all', action='store_true', help='Pobierz wszystkie dostępne odcinki (ignoruje -n)')
    parser.add_argument('--free-only', action='store_true', help='Pobierz tylko darmowe odcinki (bez treści dla patronów)')
    parser.add_argument('--min-episodes', type=int, default=3, help='Minimalna liczba odcinków dla wygenerowania feedu (domyślnie: 3)')
    parser.add_argument('--login', action='store_true', help='Zaloguj się (dla treści tylko dla patronów)')
    parser.add_argument('--login-email', help='Email do logowania (dla treści patronów)')
    parser.add_argument('--login-password', help='Hasło do logowania (dla treści patronów)')
    parser.add_argument('--token-file', help=f'Plik z tokenami (domyślnie: {TOKEN_FILE})')
    parser.add_argument('--list-only', action='store_true', help='Tylko wyświetl listę autorów (nie generuj feedów)')
    
    args = parser.parse_args()
    
    args = parser.parse_args()
    
    # KROK 1: Ustal listę programów do przeszukania
    if args.programs_file:
        # Użytkownik podał konkretny plik z programami
        program_ids = load_program_ids(args.programs_file)
        if not program_ids:
            print(f"✗ Brak programów w pliku {args.programs_file} lub plik nie istnieje")
            return 1
        print(f"✓ Wczytano {len(program_ids)} programów z {args.programs_file}\n")
    else:
        # Domyślnie: pobierz wszystkie programy z API
        all_programs = fetch_all_programs()
        if not all_programs:
            print("✗ Nie udało się pobrać programów z API")
            return 1
        program_ids = [str(prog['id']) for prog in all_programs]
        print(f"✓ Przeszukiwane będą wszystkie {len(program_ids)} programy z API")
        print(f"   (użyj -p plik.txt aby ograniczyć do konkretnych programów)\n")
    
    # Inicjalizuj autoryzację
    token_file = Path(args.token_file) if args.token_file else TOKEN_FILE
    auth = Auth(token_file)
    
    # Logowanie
    if args.login:
        email = args.login_email or input("Email: ")
        password = args.login_password or getpass.getpass("Hasło: ")
        
        if auth.login(email, password):
            print("✓ Zalogowano pomyślnie\n")
        else:
            print("✗ Logowanie nie powiodło się\n")
            auth = None
    
    # Zbuduj cache odcinków
    episodes_cache = build_episodes_cache(program_ids)
    
    # KROK 2: Ustal listę autorów do przetworzenia
    if args.authors_file:
        # Wczytaj autorów z pliku
        author_ids = load_author_ids(args.authors_file)
        if not author_ids:
            print(f"✗ Brak autorów w pliku {args.authors_file} lub plik nie istnieje")
            return 1
        
        print(f"\n✓ Wczytano {len(author_ids)} autorów z {args.authors_file}")
        
        # Utwórz listę autorów (bez pełnego skanowania - tylko z cache)
        authors = []
        for author_id in author_ids:
            # Policz odcinki z cache
            episode_count = 0
            programs_set = set()
            author_name = None
            
            for prog_id, cache_data in episodes_cache.items():
                for episode in cache_data['episodes']:
                    team = episode.get("team") or []
                    for member in team:
                        if not member:
                            continue
                        member_email = (member.get("email") or "").strip()
                        member_name = (member.get("name") or "").strip()
                        
                        if member_email == author_id:
                            if not author_name:
                                author_name = member_name
                            episode_count += 1
                            programs_set.add(cache_data['program_name'])
                            break
            
            if episode_count > 0:
                authors.append({
                    'id': author_id,
                    'name': author_name or author_id,
                    'episode_count': episode_count,
                    'programs': sorted(list(programs_set))
                })
            else:
                print(f"  ⚠ Nie znaleziono odcinków dla: {author_id}")
        
        print(f"✓ Znaleziono {len(authors)} autorów z odcinkami")
    else:
        # Zbierz listę wszystkich autorów
        print(f"\nZbieranie listy autorów...")
        authors = collect_all_authors(program_ids)
    
    print(f"\n{'='*60}")
    print(f"Znaleziono {len(authors)} unikalnych autorów")
    print(f"{'='*60}\n")
    
    # Filtruj autorów po minimalnej liczbie odcinków
    authors_to_generate = [a for a in authors if a['episode_count'] >= args.min_episodes]
    
    if args.list_only:
        print("Lista autorów:")
        print(f"{'='*60}")
        for i, author in enumerate(authors_to_generate, 1):
            programs_str = ", ".join(author['programs'][:3])
            if len(author['programs']) > 3:
                programs_str += f" (+{len(author['programs'])-3} więcej)"
            print(f"{i:3d}. {author['name']:<30} ({author['episode_count']:3d} odcinków)")
            print(f"      Programy: {programs_str}")
        print(f"{'='*60}")
        return 0
    
    # Upewnij się, że katalog wyjściowy istnieje
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    
    # Ustal parametry
    if args.all:
        max_episodes = 99999
    else:
        max_episodes = args.max_episodes
    
    include_exclusive = not args.free_only
    
    print(f"\nAutorzy do wygenerowania: {len(authors_to_generate)}")
    print(f"Minimalna liczba odcinków: {args.min_episodes}")
    print(f"Maksymalna liczba odcinków na autora: {max_episodes if max_episodes < 99999 else 'wszystkie'}")
    print(f"Katalog wyjściowy: {args.output_dir}")
    if args.free_only:
        print(f"Tryb: tylko darmowe odcinki")
    else:
        print(f"Tryb: wszystkie odcinki (włącznie z treściami dla patronów)")
    print(f"{'='*60}\n")
    
    # Generuj feedy
    success_count = 0
    error_count = 0
    
    for i, author_data in enumerate(authors_to_generate, 1):
        author_name = author_data['name']
        author_email = author_data['email']
        
        print(f"[{i}/{len(authors_to_generate)}] {author_name} ({author_data['episode_count']} odcinków)")
        
        # Zbierz odcinki autora (używając cache)
        episodes = collect_episodes_by_author_optimized(
            author_email,  # Używamy email jako ID
            program_ids,
            episodes_cache,
            max_total_episodes=max_episodes,
            include_exclusive=include_exclusive
        )
        
        if not episodes:
            print(f"  └─ ⚠ Brak odcinków po filtrowaniu\n")
            error_count += 1
            continue
        
        print(f"  └─ Znaleziono {len(episodes)} odcinków")
        
        # Wygeneruj nazwę pliku
        filename_slug = slugify(author_name) or author_email.split('@')[0]
        output_file = os.path.join(args.output_dir, f"{filename_slug}.xml")
        
        print(f"  └─ Plik: {output_file}")
        
        # Generuj feed
        try:
            success = generate_author_rss_feed(
                author_email,  # ID autora (email)
                author_name,   # Nazwa autora
                episodes,
                output_file,
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
    
    return 0

if __name__ == "__main__":
    exit(main())
