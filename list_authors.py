#!/usr/bin/env python3
"""
Lista wszystkich autorów z Radia 357
Skanuje programy i wyświetla listę unikalnych autorów wraz z ich ID
"""

import requests
import json
import sys
from pathlib import Path
import argparse

API_BASE = "https://static.radio357.pl/api/content/v1"

def get_program_info(program_id):
    """Pobierz informacje o programie"""
    url = f"{API_BASE}/programs/{program_id}"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json()

def get_program_episodes(program_id, page=0):
    """Pobierz listę odcinków programu"""
    url = f"{API_BASE}/programs/{program_id}/podcasts"
    params = {"page": page}
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()

def fetch_all_episodes_from_program(program_id, max_episodes_per_program=500):
    """Pobierz wszystkie odcinki z jednego programu"""
    all_episodes = []
    page = 0
    
    while len(all_episodes) < max_episodes_per_program:
        try:
            data = get_program_episodes(program_id, page)
            
            if "_embedded" in data and "podcasts" in data["_embedded"]:
                episodes = data["_embedded"]["podcasts"]
                if not episodes:
                    break
                    
                all_episodes.extend(episodes)
                
                if len(episodes) < 250:
                    break
                    
                page += 1
            else:
                break
                
        except Exception as e:
            break
    
    return all_episodes[:max_episodes_per_program]

def fetch_all_programs():
    """Pobierz wszystkie programy z API"""
    all_programs = []
    page = 0
    
    print("Pobieranie listy wszystkich programów z API...")
    
    while True:
        try:
            url = f"{API_BASE}/programs?page={page}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if "_embedded" in data and "programs" in data["_embedded"]:
                programs = data["_embedded"]["programs"]
                if not programs:
                    break
                
                all_programs.extend(programs)
                
                # Sprawdź paginację
                if "page" in data and "total" in data:
                    total = data["total"]
                    if len(all_programs) >= total:
                        break
                
                # Jeśli mniej niż standard, to koniec
                if len(programs) < 250:
                    break
                    
                page += 1
            else:
                break
                
        except Exception as e:
            print(f"✗ Błąd pobierania programów (strona {page}): {e}")
            break
    
    print(f"✓ Pobrano {len(all_programs)} programów z API\n")
    return all_programs

def load_program_ids(config_file):
    """Wczytaj listę ID programów z pliku tekstowego"""
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            program_ids = []
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if line.isdigit():
                    program_ids.append(line)
            return program_ids
    except FileNotFoundError:
        print(f"✗ Nie znaleziono pliku konfiguracyjnego: {config_file}")
        return None

def load_author_ids(authors_file):
    """Wczytaj listę ID autorów (emaile) z pliku tekstowego"""
    try:
        with open(authors_file, 'r', encoding='utf-8') as f:
            author_ids = []
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                # Proste sprawdzenie czy wygląda jak email
                if '@' in line:
                    author_ids.append(line)
            return author_ids
    except FileNotFoundError:
        print(f"✗ Nie znaleziono pliku z autorami: {authors_file}")
        return None

def collect_all_authors(program_ids):
    """Zbierz listę wszystkich autorów ze wszystkich programów"""
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
                if not member:
                    continue
                author_name = (member.get("name") or "").strip()
                author_email = (member.get("email") or "").strip()
                
                if author_email and author_name:
                    # Użyj email jako unikalnego ID
                    if author_email not in authors_dict:
                        authors_dict[author_email] = {
                            'name': author_name,
                            'email': author_email,
                            'episode_count': 0,
                            'programs': set()
                        }
                    
                    authors_dict[author_email]['episode_count'] += 1
                    authors_dict[author_email]['programs'].add(program_name)
    
    # Konwertuj do listy i sortuj
    authors_list = []
    for email, data in authors_dict.items():
        authors_list.append({
            'id': email,  # email jako ID
            'name': data['name'],
            'email': data['email'],
            'episode_count': data['episode_count'],
            'programs': sorted(list(data['programs']))
        })
    
    # Sortuj po liczbie odcinków (malejąco)
    authors_list.sort(key=lambda x: x['episode_count'], reverse=True)
    
    return authors_list

def display_authors(authors, show_details=False):
    """Wyświetl listę autorów"""
    print(f"\n{'='*80}")
    print(f"LISTA AUTORÓW ")
    print(f"{'='*80}\n")
    
    if not authors:
        print("Brak autorów do wyświetlenia")
        return
    
    print(f"Znaleziono {len(authors)} unikalnych autorów:\n")
    
    for i, author in enumerate(authors, 1):
        print(f"{i:3d}. {author['name']:<35} ({author['episode_count']:3d} odcinków)")
        
        if show_details:
            print(f"     ID: {author['id']}")
            programs_str = ", ".join(author['programs'][:3])
            if len(author['programs']) > 3:
                programs_str += f" (+{len(author['programs'])-3} więcej)"
            print(f"     Programy: {programs_str}")
            print()
    
    print(f"\n{'='*80}")

def save_authors_json(authors, output_file):
    """Zapisz listę autorów do pliku JSON"""
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(authors, f, ensure_ascii=False, indent=2)
    print(f"\n✓ Lista autorów zapisana do: {output_file}")

def main():
    parser = argparse.ArgumentParser(
        description='Lista wszystkich autorów z Radio 357',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Przykłady użycia:
  %(prog)s                              # Wyświetl listę autorów (wszystkie programy)
  %(prog)s --details                    # Pokaż szczegóły (ID, programy)
  %(prog)s --save authors.json          # Zapisz do pliku JSON
  %(prog)s -a authors_config.txt        # Pokaż tylko autorów z pliku
  %(prog)s -p config.txt                # Ogranicz programy do skanowania
        '''
    )
    parser.add_argument('-a', '--authors-file', 
                       help='Plik z listą autorów (emaile) - wyświetl tylko tych autorów')
    parser.add_argument('-p', '--programs-file', 
                       help='Plik z ID programów do przeszukania (domyślnie: wszystkie programy z API)')
    parser.add_argument('--details', action='store_true', 
                       help='Pokaż szczegóły (ID autora, lista programów)')
    parser.add_argument('--save', metavar='FILE', 
                       help='Zapisz listę autorów do pliku JSON')
    parser.add_argument('--min-episodes', type=int, default=1,
                       help='Minimalna liczba odcinków (domyślnie: 1)')
    
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
    
    # KROK 2: Zbierz listę autorów
    if args.authors_file:
        # Wczytaj autorów z pliku i znajdź ich statystyki
        author_ids = load_author_ids(args.authors_file)
        if not author_ids:
            print(f"✗ Brak autorów w pliku {args.authors_file} lub plik nie istnieje")
            return 1
        
        print(f"✓ Wczytano {len(author_ids)} autorów z {args.authors_file}")
        print(f"Skanowanie programów w poszukiwaniu ich odcinków...\n")
        
        # Zbierz statystyki dla autorów z pliku
        authors = []
        for author_id in author_ids:
            author_data = {
                'id': author_id,
                'name': author_id,
                'episode_count': 0,
                'programs': set()
            }
            
            for i, program_id in enumerate(program_ids, 1):
                try:
                    program_info = get_program_info(program_id)
                    program_name = program_info.get("name", f"Program {program_id}")
                except:
                    continue
                
                episodes = fetch_all_episodes_from_program(program_id, max_episodes_per_program=500)
                
                for episode in episodes:
                    team = episode.get("team") or []
                    for member in team:
                        if not member:
                            continue
                        member_email = (member.get("email") or "").strip()
                        member_name = (member.get("name") or "").strip()
                        
                        if member_email == author_id:
                            if author_data['name'] == author_id and member_name:
                                author_data['name'] = member_name
                            author_data['episode_count'] += 1
                            author_data['programs'].add(program_name)
                            break
            
            if author_data['episode_count'] > 0:
                author_data['programs'] = sorted(list(author_data['programs']))
                authors.append(author_data)
            else:
                print(f"  ⚠ Nie znaleziono odcinków dla: {author_id}")
        
        print(f"\n✓ Znaleziono {len(authors)} autorów z odcinkami")
    else:
        # Zbierz listę wszystkich autorów
        authors = collect_all_authors(program_ids)
    
    if not authors:
        print("\n✗ Nie znaleziono żadnych autorów")
        return 1
    
    # Filtruj po minimalnej liczbie odcinków
    if args.min_episodes > 1:
        authors = [a for a in authors if a['episode_count'] >= args.min_episodes]
    
    # Wyświetl listę
    display_authors(authors, show_details=args.details)
    
    # Zapisz do pliku JSON jeśli podano
    if args.save:
        save_authors_json(authors, args.save)
    
    return 0

if __name__ == "__main__":
    exit(main())
