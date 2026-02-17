#!/usr/bin/env python3
"""
Skrypt do pobierania plików audio z RSS feed
Wczytuje plik XML z feedem i pobiera wszystkie odcinki
Obsługuje zarówno bezpośrednie linki MP3 jak i strumienie HLS (m3u8)
Automatycznie używa autoryzacji Radia 357 jeśli dostępna
"""

import requests
import xml.etree.ElementTree as ET
import argparse
import os
from pathlib import Path
from urllib.parse import urlparse, unquote
import time
import re
import sys
import json
import getpass

# API endpoints dla Radia 357
GATEWAY_BASE = "https://gateway.r357.eu/api"
AUTH_BASE = "https://auth.r357.eu/api"
TOKEN_FILE = Path.home() / ".radio357_token"

class Auth:
    """Klasa do zarządzania autoryzacją Radia 357"""
    def __init__(self, token_file=TOKEN_FILE):
        self.token_file = token_file
        self.access_token = None
        self.refresh_token = None
        self.load_tokens()
    
    def load_tokens(self):
        """Wczytaj tokeny z pliku"""
        if self.token_file.exists():
            try:
                with open(self.token_file, 'r') as f:
                    data = json.load(f)
                    self.access_token = data.get('accessToken')
                    self.refresh_token = data.get('refreshToken')
            except Exception:
                pass
    
    def save_tokens(self, access_token, refresh_token):
        """Zapisz tokeny do pliku"""
        self.access_token = access_token
        self.refresh_token = refresh_token
        
        try:
            with open(self.token_file, 'w') as f:
                json.dump({
                    'accessToken': access_token,
                    'refreshToken': refresh_token
                }, f)
            # Ustaw uprawnienia tylko do odczytu dla właściciela
            try:
                import platform
                if platform.system() != 'Windows':
                    os.chmod(self.token_file, 0o600)
            except Exception:
                pass
        except Exception:
            pass
    
    def login(self, email, password):
        """Zaloguj się i pobierz tokeny"""
        url = f"{AUTH_BASE}/auth/login"
        data = {"email": email, "password": password}
        
        try:
            resp = requests.post(url, json=data, timeout=10)
            
            if resp.status_code == 200:
                result = resp.json()
                self.save_tokens(
                    result.get('accessToken'),
                    result.get('refreshToken')
                )
                return True
            else:
                return False
        except Exception:
            return False
    
    def refresh(self):
        """Odśwież token dostępu"""
        if not self.refresh_token:
            return False
        
        url = f"{AUTH_BASE}/auth/refresh"
        data = {"refreshToken": self.refresh_token}
        
        try:
            resp = requests.post(url, json=data, timeout=10)
            
            if resp.status_code == 200:
                result = resp.json()
                self.save_tokens(
                    result.get('accessToken'),
                    result.get('refreshToken')
                )
                return True
            else:
                return False
        except:
            return False
    
    def get_headers(self):
        """Zwróć nagłówki z tokenem autoryzacji"""
        if self.access_token:
            return {"Authorization": f"Bearer {self.access_token}"}
        return {}
    
    def is_authenticated(self):
        """Sprawdź czy użytkownik jest zalogowany"""
        return self.access_token is not None

def get_audio_url_from_api(podcast_id, auth=None, verbose=False):
    """Pobierz URL do pliku audio przez API (z autoryzacją)"""
    url = f"{GATEWAY_BASE}/content/podcast/{podcast_id}/url"
    headers = auth.get_headers() if auth else {}
    
    if verbose:
        print(f"\n  [DEBUG] Pobieranie URL z API:")
        print(f"  [DEBUG] Endpoint: {url}")
        print(f"  [DEBUG] Headers: {headers}")
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        
        if verbose:
            print(f"  [DEBUG] Status code: {resp.status_code}")
            print(f"  [DEBUG] Response: {resp.text[:200]}")
        
        if resp.status_code == 200:
            data = resp.json()
            audio_url = data.get("url")
            if verbose and audio_url:
                print(f"  [DEBUG] Audio URL: {audio_url[:100]}...")
            return audio_url
        elif resp.status_code == 401 and auth and auth.is_authenticated():
            # Token wygasł, spróbuj odświeżyć
            if auth.refresh():
                headers = auth.get_headers()
                resp = requests.get(url, headers=headers, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("url")
        return None
    except Exception as e:
        if verbose:
            print(f"  [DEBUG] Exception: {e}")
        return None

def extract_podcast_id_from_guid(guid):
    """Wyciągnij ID odcinka z GUID w formacie radio357-*-{id}"""
    if not guid:
        return None
    
    # Format: radio357-author-{email}-{podcast_id} lub radio357-{program_id}-{podcast_id}
    if guid.startswith('radio357-'):
        parts = guid.split('-')
        # Ostatnia część to ID odcinka
        if len(parts) >= 2:
            try:
                return parts[-1]
            except:
                pass
    return None

def sanitize_filename(filename):
    """Usuń niedozwolone znaki z nazwy pliku"""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    # Ogranicz długość nazwy pliku
    return filename[:200]

def get_filename_from_url(url, title=None, index=None):
    """Wyciągnij nazwę pliku z URL lub wygeneruj z tytułu"""
    parsed = urlparse(url)
    filename = os.path.basename(parsed.path)
    # Dekoduj URL-encoded znaki
    filename = unquote(filename)
    
    # Jeśli nie ma sensownej nazwy lub to jest generyczny endpoint, użyj tytułu
    if not filename or '.' not in filename or filename in ['download', 'download.mp3', 'url']:
        if title:
            # Stwórz nazwę z tytułu
            # Usuń/zamień znaki specjalne
            safe_title = re.sub(r'[^\w\s\-\.]', '_', title)
            # Usuń wielokrotne spacje/podkreślenia
            safe_title = re.sub(r'[\s_]+', '_', safe_title)
            # Ogranicz długość
            safe_title = safe_title[:150]
            filename = f"{safe_title}.mp3"
        elif index is not None:
            filename = f"episode_{index:03d}.mp3"
        else:
            filename = f"episode_{hash(url) % 10000}.mp3"
    
    # Jeśli to m3u8, zamień rozszerzenie na mp3
    if filename.endswith('.m3u8'):
        filename = filename[:-5] + '.mp3'
    
    return sanitize_filename(filename)

def is_m3u8_url(url):
    """Sprawdź czy URL wskazuje na plik m3u8 (HLS stream)"""
    return url.lower().endswith('.m3u8') or 'm3u8' in url.lower()

def download_m3u8_file(url, output_path, show_progress=True):
    """
    Pobierz plik m3u8 (HLS stream) używając yt-dlp
    Automatycznie pobiera i łączy wszystkie segmenty, konwertuje do mp3
    """
    try:
        import yt_dlp
    except ImportError:
        print(f"\n  ✗ Błąd: Brak biblioteki yt-dlp")
        print(f"     Zainstaluj: pip install yt-dlp")
        print(f"     Biblioteka yt-dlp jest wymagana do pobierania plików m3u8 (HLS)")
        return False
    
    try:
        print(f"\n  Pobieranie HLS (m3u8): {output_path.name}")
        print(f"  (łączenie segmentów audio...)")
        
        # Konfiguracja yt-dlp
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': str(output_path.with_suffix('')),  # bez rozszerzenia, yt-dlp doda
            'quiet': not show_progress,
            'no_warnings': True,
            'extract_audio': True,
            'audio_format': 'mp3',
            'audio_quality': 0,  # najlepsza jakość
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
        
        # Pobierz i skonwertuj
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        # yt-dlp może stworzyć plik z nieco inną nazwą, znajdź go
        actual_file = output_path
        if not actual_file.exists():
            # Spróbuj znaleźć plik z podobną nazwą
            parent = output_path.parent
            stem = output_path.stem
            for candidate in parent.glob(f"{stem}*"):
                if candidate.suffix in ['.mp3', '.m4a', '.aac']:
                    actual_file = candidate
                    # Zmień nazwę na oczekiwaną
                    if actual_file != output_path:
                        actual_file.rename(output_path)
                        actual_file = output_path
                    break
        
        if actual_file.exists():
            file_size_mb = actual_file.stat().st_size / (1024 * 1024)
            print(f"  ✓ Zapisano: {actual_file.name} ({file_size_mb:.1f} MB)")
            return True
        else:
            print(f"\n  ✗ Nie znaleziono pobranego pliku")
            return False
            
    except Exception as e:
        print(f"\n  ✗ Błąd pobierania m3u8: {e}")
        if output_path.exists():
            output_path.unlink()
        return False

def download_file(url, output_path, show_progress=True):
    """Pobierz plik z danego URL"""
    try:
        print(f"\n  Pobieranie: {output_path.name}")
        
        # Dodaj User-Agent i Referer żeby uniknąć blokady przez CloudFront/CDN
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://radio357.pl/'
        }
        
        resp = requests.get(url, stream=True, timeout=60, headers=headers)
        resp.raise_for_status()
        
        total_size = int(resp.headers.get('content-length', 0))
        downloaded = 0
        
        with open(output_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if show_progress and total_size > 0:
                        progress = (downloaded / total_size) * 100
                        size_mb = downloaded / (1024 * 1024)
                        total_mb = total_size / (1024 * 1024)
                        print(f"\r  Postęp: {progress:.1f}% ({size_mb:.1f}/{total_mb:.1f} MB)", end='', flush=True)
        
        if show_progress:
            print()  # Nowa linia po progress barze
        
        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"  ✓ Zapisano: {output_path.name} ({file_size_mb:.1f} MB)")
        return True
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            print(f"\n  ✗ Błąd pobierania: 403 Forbidden")
            print(f"     Wskazówka: Dla feedów z Radio357 użyj bezpośrednio podcaster357.py")
            print(f"     Ten skrypt działa najlepiej z feedami zawierającymi publiczne URLe")
        else:
            print(f"\n  ✗ Błąd HTTP {e.response.status_code}: {e}")
        if output_path.exists():
            output_path.unlink()  # Usuń częściowo pobrany plik
        return False
    except Exception as e:
        print(f"\n  ✗ Błąd pobierania: {e}")
        if output_path.exists():
            output_path.unlink()  # Usuń częściowo pobrany plik
        return False

def parse_rss_feed(feed_file):
    """Parsuj plik RSS i wyciągnij informacje o odcinkach"""
    try:
        tree = ET.parse(feed_file)
        root = tree.getroot()
        
        episodes = []
        
        # Obsługa różnych formatów RSS
        # Szukaj elementów <item> (standardowe RSS)
        for item in root.findall('.//item'):
            title_elem = item.find('title')
            enclosure_elem = item.find('enclosure')
            guid_elem = item.find('guid')
            
            if enclosure_elem is not None and enclosure_elem.get('url'):
                episode = {
                    'title': title_elem.text if title_elem is not None else 'Unknown',
                    'url': enclosure_elem.get('url'),
                    'type': enclosure_elem.get('type', 'audio/mpeg'),
                    'guid': guid_elem.text if guid_elem is not None else None
                }
                episodes.append(episode)
        
        return episodes
    except Exception as e:
        print(f"✗ Błąd parsowania pliku RSS: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(
        description='Pobieranie plików audio z RSS feed',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Przykłady użycia:
  # Pobierz wszystkie odcinki z feeda
  download_from_feed.py feeds/piotr_stelmach.xml
  
  # Pobierz do konkretnego katalogu
  download_from_feed.py feeds/piotr_stelmach.xml -o ~/Podcasts/Stelmach
  
  # Pobierz tylko pierwsze 5 odcinków
  download_from_feed.py feeds/piotr_stelmach.xml -n 5
  
  # Nadpisz istniejące pliki
  download_from_feed.py feeds/piotr_stelmach.xml --overwrite
        '''
    )
    parser.add_argument('feed_file', help='Plik XML z feedem RSS')
    parser.add_argument('-o', '--output', default='downloaded', 
                       help='Katalog wyjściowy dla pobranych plików (domyślnie: downloaded/)')
    parser.add_argument('-n', '--max-episodes', type=int, 
                       help='Maksymalna liczba odcinków do pobrania (domyślnie: wszystkie)')
    parser.add_argument('--overwrite', action='store_true', 
                       help='Nadpisz istniejące pliki (domyślnie: pomijaj)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Tylko wyświetl listę plików do pobrania (nie pobieraj)')
    parser.add_argument('--verbose', action='store_true',
                       help='Wyświetl szczegółowe informacje (w tym URLe)')
    
    args = parser.parse_args()
    
    # Sprawdź czy plik feed istnieje
    feed_path = Path(args.feed_file)
    if not feed_path.exists():
        print(f"✗ Plik nie istnieje: {args.feed_file}")
        return 1
    
    print(f"\n{'='*60}")
    print(f"Parsowanie RSS feed: {feed_path.name}")
    print(f"{'='*60}\n")
    
    # Parsuj feed
    episodes = parse_rss_feed(feed_path)
    
    if episodes is None:
        return 1
    
    if not episodes:
        print("✗ Nie znaleziono odcinków w feedzie")
        return 1
    
    print(f"✓ Znaleziono {len(episodes)} odcinków w feedzie\n")
    
    # Inicjalizuj autoryzację (automatycznie wczyta tokeny jeśli istnieją)
    auth = Auth()
    
    # Jeśli nie ma zapisanych tokenów, zaproponuj logowanie
    if not auth.is_authenticated():
        print("⚠ Brak zapisanych tokenów autoryzacji")
        print("  Niektóre pliki mogą wymagać logowania (błąd 403)")
        response = input("  Czy chcesz się zalogować? (t/N): ").strip().lower()
        
        if response in ('t', 'tak', 'y', 'yes'):
            email = input("  Email: ").strip()
            password = getpass.getpass("  Hasło: ")
            
            print("  Logowanie...", end='', flush=True)
            if auth.login(email, password):
                print(" ✓")
                print("  Tokeny zapisane do:", TOKEN_FILE)
            else:
                print(" ✗")
                print("  Nie udało się zalogować. Kontynuacja bez autoryzacji...")
        else:
            print("  Kontynuacja bez autoryzacji...")
        print()
    else:
        print(f"✓ Używam zapisanych tokenów z: {TOKEN_FILE}\n")
    
    # Ogranicz liczbę odcinków jeśli podano
    if args.max_episodes and args.max_episodes > 0:
        episodes = episodes[:args.max_episodes]
        print(f"  Pobieranie: {len(episodes)} odcinków (ogranicz do {args.max_episodes})\n")
    
    # Utwórz katalog wyjściowy
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Katalog wyjściowy: {output_dir.absolute()}\n")
    print(f"{'='*60}")
    
    if args.dry_run:
        print("TRYB TESTOWY - Pliki do pobrania:")
        print(f"{'='*60}\n")
        
        for i, episode in enumerate(episodes, 1):
            # Sprawdź czy możemy użyć API
            download_url = episode['url']
            used_api = False
            
            if episode.get('guid') and auth.is_authenticated():
                podcast_id = extract_podcast_id_from_guid(episode['guid'])
                if podcast_id:
                    used_api = True
            
            filename = get_filename_from_url(download_url, episode['title'], i)
            output_path = output_dir / filename
            exists = "✓ ISTNIEJE" if output_path.exists() else "✗ brak"
            format_type = "HLS (m3u8)" if is_m3u8_url(download_url) else "Direct (mp3)"
            auth_type = "z API (auth)" if used_api else "z RSS"
            
            print(f"{i:3d}. {episode['title'][:60]}")
            print(f"     Plik: {filename}")
            print(f"     Format: {format_type}")
            print(f"     Źródło: {auth_type}")
            print(f"     Status: {exists}")
            print()
        
        return 0
    
    # Pobierz odcinki
    success_count = 0
    skipped_count = 0
    error_count = 0
    
    for i, episode in enumerate(episodes, 1):
        print(f"\n[{i}/{len(episodes)}] {episode['title'][:70]}")
        
        # Spróbuj pobrać autoryzowany URL z API jeśli mamy GUID
        download_url = episode['url']
        
        if episode.get('guid') and auth.is_authenticated():
            podcast_id = extract_podcast_id_from_guid(episode['guid'])
            
            if podcast_id:
                print(f"  → Pobieranie autoryzowanego URL (ID: {podcast_id})...", end='', flush=True)
                api_url = get_audio_url_from_api(podcast_id, auth, verbose=args.verbose)
                
                if api_url:
                    print(" ✓")
                    download_url = api_url
                    if args.verbose:
                        print(f"  URL: {download_url[:100]}...")
                else:
                    print(" ✗ (użycie URL z RSS)")
                    if args.verbose:
                        print(f"  URL: {download_url[:100]}...")
        
        # Określ nazwę pliku wyjściowego
        filename = get_filename_from_url(download_url, episode['title'], i)
        output_path = output_dir / filename
        
        # Sprawdź czy plik już istnieje
        if output_path.exists() and not args.overwrite:
            file_size_mb = output_path.stat().st_size / (1024 * 1024)
            print(f"  ⊘ Pominięto (plik istnieje): {filename} ({file_size_mb:.1f} MB)")
            skipped_count += 1
            continue
        
        # Pobierz plik - wykryj czy to m3u8 (HLS stream) czy zwykły plik
        if is_m3u8_url(download_url):
            # Użyj yt-dlp dla plików m3u8 (HLS)
            success = download_m3u8_file(download_url, output_path)
        else:
            # Zwykłe pobieranie dla mp3/innych formatów
            success = download_file(download_url, output_path)
        
        if success:
            success_count += 1
        else:
            error_count += 1
        
        # Krótka przerwa między pobieraniami
        if i < len(episodes):
            time.sleep(0.5)
    
    # Podsumowanie
    print(f"\n{'='*60}")
    print(f"PODSUMOWANIE")
    print(f"{'='*60}")
    print(f"✓ Pobrano pomyślnie: {success_count}")
    if skipped_count > 0:
        print(f"⊘ Pominięto (już istnieją): {skipped_count}")
    if error_count > 0:
        print(f"✗ Błędy: {error_count}")
    print(f"{'='*60}\n")
    
    return 0

if __name__ == "__main__":
    exit(main())
