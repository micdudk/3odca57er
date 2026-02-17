# Radio 357 Podcast Tools 📻

Narzędzia do pobierania podcastów i generowania feedów RSS z [Radia 357](https://radio357.pl).

## 🚀 Instalacja

```bash
pip install -r requirements.txt
```

## 📥 Pobieranie podcastów

```bash
# Interaktywnie (poleci)
python3 podcaster357.py

# Konkretny program
python3 podcaster357.py --id 100064080 --last 5
```

## 📡 Generowanie feedów RSS

### Według audycji
```bash
# Pojedyncza audycja
python3 generate_rss_feed.py 100064080

# Wiele audycji (z config.txt)
python3 generate_all_feeds.py
```

### Według autora
```bash
# Interaktywnie - wybierz z listy
python3 generate_author_feed_by_id.py

# Lub podaj ID autora
python3 generate_author_feed_by_id.py piotr.stelmach@radio357.pl

# Feedy dla WSZYSTKICH autorów (batch)
python3 generate_author_feed_by_id.py --all-authors --min-episodes 10

# Zobacz listę autorów
python3 list_authors.py --details
```

## 📥 Pobieranie z feedów

```bash
# Pobierz wszystkie odcinki z feeda
python3 download_from_feed.py feeds/piotr_stelmach.xml

# Do konkretnego katalogu
python3 download_from_feed.py feeds/369.xml -o ~/Podcasts/369
```

## 📂 Pliki

```
podcaster357.py                 # Pobieranie podcastów
generate_rss_feed.py            # Feed (audycja)
generate_all_feeds.py           # Feedy (wiele audycji)
generate_author_feed_by_id.py   # Feed (autor/autorzy)
list_authors.py                 # Lista autorów
download_from_feed.py           # Pobieranie z RSS
config.txt                      # ID programów (po jednym na linię)
```

## 💡 Wskazówki

- Tokeny zapisywane w `~/.radio357_token` (automatyczny refresh)
- Użyj `--help` dla pełnej listy opcji
- Wymaga `ffmpeg` dla nowszych odcinków (format HLS)

## ⚠️ Disclaimer

Narzędzie do osobistego użytku. Szanuj prawa autorskie i regulamin Radia 357.
