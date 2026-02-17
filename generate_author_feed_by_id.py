#!/usr/bin/env python3
"""
Generator RSS dla odcinków konkretnego autora z Radia 357 (po ID autora)
"""

import requests
import json
from datetime import datetime
import argparse
import getpass
import os
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom
import re

API_BASE = "https://static.radio357.pl/api/content/v1"
GATEWAY_BASE = "https://gateway.r357.eu/api"
AUTH_BASE = "https://auth.r357.eu/api"
TOKEN_FILE = Path.home() / ".radio357_token"

class Auth:
    """Klasa do zarządzania autoryzacją"""
    def __init__(self, token_file=TOKEN_FILE):
        self.token_file = token_file
        self.access_token = None
        self.refresh_token = None
        self.load_tokens()
    
    def load_tokens(self):
        if self.token_file.exists():
            try:
                with open(self.token_file, 'r') as f:
                    data = json.load(f)
                    self.access_token = data.get('accessToken')
                    self.refresh_token = data.get('refreshToken')
            except:
                pass
    
    def save_tokens(self, access_token, refresh_token):
        self.access_token = access_token
        self.refresh_token = refresh_token
        try:
            with open(self.token_file, 'w') as f:
                json.dump({'accessToken': access_token, 'refreshToken': refresh_token}, f)
            os.chmod(self.token_file, 0o600)
        except:
            pass
    
    def login(self, email, password):
        url = f"{AUTH_BASE}/auth/login"
        try:
            resp = requests.post(url, json={"email": email, "password": password}, timeout=10)
            if resp.status_code == 200:
                result = resp.json()
                self.save_tokens(result.get('accessToken'), result.get('refreshToken'))
                return True
        except:
            pass
        return False
    
    def refresh(self):
        if not self.refresh_token:
            return False
        url = f"{AUTH_BASE}/auth/refresh"
        try:
            resp = requests.post(url, json={"refreshToken": self.refresh_token}, timeout=10)
            if resp.status_code == 200:
                result = resp.json()
                self.save_tokens(result.get('accessToken'), result.get('refreshToken'))
                return True
        except:
            pass
        return False
    
    def get_headers(self):
        if self.access_token:
            return {"Authorization": f"Bearer {self.access_token}"}
        return {}
    
    def is_authenticated(self):
        return self.access_token is not None

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

def get_audio_url(podcast_id, auth=None):
    """Pobierz URL do pliku audio dla danego odcinka"""
    url = f"{GATEWAY_BASE}/content/podcast/{podcast_id}/url"
    headers = auth.get_headers() if auth else {}
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("url")
        elif resp.status_code == 401 and auth and auth.is_authenticated():
            if auth.refresh():
                headers = auth.get_headers()
                resp = requests.get(url, headers=headers, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("url")
        return None
    except:
        return None

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
    
    print(f"✓ Pobrano {len(all_programs)} programów z API")
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

def collect_episodes_by_author_id(author_id, program_ids, max_total_episodes=100, include_exclusive=False):
    """Zbierz odcinki konkretnego autora (po ID = email)"""
    author_episodes = []
    author_name = None
    programs_scanned = 0
    
    print(f"\nSzukam odcinków autora o ID: {author_id}")
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
        
        # Filtruj odcinki po autorze
        matching_count = 0
        for episode in episodes:
            # Sprawdź autorów
            team = episode.get("team") or []
            
            # Sprawdź czy któryś z członków zespołu ma dany email
            for member in team:
                if not member:
                    continue
                member_email = (member.get("email") or "").strip()
                member_name = (member.get("name") or "").strip()
                
                if member_email == author_id:
                    # Zapisz nazwę autora (z pierwszego znalezionego odcinka)
                    if not author_name:
                        author_name = member_name
                    
                    # Sprawdź czy to darmowy odcinek
                    is_free = episode.get("isFree", True)
                    
                    if is_free or include_exclusive:
                        # Dodaj informacje o programie do odcinka
                        episode["_program_name"] = program_name
                        episode["_program_id"] = program_id
                        episode["_program_image"] = program_image
                        author_episodes.append(episode)
                        matching_count += 1
                    
                    break  # Znaleziono autora w tym odcinku, przejdź do następnego
        
        if matching_count > 0:
            print(f"  └─ Znaleziono: {matching_count} odcinków")
        
        programs_scanned += 1
        
        # Jeśli mamy już wystarczająco dużo odcinków, możemy przerwać
        if len(author_episodes) >= max_total_episodes:
            break
    
    # Sortuj odcinki po dacie publikacji (od najnowszych)
    author_episodes.sort(key=lambda x: x.get("publishedAt", 0), reverse=True)
    
    # Ogranicz do max_total_episodes
    author_episodes = author_episodes[:max_total_episodes]
    
    print(f"\n{'='*60}")
    print(f"Przeskanowano programów: {programs_scanned}/{len(program_ids)}")
    print(f"Znaleziono odcinków: {len(author_episodes)}")
    if author_name:
        print(f"Autor: {author_name}")
    print(f"{'='*60}\n")
    
    return author_episodes, author_name

def collect_episodes_by_author_id_from_cache(author_id, episodes_cache, max_total_episodes=100, include_exclusive=False):
    """
    Zbierz odcinki konkretnego autora (po ID = email) z cache.
    Ta funkcja używa cache zbudowanego w collect_all_authors_for_selection(),
    co eliminuje potrzebę ponownego skanowania programów.
    
    Args:
        author_id: Email autora
        episodes_cache: Dict {program_id: {'program_name': str, 'program_image': str, 'episodes': list}}
        max_total_episodes: Maksymalna liczba odcinków do zwrócenia
        include_exclusive: Czy uwzględnić odcinki płatne
        
    Returns:
        Tuple: (author_episodes, author_name)
    """
    author_episodes = []
    author_name = None
    
    print(f"\nFiltrowanie odcinków autora z cache...")
    
    for program_id, cache_data in episodes_cache.items():
        episodes = cache_data['episodes']
        
        # Filtruj odcinki po autorze (po email)
        for episode in episodes:
            # Sprawdź autorów w team
            team = episode.get("team") or []
            has_author = False
            
            for member in team:
                if not member:
                    continue
                member_email = (member.get("email") or "").strip()
                member_name = (member.get("name") or "").strip()
                
                if member_email == author_id:
                    # Zapisz nazwę autora (z pierwszego znalezionego odcinka)
                    if not author_name:
                        author_name = member_name
                    
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
    
    print(f"Znaleziono odcinków: {len(author_episodes)}")
    if author_name:
        print(f"Autor: {author_name}\n")
    
    return author_episodes, author_name

def slugify(text):
    """Konwertuj tekst na slug (nazwa_pliku)"""
    replacements = {
        'ą': 'a', 'ć': 'c', 'ę': 'e', 'ł': 'l', 'ń': 'n', 
        'ó': 'o', 'ś': 's', 'ź': 'z', 'ż': 'z',
        'Ą': 'A', 'Ć': 'C', 'Ę': 'E', 'Ł': 'L', 'Ń': 'N',
        'Ó': 'O', 'Ś': 'S', 'Ź': 'Z', 'Ż': 'Z'
    }
    for pl, ascii in replacements.items():
        text = text.replace(pl, ascii)
    
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s-]+', '_', text)
    text = text.lower()
    text = text.strip('_')
    
    return text

def generate_author_rss_feed(author_id, author_name, episodes, output_file, include_exclusive=False, auth=None):
    """Generuj plik RSS dla odcinków danego autora"""
    
    print(f"Generowanie RSS feed dla autora: {author_name}")
    print(f"Liczba odcinków: {len(episodes)}\n")
    
    # Utwórz RSS feed
    rss = Element('rss', {
        'version': '2.0',
        'xmlns:itunes': 'http://www.itunes.com/dtds/podcast-1.0.dtd',
        'xmlns:content': 'http://purl.org/rss/1.0/modules/content/'
    })
    
    channel = SubElement(rss, 'channel')
    
    # Metadane kanału
    title = SubElement(channel, 'title')
    title.text = f"{author_name} - Radia 357"
    
    link = SubElement(channel, 'link')
    link.text = f"https://radio357.pl/podcasty/"
    
    description = SubElement(channel, 'description')
    description.text = f"Wszystkie odcinki podcastów prowadzone przez {author_name} na Radia 357"
    
    language = SubElement(channel, 'language')
    language.text = 'pl-PL'
    
    # iTunes specific
    itunes_author = SubElement(channel, 'itunes:author')
    itunes_author.text = author_name
    
    itunes_summary = SubElement(channel, 'itunes:summary')
    itunes_summary.text = f"Zbiór odcinków podcastów prowadzonych przez {author_name}"
    
    itunes_category = SubElement(channel, 'itunes:category', {'text': 'Arts'})
    
    # Dodaj odcinki
    added_count = 0
    skipped_count = 0
    
    for episode in episodes:
        episode_id = episode.get("id")
        episode_title = episode.get("title", f"Odcinek {episode_id}")
        episode_subtitle = episode.get("subTitle", "")
        episode_desc = episode.get("description", "")
        episode_desc_rich = episode.get("descriptionRich", "")
        published_at = episode.get("publishedAt", 0)
        is_free = episode.get("isFree", True)
        duration = episode.get("duration", 0)
        episode_image = episode.get("image", "")
        
        # Informacje o programie
        program_name = episode.get("_program_name", "Radio 357")
        program_id = episode.get("_program_id", "")
        program_image = episode.get("_program_image", "")
        
        # Użyj obrazka odcinka, a jeśli nie ma - obrazka programu
        item_image = episode_image or program_image
        
        # Autorzy/prowadzący
        team = episode.get("team") or []
        authors = [member.get("name", "") for member in team if member.get("name")]
        author_emails = [member.get("email", "") for member in team if member.get("email")]
        
        # Kategorie
        categories = episode.get("categories") or []
        category_names = [cat.get("name", "") for cat in categories if cat.get("name")]
        
        # Dodaj program jako kategorię
        if program_name:
            category_names.insert(0, program_name)
        
        # Pomiń treści dla patronów jeśli nie chcemy ich includować
        if not is_free and not include_exclusive:
            skipped_count += 1
            continue
        
        # Pobierz URL audio
        audio_url = get_audio_url(episode_id, auth)
        
        if not audio_url:
            if not is_free:
                print(f"  ⊘ Pominięto (tylko dla patronów): {episode_title}")
            else:
                print(f"  ✗ Brak URL audio: {episode_title}")
            skipped_count += 1
            continue
        
        # Konwertuj timestamp na RFC 2822 format
        if isinstance(published_at, int):
            pub_date = datetime.fromtimestamp(published_at / 1000)
        else:
            pub_date = datetime.now()
        
        pub_date_str = pub_date.strftime('%a, %d %b %Y %H:%M:%S +0000')
        
        # Dodaj item do RSS
        item = SubElement(channel, 'item')
        
        item_title = SubElement(item, 'title')
        # Dodaj nazwę programu do tytułu
        full_title = f"[{program_name}] {episode_title}"
        if episode_subtitle:
            full_title += f" - {episode_subtitle}"
        item_title.text = full_title
        
        item_link = SubElement(item, 'link')
        item_link.text = f"https://radio357.pl/podcasty/audycje/odcinek/{episode_id}/"
        
        item_guid = SubElement(item, 'guid', {'isPermaLink': 'false'})
        item_guid.text = f"radio357-author-{author_id}-{episode_id}"
        
        item_pubDate = SubElement(item, 'pubDate')
        item_pubDate.text = pub_date_str
        
        # Autor(zy)
        if authors:
            if author_emails:
                item_author = SubElement(item, 'author')
                item_author.text = f"{author_emails[0]} ({authors[0]})"
            
            itunes_author_item = SubElement(item, 'itunes:author')
            itunes_author_item.text = ", ".join(authors)
        
        # Kategorie
        for cat_name in category_names:
            item_category = SubElement(item, 'category')
            item_category.text = cat_name
        
        # Opis
        description_text = episode_desc_rich if episode_desc_rich else (episode_desc or episode_title)
        
        item_description = SubElement(item, 'description')
        item_description.text = description_text
        
        if episode_desc_rich:
            content_encoded = SubElement(item, 'content:encoded')
            content_encoded.text = episode_desc_rich
        
        item_enclosure = SubElement(item, 'enclosure', {
            'url': audio_url,
            'type': 'audio/mpeg'
        })
        
        # iTunes specific
        if duration > 0:
            hours = duration // 3600
            minutes = (duration % 3600) // 60
            seconds = duration % 60
            duration_str = f"{hours}:{minutes:02d}:{seconds:02d}" if hours > 0 else f"{minutes}:{seconds:02d}"
            
            itunes_duration = SubElement(item, 'itunes:duration')
            itunes_duration.text = duration_str
        
        if episode_subtitle or episode_desc:
            itunes_subtitle = SubElement(item, 'itunes:subtitle')
            itunes_subtitle.text = episode_subtitle if episode_subtitle else (episode_desc[:250] if episode_desc else "")
        
        itunes_summary = SubElement(item, 'itunes:summary')
        itunes_summary.text = episode_desc or episode_title
        
        if item_image:
            itunes_item_image = SubElement(item, 'itunes:image', {'href': item_image})
        
        added_count += 1
        print(f"  ✓ Dodano: [{program_name}] {episode_title}")
    
    # Zapisz do pliku
    xml_str = minidom.parseString(tostring(rss, encoding='utf-8')).toprettyxml(indent="  ", encoding='utf-8')
    
    # Upewnij się, że katalog istnieje
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'wb') as f:
        f.write(xml_str)
    
    print(f"\n{'='*60}")
    print(f"✓ RSS feed zapisany: {output_file}")
    print(f"  Dodano odcinków: {added_count}")
    print(f"  Pominięto: {skipped_count}")
    print(f"{'='*60}")
    
    return True

def collect_all_authors_for_selection(program_ids):
    """
    Zbierz listę autorów do wyboru interaktywnego.
    Zwraca również cache z odcinkami, żeby uniknąć ponownego skanowania.
    
    Returns:
        Tuple: (authors_list, episodes_cache)
        - authors_list: Lista autorów do wyboru
        - episodes_cache: Dict {program_id: {'program_name': str, 'program_image': str, 'episodes': list}}
    """
    authors_dict = {}
    episodes_cache = {}  # Cache odcinków dla ponownego użycia
    
    print(f"Skanowanie programów w poszukiwaniu autorów...")
    print(f"Programy do przeskanowania: {len(program_ids)}\n")
    
    for i, program_id in enumerate(program_ids, 1):
        try:
            program_info = get_program_info(program_id)
            program_name = program_info.get("name", f"Program {program_id}")
            program_image = program_info.get("image", "")
        except Exception as e:
            continue
        
        print(f"[{i}/{len(program_ids)}] {program_name}")
        
        episodes = fetch_all_episodes_from_program(program_id, max_episodes_per_program=500)
        
        # Dodaj informacje o programie do każdego odcinka
        for episode in episodes:
            episode["_program_name"] = program_name
            episode["_program_id"] = program_id
            episode["_program_image"] = program_image
        
        # Zapisz do cache
        episodes_cache[program_id] = {
            'program_name': program_name,
            'program_image': program_image,
            'episodes': episodes
        }
        
        # Zbierz autorów z odcinków
        for episode in episodes:
            team = episode.get("team") or []
            for member in team:
                if not member:
                    continue
                author_name = (member.get("name") or "").strip()
                author_email = (member.get("email") or "").strip()
                
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
    
    authors_list = []
    for email, data in authors_dict.items():
        authors_list.append({
            'id': email,
            'name': data['name'],
            'episode_count': data['episode_count'],
            'programs': sorted(list(data['programs']))
        })
    
    authors_list.sort(key=lambda x: x['episode_count'], reverse=True)
    
    return authors_list, episodes_cache

def display_authors_for_selection(authors):
    """Wyświetl listę autorów do wyboru"""
    print(f"\n{'='*80}")
    print(f"WYBIERZ AUTORA")
    print(f"{'='*80}\n")
    print(f"Znaleziono {len(authors)} autorów:\n")
    
    for i, author in enumerate(authors, 1):
        programs_preview = ", ".join(author['programs'][:2])
        if len(author['programs']) > 2:
            programs_preview += "..."
        print(f"{i:3d}. {author['name']:<30} ({author['episode_count']:3d} odcinków) - {programs_preview}")
    
    print(f"\n{'='*80}")

def main():
    parser = argparse.ArgumentParser(
        description='Generowanie RSS feed dla odcinków autora z Radia 357 (po ID)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Przykłady użycia:
  # Interaktywny wybór (skanuj wszystkie programy, znajdź wszystkich autorów):
  %(prog)s
  
  # Z podanym ID autora:
  %(prog)s piotr.kaczkowski@radio357.pl
  %(prog)s rafal.bryndal@radio357.pl -o feeds/bryndal.xml
  
  # Wybór z listy autorów z pliku:
  %(prog)s -a authors_config.txt
  
  # Ograniczenie programów do skanowania:
  %(prog)s -p config.txt
        '''
    )
    parser.add_argument('author_id', nargs='?', help='ID autora (adres email) - opcjonalny, jeśli nie podano zostanie wyświetlona lista')
    parser.add_argument('-a', '--authors-file', help='Plik z listą autorów (emaile) do wyboru w trybie interaktywnym')
    parser.add_argument('-p', '--programs-file', help='Plik z ID programów do przeszukania (domyślnie: wszystkie programy z API)')
    parser.add_argument('-o', '--output', help='Nazwa pliku wyjściowego (domyślnie: feeds/{autor_slug}.xml)')
    parser.add_argument('-n', '--max-episodes', type=int, default=300, help='Maksymalna liczba odcinków (domyślnie: 300)')
    parser.add_argument('--all', action='store_true', help='Pobierz wszystkie dostępne odcinki (ignoruje -n)')
    parser.add_argument('--free-only', action='store_true', help='Pobierz tylko darmowe odcinki (bez treści dla patronów)')
    parser.add_argument('--login', action='store_true', help='Zaloguj się (dla treści tylko dla patronów)')
    parser.add_argument('--login-email', help='Email do logowania (dla treści patronów)')
    parser.add_argument('--login-password', help='Hasło do logowania (dla treści patronów)')
    parser.add_argument('--token-file', help=f'Plik z tokenami (domyślnie: {TOKEN_FILE})')
    
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
    
    # KROK 2: Ustal ID autora
    author_id = args.author_id
    episodes_cache = None  # Cache odcinków dla trybu interaktywnego
    
    if not author_id:
        # Tryb interaktywny - wybór autora z listy
        print("\n" + "="*80)
        print("TRYB INTERAKTYWNY - Wybierz autora")
        print("="*80 + "\n")
        
        if args.authors_file:
            # Wczytaj listę autorów z pliku
            author_ids = load_author_ids(args.authors_file)
            if not author_ids:
                print(f"✗ Brak autorów w pliku {args.authors_file} lub plik nie istnieje")
                return 1
            
            # Utwórz prostą listę do wyboru (bez skanowania programów - będą pokazane tylko emaile)
            print(f"Wczytano {len(author_ids)} autorów z {args.authors_file}\n")
            print(f"Wybierz autora:\n")
            for i, email in enumerate(author_ids, 1):
                print(f"{i:3d}. {email}")
            
            print(f"\n{'='*80}")
            
            # Zapytaj o wybór
            try:
                choice_input = input(f"\nWybierz numer autora (1-{len(author_ids)}) [Enter = anuluj]: ")
                
                if not choice_input.strip():
                    print("Anulowano.")
                    return 0
                
                choice = int(choice_input)
                
                if choice < 1 or choice > len(author_ids):
                    print(f"✗ Nieprawidłowy numer. Wybierz od 1 do {len(author_ids)}")
                    return 1
                
                author_id = author_ids[choice - 1]
                print(f"\n✓ Wybrano: {author_id}\n")
                
            except ValueError:
                print("✗ Podaj prawidłowy numer")
                return 1
            except KeyboardInterrupt:
                print("\n\nAnulowano.")
                return 0
        
        else:
            # Skanuj programy i znajdź wszystkich autorów
            # Zbierz listę autorów (wraz z cache odcinków)
            authors, episodes_cache = collect_all_authors_for_selection(program_ids)
            
            if not authors:
                print("\n✗ Nie znaleziono żadnych autorów")
                return 1
            
            # Wyświetl listę
            display_authors_for_selection(authors)
            
            # Zapytaj o wybór
            try:
                choice_input = input("\nWybierz numer autora (1-{}) [Enter = anuluj]: ".format(len(authors)))
                
                if not choice_input.strip():
                    print("Anulowano.")
                    return 0
                
                choice = int(choice_input)
                
                if choice < 1 or choice > len(authors):
                    print(f"✗ Nieprawidłowy numer. Wybierz od 1 do {len(authors)}")
                    return 1
                
                selected_author = authors[choice - 1]
                author_id = selected_author['id']
                author_name = selected_author['name']
                
                print(f"\n✓ Wybrano: {author_name} ({author_id})")
                print(f"  Odcinków: {selected_author['episode_count']}")
                print()
                
            except ValueError:
                print("✗ Podaj prawidłowy numer")
                return 1
            except KeyboardInterrupt:
                print("\n\nAnulowano.")
                return 0
    
    # KROK 3: Zbierz odcinki autora
    if args.all:
        max_episodes = 99999
    else:
        max_episodes = args.max_episodes
    
    include_exclusive = not args.free_only
    
    # Zbierz odcinki autora
    # W trybie interaktywnym (episodes_cache != None) używamy cache, żeby nie skanować ponownie
    if episodes_cache is not None:
        # Tryb interaktywny z cache - nie skanujemy ponownie
        episodes, author_name = collect_episodes_by_author_id_from_cache(
            author_id,
            episodes_cache,
            max_total_episodes=max_episodes,
            include_exclusive=include_exclusive
        )
    else:
        # Tryb bezpośredni (podano author_id) - skanujemy programy
        episodes, author_name = collect_episodes_by_author_id(
            author_id,
            program_ids,
            max_total_episodes=max_episodes,
            include_exclusive=include_exclusive
        )
    
    if not episodes:
        print(f"✗ Nie znaleziono żadnych odcinków autora o ID: {author_id}")
        return 1
    
    if not author_name:
        author_name = author_id  # Fallback do ID jeśli nie znaleziono nazwy
    
    # Wygeneruj nazwę pliku wyjściowego
    if args.output:
        output_file = args.output
    else:
        author_slug = slugify(author_name)
        if not author_slug:
            author_slug = "autor"
        output_file = f"feeds/{author_slug}.xml"
    
    # Generuj feed
    generate_author_rss_feed(
        author_id,
        author_name,
        episodes,
        output_file,
        include_exclusive=include_exclusive,
        auth=auth
    )
    
    return 0

if __name__ == "__main__":
    exit(main())
