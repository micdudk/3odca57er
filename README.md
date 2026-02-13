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
- **Treści dla patronów** - dostęp do odcinków tylko dla patronów (wymaga konta Patronite)
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
# 2. O numer programu (1-434)
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

Bonus: `generate_rss_feed.py` tworzy feedy RSS.

```bash
python3 generate_rss_feed.py 100064080 --output feed.xml
```

**Automatyzacja**: Zobacz [AUTOMATYZACJA.md](AUTOMATYZACJA.md) - cron, systemd, bezpieczeństwo.

## 📦 Pliki w repo

- `podcaster357.py` - główny skrypt
- `generate_rss_feed.py` - generator feedów RSS
- `AUTOMATYZACJA.md` - przewodnik po automatyzacji na serwerze
- `requirements.txt` - zależności

## ⚠️ Disclaimer

Narzędzie do osobistego użytku. Szanuj prawa autorskie i regulamin Radio 357.

## 📝 Licencja

MIT License - użyj jak chcesz! 🎉
