# Enerp AI Assistant (Asystentka Zofia)

Głosowy asystent AI dla firmy Enerp — mówi po polsku, słucha przez mikrofon, odpowiada głosem Zofii.
Działa jako fizyczny terminal w biurze (komputer z głośnikiem i mikrofonem, przeglądarka Chrome).

## Funkcje

| Funkcja | Opis |
|---|---|
| 🎤 **Dialog głosowy** | Ciągłe nasłuchiwanie, rozpoznawanie mowy (STT), odpowiedź głosowa (TTS) |
| 🧠 **AI (DeepSeek)** | Rozumienie kontekstu, pamięć rozmowy, odpowiedzi po polsku |
| 🌤️ **Pogoda** | Dane z Open-Meteo — aktualna temperatura, prognoza 3-dniowa |
| 🔍 **Wyszukiwarka** | DuckDuckGo — newsy, imieniny, wypadki, kursy walut |
| 💾 **Pamięć trwała** | Konwersacje zapisywane między restartami |
| 📅 **Świadomość czasu** | AI zna aktualną datę, dzień tygodnia i godzinę |
| 📍 **Świadomość miejsca** | Domyślna lokalizacja: Natolin 43, 05-825 Natolin |

## Szybki start

### Wymagania
- Python 3.12+
- Chrome lub Edge (do rozpoznawania mowy)
- Klucz API DeepSeek

### Instalacja

```bash
# 1. Sklonuj repozytorium
git clone https://github.com/EnerpSoftware/enerp-aiassistant.git
cd enerp-aiassistant

# 2. Zainstaluj zależności
python3 -m venv venv
./venv/bin/pip install -r requirements.txt

# 3. Skonfiguruj klucz DeepSeek
mkdir -p ~/.config/deepseek
echo "sk-twój-klucz-api" > ~/.config/deepseek/key
chmod 600 ~/.config/deepseek/key

# 4. Wygeneruj certyfikat SSL (wymagany do mikrofonu)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout selfsigned.key -out selfsigned.crt \
  -subj "/CN=localhost" -addext "subjectAltName=IP:127.0.0.1"

# 5. Uruchom
./venv/bin/uvicorn server:app --host 0.0.0.0 --port 8080
```

Otwórz `https://<adres-ip>:8080` w Chrome. Przy pierwszym wejściu zaakceptuj ostrzeżenie o certyfikacie (Zaawansowane → Przejdź do strony).

### Produkcja (systemd + nginx)

```bash
./venv/bin/uvicorn server:app --host 0.0.0.0 --port 8080 --ssl-keyfile selfsigned.key --ssl-certfile selfsigned.crt
```

Lub przez nginx (SSL na nginx, HTTP do uvicorn):

```bash
sudo bash setup.sh
```

## API

| Endpoint | Metoda | Opis |
|---|---|---|
| `/api/health` | GET | Status serwisu |
| `/api/tts?text=...&voice=zofia` | GET | Synteza mowy (MP3 strumieniowo) |
| `/api/chat` | POST | AI chat z kontekstem `{"text": "...", "session_id": "..."}` |
| `/api/chat/{session_id}` | DELETE | Wyczyść historię rozmowy |
| `/api/search?q=...` | GET | Wyszukiwanie DuckDuckGo |

## Uruchamianie testów

```bash
./venv/bin/pip install -r requirements.txt
./venv/bin/python -m pytest tests/ -v
```

## Struktura projektu

```
enerp-aiassistant/
├── server.py              # FastAPI backend
├── static/
│   └── index.html         # Frontend SPA
├── tests/
│   ├── test_server.py     # Testy endpointów API
│   └── test_weather.py    # Testy integracji pogodowej
├── requirements.txt       # Zależności Python
├── pytest.ini             # Konfiguracja pytest
├── nginx-assistant.conf   # Konfiguracja nginx
├── asystentka.service     # Unit systemd
├── setup.sh               # Skrypt instalacyjny
├── .github/workflows/
│   └── tests.yml          # CI/CD — testy przy push i PR
├── README.md
└── ARCHITECTURE.md
```

## Licencja

Proprietary — Enerp Software. Wszelkie prawa zastrzeżone.
