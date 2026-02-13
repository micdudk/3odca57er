# Radio 357 Podcast Downloader 📻

Skrypt do pobierania podcastów z [Radio 357](https://radio357.pl).

## 🚀 Szybki start

```bash
# Zainstaluj zależności
pip install requests

# Zainstaluj ffmpeg (opcjonalne, dla nowszych odcinków)
brew install ffmpeg                # macOS
sudo apt install ffmpeg           # Linux
choco install ffmpeg              # Windows

# Uruchom
python3 podcaster357.py           # macOS/Linux
python podcaster357.py            # Windows
```

## ✨ Funkcje

- **Interaktywny wybór** - lista wszystkich 434 programów do wyboru
- **Automatyczne logowanie** - pyta o login przy pierwszym uruchomieniu, potem zapamiętuje
- **Treści dla patronów** - dostęp do odcinków tylko dla patronów (wymaga konta 357 i aktywnego patronatu)
- **Wybór liczby odcinków** - pobierz wszystkie lub tylko ostatnie N
- **Wznawianie** - pomija już pobrane pliki
- **Ładne nazwy** - pliki nazywane datą i tytułem
- **HLS streaming** - automatyczna obsługa nowszych odcinków (wymaga ffmpeg)

## 📖 Użycie

### Podstawowe (interaktywne)

```bash
# Uruchom i wybierz z listy
python3 podcaster357.py

# Program zapyta:
# 1. O login (Enter = bez logowania, tylko darmowe)
# 2. O numer programu (1-iluś tam, ile aktualnie jest)
# 3. O liczbę odcinków (Enter = wszystkie)
```

### Z argumentami

```bash
# Pokaż wszystkie programy (bez pobierania)
python3 podcaster357.py --show-all-programs

# Pobierz konkretny program po ID
python3 podcaster357.py --id 100064080

# Pobierz tylko 5 ostatnich odcinków
python3 podcaster357.py --id 100064080 --last 5

# Pomiń logowanie (tylko darmowe treści)
python3 podcaster357.py --no-login

# Własny katalog wyjściowy
python3 podcaster357.py --id 100064080 --output ~/Moje_Podcasty
```

## 📝 Jak znaleźć ID programu?

```bash
# Pokaż wszystkie programy
python3 podcaster357.py --show-all-programs

# Wyszukaj konkretny
python3 podcaster357.py --show-all-programs | grep "Nazwa"
```

## 🎯 Przykłady

```bash
# Interaktywny wybór (najprostsze)
python3 podcaster357.py

# Pobierz 5 ostatnich odcinków konkretnego programu
python3 podcaster357.py --id 100064080 --last 5
```

## 🛠️ Wszystkie opcje

```bash
python3 podcaster357.py --help
```

| Opcja | Opis |
|-------|------|
| `--id ID` | ID programu do pobrania |
| `--last N` | Pobierz tylko N ostatnich odcinków |
| `--no-login` | Pomiń logowanie (tylko darmowe) |
| `--output PATH` | Katalog wyjściowy |
| `--show-all-programs` | Pokaż listę programów |
| `--token-file PATH` | Własna lokalizacja tokenu |

## 💡 Wskazówki

- **Logowanie**: Token wygasa? Uruchom ponownie, zaloguje się automatycznie
- **Darmowe treści**: Użyj `--no-login` aby pominąć logowanie
- **Pliki**: Zapisywane w `~/Podcasts/Nazwa_Programu/` jako `2026-01-15_Tytuł.mp3`
- **ffmpeg**: Nowsze odcinki wymagają ffmpeg (format HLS), starsze działają bez niego
- **Windows**: Użyj `python` zamiast `python3` i PowerShell zamiast cmd.exe

## 🎙️ Generator RSS

Generuje feedy RSS 2.0 kompatybilne z iTunes/Apple Podcasts i innymi aplikacjami podcastowymi.

**Informacje w feedzie:**
- Tytuł i podtytuł odcinka
- Pełny opis (z obsługą HTML)
- Autor(zy)/prowadzący z imieniem i emailem
- Kategorie odcinków
- Data publikacji i czas trwania
- Obrazy dla programu i odcinków
- Link do odcinka na Radio 357

### Pojedynczy feed

```bash
# Utworzy feed.xml dla wybranego programu (domyślnie: wszystkie treści, włącznie z patronami)
python3 generate_rss_feed.py 100064080 --output feed.xml

# Pobierz wszystkie odcinki (bez limitu)
python3 generate_rss_feed.py 100064080 --all --output feed.xml

# Tylko darmowe odcinki (bez treści dla patronów)
python3 generate_rss_feed.py 100064080 --free-only --output feed.xml
```

### Wiele feedów jednocześnie

Utwórz `config.txt` z listą ID programów (jeden per linia):

```
# Lista ID programów Radio 357
# Komentarze zaczynające się od # są ignorowane

# Szał
100037114

# Pikselowe marzenia
100064080

# Złe Radio  
130265

# Rzecz technologiczna
251803
```

Uruchom skrypt - automatycznie wygeneruje pliki XML z nazwami utworzonymi z nazw programów:

```bash
# Wygeneruj wszystkie feedy (domyślnie: 50 odcinków, wszystkie treści włącznie z patronami)
python3 generate_all_feeds.py

# Pobierz wszystkie dostępne odcinki
python3 generate_all_feeds.py --all

# Tylko darmowe treści (bez treści dla patronów)
python3 generate_all_feeds.py --free-only

# Własny katalog wyjściowy
python3 generate_all_feeds.py -o /var/www/rss

# Ograniczenie liczby odcinków
python3 generate_all_feeds.py -n 20

# Własny plik konfiguracyjny + wszystkie odcinki
python3 generate_all_feeds.py -c moje_programy.txt -o /var/www/html/rss --all
```

**Automatyzacja**: Zobacz [AUTOMATYZACJA.md](AUTOMATYZACJA.md) - cron, systemd, bezpieczeństwo.

## 📦 Pliki w repo

- `podcaster357.py` - główny skrypt do pobierania podcastów
- `generate_rss_feed.py` - generator pojedynczego feedu RSS
- `generate_all_feeds.py` - generator wielu feedów z pliku konfiguracyjnego
- `config.txt` - przykładowy plik konfiguracyjny (lista ID programów)
- `AUTOMATYZACJA.md` - przewodnik po automatyzacji na serwerze
- `requirements.txt` - zależności

## ⚠️ Disclaimer

Narzędzie do osobistego użytku. Szanuj prawa autorskie i regulamin Radio 357.

## 📝 Licencja

MIT License - użyj jak chcesz! 🎉
