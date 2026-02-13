# Automatyzacja RSS 🤖

Przewodnik automatycznego generowania feedów RSS na serwerze (Linux/macOS).

> **Windows**: Użyj Task Scheduler zamiast cron.

## 🔐 Jak działa logowanie?

1. **Pierwsze logowanie** - podajesz email i hasło
2. **Token zapisany** - w `~/.radio357_token` (chmod 600)
3. **Kolejne uruchomienia** - używają tokenu automatycznie
4. **Auto-refresh** - token odświeża się przed wygaśnięciem

**Hasło nie jest przechowywane** - tylko token dostępu.

## 🚀 Setup krok po kroku

### 1. Instalacja

```bash
# Zainstaluj ffmpeg (opcjonalne, dla nowszych odcinków)
brew install ffmpeg              # macOS
sudo apt install ffmpeg         # Linux Ubuntu/Debian
sudo yum install ffmpeg         # Linux CentOS/RHEL
```

### 2. Pierwsze logowanie

```bash
# Zaloguj się raz - zapisze token
python3 podcaster357.py
# Podaj email i hasło
```

### 3. Skrypt aktualizujący

```bash
cat > ~/update_rss.sh << 'EOF'
#!/bin/bash
PROGRAM_ID="100037114"
OUTPUT_FILE="/var/www/html/rss/feed.xml"

cd ~/radio357
python3 generate_rss_feed.py "$PROGRAM_ID" --output "$OUTPUT_FILE" --max-episodes 50
chmod 644 "$OUTPUT_FILE"
echo "$(date): Zaktualizowano" >> ~/rss_update.log
EOF

chmod +x ~/update_rss.sh
```

### 4. Cron (co 6 godzin)

```bash
crontab -e
# Dodaj:
0 */6 * * * /home/user/update_rss.sh
```

## 📝 Wiele audycji

Config z listą programów:

```bash
cat > ~/rss_feeds.conf << 'EOF'
# program_id|nazwa_pliku|max_episodes
100037114|chore_sny.xml|50
100064080|pikselowe.xml|30
130265|zle_radio.xml|20
EOF
```

Skrypt aktualizujący wszystko:

```bash
cat > ~/update_all_rss.sh << 'EOF'
#!/bin/bash
OUTPUT_DIR="/var/www/html/rss"
SCRIPT_DIR="$HOME/radio357"
cd "$SCRIPT_DIR"

while IFS='|' read -r program_id filename max_episodes; do
    [[ "$program_id" =~ ^#.*$ ]] && continue
    [[ -z "$program_id" ]] && continue
    
    python3 generate_rss_feed.py "$program_id" \
        --output "$OUTPUT_DIR/$filename" \
        --max-episodes "$max_episodes"
    chmod 644 "$OUTPUT_DIR/$filename"
done < "$HOME/rss_feeds.conf"

echo "$(date): Zaktualizowano" >> ~/rss_update.log
EOF

chmod +x ~/update_all_rss.sh

# Cron (codziennie o 6:00)
# 0 6 * * * /home/user/update_all_rss.sh
```

## 🛡️ Zabezpieczenia (opcjonalne)

### Dedykowany użytkownik

```bash
# Jako root
useradd -m -s /bin/bash rss-generator
apt install ffmpeg  # lub yum install ffmpeg
su - rss-generator

# Zainstaluj skrypty
git clone https://github.com/micdudk/3odca57er.git
cd 3odca57er
pip3 install -r requirements.txt --user
python3 podcaster357.py  # pierwsze logowanie
```

### Systemd timer (zamiast cron)

Service (`/etc/systemd/system/rss-generator.service`):
```ini
[Unit]
Description=Generator RSS dla Radia 357
After=network.target

[Service]
Type=oneshot
User=rss-generator
WorkingDirectory=/home/rss-generator/radio357
ExecStart=/home/rss-generator/update_all_rss.sh
StandardOutput=journal
```

Timer (`/etc/systemd/system/rss-generator.timer`):
```ini
[Unit]
Description=Generator RSS - timer (co 6h)

[Timer]
OnCalendar=*-*-* 00,06,12,18:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

Aktywacja:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now rss-generator.timer
sudo systemctl list-timers  # sprawdź
```

## 🔧 Troubleshooting

```bash
# Token wygasł - zaloguj się ponownie
rm ~/.radio357_token && python3 podcaster357.py

# Test pojedynczego feeda
python3 generate_rss_feed.py 100064080 --output test.xml

# Sprawdź logi
tail -f ~/rss_update.log                    # cron
sudo journalctl -u rss-generator.service -f  # systemd
```

## 📊 Struktura katalogów

```
/home/rss-generator/
├── radio357/
│   ├── podcaster357.py
│   └── generate_rss_feed.py
├── .radio357_token     # Token (chmod 600)
├── rss_feeds.conf      # Lista feedów
├── update_all_rss.sh
└── rss_update.log

/var/www/html/rss/
├── chore_sny.xml       # Publiczne feedy
└── pikselowe.xml
```

Feedy dostępne pod: `https://twoja-domena.pl/rss/chore_sny.xml`

## 💡 Best practices

**Dobre:**
- Token z uprawnieniami 600
- Dedykowany użytkownik systemu
- Aktualizacja co 6h (większość przypadków)
- Max 50 odcinków w RSS (optymalny rozmiar)

**Złe:**
- Commitowanie tokenu do git
- Przechowywanie hasła w skryptach  
- Uruchamianie jako root
- Uprawnienia 777
