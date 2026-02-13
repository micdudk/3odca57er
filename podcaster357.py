#!/usr/bin/env python3
"""
Skrypt do pobierania podcastów z Radia 357 (radio357.pl)
Możliwość wyboru programu z listy lub podania własnego ID
"""

import requests
import json
import os
import sys
import platform
import subprocess
import shutil
from pathlib import Path
import time
from datetime import datetime
import argparse
import getpass

# Ustaw encoding UTF-8 dla konsoli Windows
if platform.system() == 'Windows':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        # Python < 3.7
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Konfiguracja
OUTPUT_BASE_DIR = Path.home() / "Podcasts"
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
        """Wczytaj tokeny z pliku"""
        if self.token_file.exists():
            try:
                with open(self.token_file, 'r') as f:
                    data = json.load(f)
                    self.access_token = data.get('accessToken')
                    self.refresh_token = data.get('refreshToken')
            except Exception as e:
                print(f"⚠ Nie można wczytać tokenów: {e}")
    
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
            # Ustaw uprawnienia tylko do odczytu dla właściciela (Unix/Linux/macOS)
            try:
                if platform.system() != 'Windows':
                    os.chmod(self.token_file, 0o600)
            except Exception:
                pass  # Ignoruj błędy chmod na Windows
        except Exception as e:
            print(f"⚠ Nie można zapisać tokenów: {e}")
    
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
                print("✓ Zalogowano pomyślnie")
                return True
            elif resp.status_code == 401:
                print("✗ Błędny email lub hasło")
                return False
            else:
                print(f"✗ Błąd logowania: {resp.status_code}")
                return False
        except Exception as e:
            print(f"✗ Błąd logowania: {e}")
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
    
    def prompt_login(self):
        """Poproś użytkownika o dane logowania i zaloguj"""
        print("\n" + "=" * 80)
        print("LOGOWANIE")
        print("=" * 80)
        print("Brak autoryzacji. Zaloguj się aby uzyskać dostęp do treści tylko dla patronów.")
        print("Możesz pominąć logowanie (Enter) - pobierzesz tylko treści darmowe.\n")
        
        try:
            email = input("Email (lub Enter aby pominąć): ").strip()
            
            if not email:
                print("\n⊘ Kontynuowanie bez logowania - tylko treści darmowe\n")
                return False
            
            password = getpass.getpass("Hasło: ")
            
            if not password:
                print("\n⊘ Kontynuowanie bez logowania - tylko treści darmowe\n")
                return False
            
            success = self.login(email, password)
            print()
            return success
            
        except KeyboardInterrupt:
            print("\n\n⊘ Kontynuowanie bez logowania - tylko treści darmowe\n")
            return False

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
            return data.get("url"), False  # URL, needs_auth
        elif resp.status_code == 401 and auth and auth.is_authenticated():
            # Token wygasł, spróbuj odświeżyć
            if auth.refresh():
                headers = auth.get_headers()
                resp = requests.get(url, headers=headers, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("url"), False
            return None, True
        elif resp.status_code == 403:
            return None, True  # Wymagana autoryzacja
        else:
            return None, False
    except Exception as e:
        print(f"  ✗ Błąd pobierania URL: {e}")
        return None, False

def sanitize_filename(filename):
    """Usuń niedozwolone znaki z nazwy pliku"""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    # Ogranicz długość nazwy pliku
    return filename[:200]

def download_file(url, output_path, description=""):
    """Pobierz plik z danego URL (obsługuje HLS streamy)"""
    # Sprawdź czy to HLS stream (.m3u8)
    if '.m3u8' in url:
        return download_hls_stream(url, output_path)
    
    # Standardowe pobieranie dla bezpośrednich linków
    try:
        resp = requests.get(url, stream=True, timeout=60)
        resp.raise_for_status()
        
        total_size = int(resp.headers.get('content-length', 0))
        downloaded = 0
        
        with open(output_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        size_mb = downloaded / (1024 * 1024)
                        total_mb = total_size / (1024 * 1024)
                        print(f"\r  Postęp: {progress:.1f}% ({size_mb:.1f}/{total_mb:.1f} MB)", end='')
        
        print(f"\n  ✓ Zapisano: {output_path.name}")
        return True
    except Exception as e:
        print(f"\n  ✗ Błąd pobierania: {e}")
        if output_path.exists():
            output_path.unlink()  # Usuń częściowo pobrany plik
        return False

def download_hls_stream(url, output_path):
    """Pobierz HLS stream używając ffmpeg"""
    # Sprawdź czy ffmpeg jest dostępny
    if not shutil.which('ffmpeg'):
        print(f"\n  ✗ Błąd: ffmpeg nie jest zainstalowany")
        if platform.system() == 'Windows':
            print(f"     Zainstaluj: https://ffmpeg.org/download.html lub choco install ffmpeg")
        elif platform.system() == 'Darwin':
            print(f"     Zainstaluj: brew install ffmpeg")
        else:
            print(f"     Zainstaluj: sudo apt install ffmpeg (Ubuntu/Debian) lub sudo yum install ffmpeg (CentOS/RHEL)")
        return False
    
    try:
        print(f"\n  📡 Pobieranie HLS stream...")
        
        # Użyj ffmpeg do pobrania i konwersji do MP3
        cmd = [
            'ffmpeg',
            '-i', url,
            '-vn',  # Bez video
            '-acodec', 'libmp3lame',  # Kodek MP3
            '-ab', '128k',  # Bitrate
            '-y',  # Nadpisz bez pytania
            '-loglevel', 'error',  # Tylko błędy
            '-stats',  # Pokaż statystyki
            str(output_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            # Sprawdź rozmiar pobranego pliku
            if output_path.exists():
                size_mb = output_path.stat().st_size / (1024 * 1024)
                print(f"  ✓ Zapisano: {output_path.name} ({size_mb:.1f} MB)")
                return True
            else:
                print(f"  ✗ Błąd: plik nie został utworzony")
                return False
        else:
            print(f"  ✗ Błąd ffmpeg: {result.stderr}")
            if output_path.exists():
                output_path.unlink()
            return False
            
    except Exception as e:
        print(f"  ✗ Błąd pobierania HLS: {e}")
        if output_path.exists():
            output_path.unlink()
        return False

def fetch_all_programs():
    """Pobierz wszystkie programy z API"""
    all_programs = []
    page = 0
    
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
    
    return all_programs

def fetch_all_episodes(program_id):
    """Pobierz wszystkie odcinki programu (paginacja)"""
    all_episodes = []
    page = 0
    
    while True:
        try:
            data = get_program_episodes(program_id, page)
            
            # Sprawdź czy są odcinki w odpowiedzi
            if "_embedded" in data and "podcasts" in data["_embedded"]:
                episodes = data["_embedded"]["podcasts"]
                if not episodes:
                    break
                    
                all_episodes.extend(episodes)
                print(f"   Strona {page}: {len(episodes)} odcinków")
                
                # Sprawdź informacje o paginacji
                if "page" in data and "total" in data:
                    total = data["total"]
                    page_size = data.get("page_size", 250)
                    
                    # Jeśli mamy już wszystkie odcinki
                    if len(all_episodes) >= total:
                        break
                
                # Jeśli otrzymaliśmy mniej odcinków niż standardowy rozmiar strony, to koniec
                if len(episodes) < 250:
                    break
                    
                page += 1
                time.sleep(0.3)  # Przerwa między żądaniami
            else:
                break
                
        except Exception as e:
            print(f"   ✗ Błąd na stronie {page}: {e}")
            break
    
    return all_episodes

def download_program_podcasts(program_id, program_name, output_dir, auth=None, last_n=None):
    """Pobierz wszystkie podcasty z danego programu"""
    
    print("=" * 80)
    print(f"POBIERANIE PODCASTÓW: {program_name}")
    print("=" * 80)
    
    # Utwórz katalog wyjściowy
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Pobierz listę wszystkich odcinków
    print(f"\n1. Pobieranie listy odcinków...")
    all_episodes = fetch_all_episodes(program_id)
    
    print(f"\n   Znaleziono łącznie: {len(all_episodes)} odcinków")
    
    # Ogranicz do ostatnich N odcinków jeśli podano
    if last_n is not None and last_n > 0:
        all_episodes = all_episodes[:last_n]
        print(f"   Ograniczono do ostatnich: {len(all_episodes)} odcinków\n")
    else:
        print()
    
    if not all_episodes:
        print("   ⚠ Brak odcinków do pobrania")
        return
    
    # Pobierz każdy odcinek
    print(f"2. Pobieranie odcinków do: {output_dir}\n")
    
    downloaded_count = 0
    skipped_count = 0
    failed_count = 0
    exclusive_count = 0
    
    # Pokaż status autoryzacji
    if auth and auth.is_authenticated():
        print("🔓 Zalogowano - dostęp do treści tylko dla patronów\n")
    else:
        print("🔒 Brak autoryzacji - tylko treści darmowe\n")
    
    for idx, episode in enumerate(all_episodes, 1):
        episode_id = episode.get("id")
        episode_title = episode.get("title", f"Odcinek_{episode_id}")
        published_at = episode.get("publishedAt", "")
        is_free = episode.get("isFree", True)
        
        # Wyciągnij datę z publishedAt (może być timestamp lub string)
        date_str = ""
        if published_at:
            if isinstance(published_at, int):
                # Jest to timestamp (w milisekundach)
                date_obj = datetime.fromtimestamp(published_at / 1000)
                date_str = date_obj.strftime("%Y-%m-%d")
            elif isinstance(published_at, str):
                # Jest to string w formacie ISO
                date_str = published_at[:10]  # YYYY-MM-DD
        
        # Utwórz nazwę pliku
        if date_str:
            filename = f"{date_str}_{sanitize_filename(episode_title)}.mp3"
        else:
            filename = f"{idx:03d}_{sanitize_filename(episode_title)}.mp3"
        
        output_path = output_dir / filename
        
        print(f"[{idx}/{len(all_episodes)}] {episode_title}")
        print(f"  ID: {episode_id} | Data: {date_str or 'brak'} | Darmowy: {is_free}")
        
        # Sprawdź czy plik już istnieje
        if output_path.exists():
            file_size = output_path.stat().st_size
            if file_size > 100000:  # Jeśli plik ma więcej niż 100KB, uznaj za poprawny
                print(f"  ⊘ Plik już istnieje ({file_size / (1024*1024):.1f} MB), pomijam")
                skipped_count += 1
                continue
            else:
                print(f"  ⚠ Plik istnieje ale jest za mały ({file_size} B), pobieram ponownie")
                output_path.unlink()
        
        # Pobierz URL audio
        audio_url, needs_auth = get_audio_url(episode_id, auth)
        
        if not audio_url:
            if needs_auth:
                print(f"  🔒 Treść tylko dla patronów")
                exclusive_count += 1
            else:
                print(f"  ✗ Nie udało się pobrać URL audio")
                failed_count += 1
            continue
        
        # Pobierz plik
        if download_file(audio_url, output_path, episode_title):
            downloaded_count += 1
        else:
            failed_count += 1
        
        # Przerwa między pobieraniami
        time.sleep(0.5)
        print()
    
    # Podsumowanie
    print("=" * 80)
    print("PODSUMOWANIE")
    print("=" * 80)
    print(f"Pobrano:           {downloaded_count}")
    print(f"Pominięto:         {skipped_count} (już istnieją)")
    print(f"Dla patronów:      {exclusive_count} (wymagają patronatu)")
    print(f"Błędy:             {failed_count}")
    print(f"Łącznie odcinków:  {len(all_episodes)}")
    print(f"\nPliki zapisane w: {output_dir}")
    print("=" * 80)

def interactive_program_selection():
    """Interaktywny wybór programu z pełnej listy"""
    print("\n" + "=" * 80)
    print("WYBÓR PROGRAMU")
    print("=" * 80)
    print("\nPobieranie listy programów z API...\n")
    
    programs = fetch_all_programs()
    
    if not programs:
        print("✗ Nie udało się pobrać listy programów")
        return None, None
    
    # Sortuj alfabetycznie
    sorted_programs = sorted(programs, key=lambda x: x.get('name', '').lower())
    
    print(f"Znaleziono {len(sorted_programs)} programów:\n")
    print(f"{'Nr':<6} {'ID':<12} {'Nazwa'}")
    print("-" * 80)
    
    # Wyświetl wszystkie programy z numerami
    for idx, prog in enumerate(sorted_programs, 1):
        prog_id = prog.get('id', 'N/A')
        prog_name = prog.get('name', 'Bez nazwy')
        
        # Ogranicz długość nazwy
        if len(prog_name) > 60:
            prog_name = prog_name[:57] + "..."
        
        print(f"{idx:<6} {prog_id:<12} {prog_name}")
    
    print("-" * 80)
    
    # Poproś o wybór
    while True:
        try:
            choice = input(f"\nWybierz numer programu (1-{len(sorted_programs)}) lub 'q' aby wyjść: ").strip()
            
            if choice.lower() == 'q':
                print("Anulowano.")
                return None, None
            
            choice_num = int(choice)
            
            if 1 <= choice_num <= len(sorted_programs):
                selected = sorted_programs[choice_num - 1]
                program_id = selected.get('id')
                program_name = selected.get('name', f"Program {program_id}")
                
                print(f"\n✓ Wybrano: {program_name} (ID: {program_id})\n")
                return program_id, program_name
            else:
                print(f"✗ Podaj liczbę od 1 do {len(sorted_programs)}")
        except ValueError:
            print("✗ Podaj poprawną liczbę")
        except KeyboardInterrupt:
            print("\n\nAnulowano.")
            return None, None

def show_all_programs():
    """Wyświetl wszystkie programy z API"""
    print("\n" + "=" * 80)
    print("WSZYSTKIE PROGRAMY Z RADIA 357")
    print("=" * 80)
    print("\nPobieranie listy programów z API...\n")
    
    programs = fetch_all_programs()
    
    if not programs:
        print("✗ Nie udało się pobrać listy programów")
        return
    
    print(f"Znaleziono {len(programs)} programów:\n")
    print(f"{'ID':<12} {'Nazwa':<50} {'Typ':<15}")
    print("-" * 80)
    
    for prog in sorted(programs, key=lambda x: x.get('name', '')):
        prog_id = prog.get('id', 'N/A')
        prog_name = prog.get('name', 'Bez nazwy')
        prog_type = prog.get('type', 'podcast')
        
        # Ogranicz długość nazwy
        if len(prog_name) > 47:
            prog_name = prog_name[:44] + "..."
        
        print(f"{prog_id:<12} {prog_name:<50} {prog_type:<15}")
    
    print("-" * 80)
    print(f"\nAby pobrać podcast, użyj:")
    print(f"  python3 {os.path.basename(__file__)} --id <ID_PROGRAMU>")
    print(f"\nPrzykład:")
    print(f"  python3 {os.path.basename(__file__)} --id {programs[0].get('id')}")
    print("=" * 80)

def main():
    parser = argparse.ArgumentParser(
        description='Pobieranie podcastów z Radia 357',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--id', dest='program_id', help='ID programu')
    parser.add_argument('--show-all-programs', action='store_true', help='Wyświetl wszystkie programy z API')
    parser.add_argument('--output', '-o', help='Katalog wyjściowy (domyślnie: ~/Podcasts/)')
    parser.add_argument('--last', type=int, metavar='N', help='Pobierz tylko N ostatnich odcinków')
    parser.add_argument('--no-login', action='store_true', help='Pomiń logowanie (tylko treści darmowe)')
    parser.add_argument('--token-file', help=f'Plik z tokenami (domyślnie: {TOKEN_FILE})')
    
    args = parser.parse_args()
    
    # Inicjalizuj autoryzację
    token_file = Path(args.token_file) if args.token_file else TOKEN_FILE
    auth = Auth(token_file)
    
    # Sprawdź czy użytkownik chce pominąć logowanie
    if args.no_login:
        print("\n⊘ Pominięto logowanie (--no-login) - tylko treści darmowe\n")
        auth = None
    elif not auth.is_authenticated():
        # Brak tokenów - poproś o logowanie
        if not auth.prompt_login():
            auth = None
    else:
        print("\n✓ Zalogowano (tokeny wczytane z pliku)\n")
    
    # Wyświetl listę programów
    if args.show_all_programs:
        show_all_programs()
        return
    
    # Wybierz program
    program_id = None
    program_name = None
    
    if args.program_id:
        # Użyj podanego ID
        program_id = args.program_id
        try:
            info = get_program_info(program_id)
            program_name = info.get("name", f"Program {program_id}")
        except Exception as e:
            print(f"✗ Błąd pobierania informacji o programie: {e}")
            return
    else:
        # Interaktywny wybór programu
        program_id, program_name = interactive_program_selection()
        
        if not program_id:
            return
    
    # Zapytaj o liczbę odcinków jeśli nie podano --last i wybór był interaktywny
    last_n = args.last
    if last_n is None and not args.program_id:
        # Użytkownik wybrał program interaktywnie i nie podał --last
        try:
            response = input("\nIle ostatnich odcinków pobrać? (Enter = wszystkie): ").strip()
            if response:
                last_n = int(response)
                if last_n <= 0:
                    print("✗ Liczba musi być większa od 0, pobiorę wszystkie")
                    last_n = None
            print()
        except ValueError:
            print("✗ Nieprawidłowa liczba, pobiorę wszystkie\n")
            last_n = None
        except KeyboardInterrupt:
            print("\n\nAnulowano.")
            return
    
    # Ustaw katalog wyjściowy
    if args.output:
        output_dir = Path(args.output)
    else:
        # Utwórz katalog na podstawie nazwy programu
        safe_name = sanitize_filename(program_name).replace(' ', '_')
        output_dir = OUTPUT_BASE_DIR / safe_name
    
    # Pobierz podcasty
    download_program_podcasts(program_id, program_name, output_dir, auth, last_n=last_n)

if __name__ == "__main__":
    main()
