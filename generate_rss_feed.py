#!/usr/bin/env python3
"""
Generator RSS dla podcastów z Radia 357
Pozwala stworzyć własny plik RSS do subskrypcji w aplikacjach podcastowych
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

API_BASE = "https://static.radio357.pl/api/content/v1"
GATEWAY_BASE = "https://gateway.r357.eu/api"
AUTH_BASE = "https://auth.r357.eu/api"
TOKEN_FILE = Path.home() / ".radio357_token"

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

def fetch_all_episodes(program_id, max_episodes=100):
    """Pobierz wszystkie odcinki programu (z limitem)"""
    all_episodes = []
    page = 0
    
    while len(all_episodes) < max_episodes:
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
            print(f"Błąd pobierania strony {page}: {e}")
            break
    
    return all_episodes[:max_episodes]

def generate_rss_feed(program_id, output_file, max_episodes=50, include_exclusive=False, auth=None):
    """Generuj plik RSS dla danego programu"""
    
    print(f"Generowanie RSS feed dla programu ID: {program_id}")
    
    # Pobierz informacje o programie
    try:
        program_info = get_program_info(program_id)
        program_name = program_info.get("name", "3odca57er")
        program_desc = program_info.get("desc", "")
        program_image = program_info.get("image", "")
    except Exception as e:
        print(f"✗ Błąd pobierania informacji o programie: {e}")
        return False
    
    print(f"Program: {program_name}")
    
    # Pobierz odcinki
    print(f"Pobieranie odcinków (maksymalnie {max_episodes})...")
    episodes = fetch_all_episodes(program_id, max_episodes)
    print(f"Znaleziono: {len(episodes)} odcinków")
    
    # Utwórz RSS feed
    rss = Element('rss', {
        'version': '2.0',
        'xmlns:itunes': 'http://www.itunes.com/dtds/podcast-1.0.dtd',
        'xmlns:content': 'http://purl.org/rss/1.0/modules/content/'
    })
    
    channel = SubElement(rss, 'channel')
    
    # Metadane kanału
    title = SubElement(channel, 'title')
    title.text = program_name
    
    link = SubElement(channel, 'link')
    link.text = f"https://radio357.pl/podcasty/audycje/"
    
    description = SubElement(channel, 'description')
    description.text = program_desc or f"Podcast {program_name} z Radio 357"
    
    language = SubElement(channel, 'language')
    language.text = 'pl-PL'
    
    if program_image:
        image = SubElement(channel, 'image')
        image_url = SubElement(image, 'url')
        image_url.text = program_image
        image_title = SubElement(image, 'title')
        image_title.text = program_name
        image_link = SubElement(image, 'link')
        image_link.text = f"https://radio357.pl/"
    
    # iTunes specific
    itunes_author = SubElement(channel, 'itunes:author')
    itunes_author.text = "Radio 357"
    
    itunes_summary = SubElement(channel, 'itunes:summary')
    itunes_summary.text = program_desc or f"Podcast {program_name}"
    
    if program_image:
        itunes_image = SubElement(channel, 'itunes:image', {'href': program_image})
    
    itunes_category = SubElement(channel, 'itunes:category', {'text': 'Arts'})
    
    # Dodaj odcinki
    added_count = 0
    skipped_count = 0
    
    for episode in episodes:
        episode_id = episode.get("id")
        episode_title = episode.get("title", f"Odcinek {episode_id}")
        episode_desc = episode.get("desc", "")
        published_at = episode.get("publishedAt", 0)
        is_free = episode.get("isFree", True)
        duration = episode.get("duration", 0)
        episode_image = episode.get("image", program_image)
        
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
        item_title.text = episode_title
        
        item_link = SubElement(item, 'link')
        item_link.text = f"https://radio357.pl/podcasty/audycje/odcinek/{episode_id}/"
        
        item_guid = SubElement(item, 'guid', {'isPermaLink': 'false'})
        item_guid.text = f"radio357-{program_id}-{episode_id}"
        
        item_pubDate = SubElement(item, 'pubDate')
        item_pubDate.text = pub_date_str
        
        item_description = SubElement(item, 'description')
        item_description.text = episode_desc or episode_title
        
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
        
        itunes_summary = SubElement(item, 'itunes:summary')
        itunes_summary.text = episode_desc or episode_title
        
        if episode_image:
            itunes_item_image = SubElement(item, 'itunes:image', {'href': episode_image})
        
        added_count += 1
        print(f"  ✓ Dodano: {episode_title}")
    
    # Zapisz do pliku
    xml_str = minidom.parseString(tostring(rss, encoding='utf-8')).toprettyxml(indent="  ", encoding='utf-8')
    
    with open(output_file, 'wb') as f:
        f.write(xml_str)
    
    print(f"\n{'='*60}")
    print(f"✓ RSS feed zapisany: {output_file}")
    print(f"  Dodano odcinków: {added_count}")
    print(f"  Pominięto: {skipped_count}")
    print(f"{'='*60}")
    
    return True

def main():
    parser = argparse.ArgumentParser(
        description='Generowanie RSS feed dla podcastów Radia 357'
    )
    parser.add_argument('program_id', help='ID programu')
    parser.add_argument('-o', '--output', default='radio357_feed.xml', help='Nazwa pliku wyjściowego (domyślnie: radio357_feed.xml)')
    parser.add_argument('-n', '--max-episodes', type=int, default=50, help='Maksymalna liczba odcinków (domyślnie: 50)')
    parser.add_argument('--include-exclusive', action='store_true', help='Dołącz treści tylko dla patronów (mogą nie działać bez autoryzacji)')
    parser.add_argument('--login', action='store_true', help='Zaloguj się (dla treści tylko dla patronów)')
    parser.add_argument('--email', help='Email do logowania')
    parser.add_argument('--password', help='Hasło')
    parser.add_argument('--token-file', help=f'Plik z tokenami (domyślnie: {TOKEN_FILE})')
    
    args = parser.parse_args()
    
    # Inicjalizuj autoryzację
    token_file = Path(args.token_file) if args.token_file else TOKEN_FILE
    auth = Auth(token_file)
    
    # Logowanie
    if args.login:
        email = args.email or input("Email: ")
        password = args.password or getpass.getpass("Hasło: ")
        
        if auth.login(email, password):
            print("✓ Zalogowano pomyślnie\n")
            # Automatycznie włącz treści tylko dla patronów przy logowaniu
            if not args.include_exclusive:
                args.include_exclusive = True
                print("ℹ️  Automatycznie włączono treści tylko dla patronów (użyto --login)\n")
        else:
            print("✗ Logowanie nie powiodło się\n")
            auth = None
    
    generate_rss_feed(
        args.program_id,
        args.output,
        max_episodes=args.max_episodes,
        include_exclusive=args.include_exclusive,
        auth=auth
    )

if __name__ == "__main__":
    main()
