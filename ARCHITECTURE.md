# Architektura — Enerp AI Assistant

## Diagram systemu (stan obecny — v1)

```
┌─────────────────────────────────────────────────────────┐
│                    Przeglądarka (Chrome)                │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ SpeechRecog │  │  Orb UI      │  │  Chat Panel   │  │
│  │ (STT, mic)  │  │  (Canvas)    │  │  (transkrypcja)│  │
│  └──────┬──────┘  └──────────────┘  └───────────────┘  │
│         │                                              │
└─────────┼──────────────────────────────────────────────┘
          │ HTTPS (port 443, nginx SSL)
          ▼
┌─────────────────────────────────────────────────────────┐
│                      nginx                              │
│               SSL termination → proxy                   │
└─────────────────────┬───────────────────────────────────┘
                      │ HTTP (port 8080)
                      ▼
┌─────────────────────────────────────────────────────────┐
│                   FastAPI (uvicorn)                      │
│                                                         │
│  ┌───────────┐  ┌───────────┐  ┌────────────────────┐  │
│  │ /api/tts  │  │ /api/chat │  │ /api/search        │  │
│  │ edge-tts  │  │           │  │ DuckDuckGo         │  │
│  │ (synteza) │  │           │  │                    │  │
│  └───────────┘  └─────┬─────┘  └────────────────────┘  │
│                       │                                │
│         ┌─────────────┼─────────────┐                  │
│         ▼             ▼             ▼                  │
│  ┌──────────┐  ┌───────────┐  ┌───────────┐           │
│  │DeepSeek  │  │Open-Meteo │  │Conversation│          │
│  │AI (API)  │  │(pogoda)   │  │Files (JSON)│          │
│  └──────────┘  └───────────┘  └───────────┘           │
│                                                         │
│  Zofia (pl-PL-ZofiaNeural) ← edge-tts → MP3 stream     │
└─────────────────────────────────────────────────────────┘
```

## Przepływ danych — dialog głosowy

```
1. Użytkownik mówi → mikrofon
2. SpeechRecognition (Web Speech API) → tekst po polsku
3. POST /api/chat { text, session_id }
4. Serwer: 
   ├── Jeśli pytanie o pogodę → Open-Meteo API
   ├── Jeśli pytanie o newsy/daty → DuckDuckGo API  
   └── DeepSeek API z kontekstem + promptem systemowym
5. Odpowiedź AI → JSON { response, session_id }
6. Frontend: GET /api/tts?text=... → odtwarzanie audio
7. Mikrofon automatycznie wznawia nasłuchiwanie
```

## Komponenty

### Backend (`server.py`)

| Moduł | Odpowiedzialność |
|---|---|
| `build_system_prompt()` | Dynamiczny prompt z datą, godziną, lokalizacją |
| `load/save_conversation()` | Persystencja rozmów (JSON na dysku) |
| `fetch_weather()` | Open-Meteo — aktualna pogoda + prognoza 3-dni |
| `search_web()` | DuckDuckGo — wyniki wyszukiwania |
| `extract_city()` | Wykrywa miasto w zapytaniu |
| `needs_search()` | Decyduje czy odpalić wyszukiwarkę |

### Frontend (`static/index.html`)

- **Orb Canvas** — wizualizacja audio, częstotliwości, cząsteczki
- **MicButton** — toggle on/off, 4 stany: idle/listening/thinking/speaking
- **ChatPanel** — prawy panel, transkrypcja rozmowy user/AI
- **AudioEngine** — Web Audio API, analizator FFT, odtwarzanie TTS

### Zewnętrzne API

| API | Typ | Limit |
|---|---|---|
| DeepSeek (Anthropic-compatible) | AI LLM | ~$2/mln tokenów |
| Open-Meteo | Pogoda | Darmowe, bez limitu |
| DuckDuckGo | Wyszukiwarka | ~50 zapytań/min |
| edge-tts (Microsoft) | Synteza mowy | Darmowe, bez limitu |

## Roadmapa — plany rozwoju

### v1.1 — Powiadomienia aktywne (w toku)

- Powiadomienia o przelewach, płatnościach, ważnych zdarzeniach
- Integracja z systemem FinTech Enerp
- Webhooki / polling co N minut

### v1.2 — Integracja z systemami Enerp

```
┌──────────────────────────────────────────────────┐
│               Enerp System Landscape             │
│                                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │  FinTech │ │ EMS/CRM  │ │   Kalendarz      │ │
│  │ (płatn., │ │ (leady,  │ │ (Google/M365)    │ │
│  │ przelewy)│ │ klienci) │ │                  │ │
│  └────┬─────┘ └────┬─────┘ └────────┬─────────┘ │
│       │            │               │            │
│       └────────────┼───────────────┘            │
│                    │                            │
│                    ▼                            │
│  ┌─────────────────────────────────────────────┐│
│  │         Enerp AI Assistant                  ││
│  │  • Agregacja danych z systemów              ││
│  │  • Podsumowania o 10:00 i 15:00            ││
│  │  • Alerty w czasie rzeczywistym            ││
│  │  • Odpowiedzi na pytania o dane firmowe    ││
│  └─────────────────────────────────────────────┘│
└──────────────────────────────────────────────────┘
```

### v2.0 — Autonomiczny agent

- Wykonywanie czynności za użytkownika (np. wysyłanie maili, tworzenie zadań)
- Integracja ze skrzynkami mailowymi (IMAP/Gmail API)
- Analiza leadów i raportowanie

### v2.5 — Multi-user / multi-room

- Obsługa wielu stanowisk w biurze
- Rozpoznawanie kto mówi
- Personalizowane powiadomienia

### v3.0 — SaaS / multi-tenant

- Panel administracyjny
- Konfigurowalne integracje
- API dla partnerów

## Harmonogram podsumowań (planowane)

```
08:00 — Raport poranny: leady z wczoraj, płatności, wydarzenia w kalendarzu
10:00 — Checkpoint: nowe zdarzenia od rana, pilne sprawy
13:00 — Podsumowanie południowe: stan leadów, transakcje
15:00 — Podsumowanie popołudniowe: co się wydarzyło, co na jutro
17:30 — Raport końcowy dnia + prognoza na jutro
```

## Polityka gałęzi i commitów

```
main          — produkcja (chroniona)
├── develop   — integracja (domyślny branch roboczy)
│   ├── feat/nazwa-funkcji
│   ├── fix/nazwa-poprawki
│   └── chore/nazwa-porządku
└── release/* — przygotowanie wydania
```

### Konwencja commitów

```
feat(chat): dodaj wyszukiwanie DuckDuckGo
fix(tts): obsługa pustego tekstu
docs(readme): opis architektury
test(weather): testy dla extract_city
chore(ci): konfiguracja GitHub Actions
```

### PR Checklist

- [ ] Testy przechodzą (`pytest tests/ -v`)
- [ ] Nowy kod ma testy
- [ ] Dokumentacja zaktualizowana (jeśli dotyczy)
- [ ] Review przez drugą osobę
- [ ] Squash merge do `develop`

## Bezpieczeństwo

- Klucze API przechowywane poza repo (`~/.config/deepseek/key`)
- Certyfikaty SSL w `.gitignore`
- Dane konwersacji w `~/.assistant_conversations/` — poza repo
- nginx jako reverse proxy — ogranicza powierzchnię ataku
- CORS skonfigurowany restrykcyjnie (w produkcji)

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)
