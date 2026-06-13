"""
Asystentka TTS Server — FastAPI + edge-tts + DeepSeek AI
  • Głosy: pl-PL-ZofiaNeural (kobieta), pl-PL-MarekNeural (mężczyzna)
  • AI: DeepSeek przez endpoint Anthropic-kompatybilny
  • Web search: DuckDuckGo (gdy potrzeba aktualnych danych)
  • Pamięć: konwersacje zapisywane w ~/.assistant_conversations/
"""
import io
import os
import re
import json
import time
import asyncio
from pathlib import Path
from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.responses import StreamingResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import edge_tts
import aiohttp
from ddgs import DDGS

app = FastAPI(title="Asystentka TTS + AI + Search")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

VOICES = {
    "zofia": "pl-PL-ZofiaNeural",
    "marek": "pl-PL-MarekNeural",
}

# ── DeepSeek API config ──────────────────────────────────────
DS_KEY_FILE = Path(os.environ.get("DS_KEY_FILE", os.path.expanduser("~/.config/deepseek/key")))
DS_API_KEY = None
if DS_KEY_FILE.exists():
    DS_API_KEY = DS_KEY_FILE.read_text().strip().split("\n")[0].strip()
    print(f"🔑 DeepSeek API key loaded ({len(DS_API_KEY)} chars)")
else:
    print("⚠️  Brak klucza DeepSeek API – /api/chat nie będzie działać")

DS_BASE_URL = "https://api.deepseek.com/anthropic"
DS_MODEL = "deepseek-v4-pro[1m]"

# ── Polish day/month names for date formatting ───────────────
_PL_DAYS = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"]
_PL_MONTHS = [
    "stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca",
    "lipca", "sierpnia", "września", "października", "listopada", "grudnia"
]


def _pl_date(now) -> str:
    return f"{_PL_DAYS[now.weekday()]}, {now.day} {_PL_MONTHS[now.month - 1]} {now.year} r."


def build_system_prompt() -> str:
    """Dynamiczny prompt z aktualną datą, godziną i lokalizacją."""
    from datetime import datetime, timezone, timedelta
    tz = timezone(timedelta(hours=2))  # CEST — Polska
    now = datetime.now(tz)
    date_str = _pl_date(now)
    time_str = now.strftime("%H:%M")
    return f"""Jesteś Zofia — asystentka głosowa mówiąca po polsku.
Jesteś pomocna, rzeczowa i zwięzła. Odpowiadasz krótko — maksymalnie 2-3 zdania,
chyba że użytkownik poprosi o więcej szczegółów. Mów naturalnym, ciepłym tonem.
Odpowiadasz wyłącznie po polsku.

=== KONTEKST CZASOWY I MIEJSCE ===
- Teraz jest: {date_str}, godzina {time_str} (czas polski CEST/UTC+2)
- Jesteśmy w Polsce, domyślna lokalizacja: Natolin 43, 05-825 Natolin, woj. mazowieckie
- Blisko: Grodzisk Mazowiecki (~3 km), Milanówek (~4 km), Pruszków (~8 km), trasa A2 (węzeł Brwinów ~5 km), DK719
- ZAWSZE używaj powyższej daty i czasu — to są prawdziwe, aktualne dane

=== ZASADY ===
- Jeśli pytanie dotyczy daty, dnia tygodnia lub godziny — odpowiedz na podstawie KONTEKSTU powyżej
- Jeśli pytanie dotyczy imienin, pogody, wypadków, wydarzeń — najpierw sprawdź kontekst czasowy, potem skorzystaj z wyników wyszukiwania z internetu (jeśli zostały dostarczone)
- Jeśli w wiadomości od systemu znajdują się wyniki wyszukiwania z internetu, oprzyj na nich odpowiedź
- ZAWSZE uwzględniaj aktualną datę przy odpowiedziach dotyczących "dzisiaj", "wczoraj", "jutro" itp."""

# ── Persistence ───────────────────────────────────────────────
CONV_DIR = Path(os.path.expanduser("~/.assistant_conversations"))
CONV_DIR.mkdir(parents=True, exist_ok=True)

# ── Weather: Open-Meteo (free, no API key) ───────────────────
# WMO weather codes → Polish descriptions
WMO_CODES: dict[int, str] = {
    0: "bezchmurne niebo", 1: "prawie bezchmurnie",
    2: "częściowo pochmurno", 3: "pochmurno",
    45: "mgła", 48: "szadź",
    51: "mżawka lekka", 53: "mżawka umiarkowana", 55: "mżawka gęsta",
    61: "deszcz lekki", 63: "deszcz umiarkowany", 65: "deszcz silny",
    71: "śnieg lekki", 73: "śnieg umiarkowany", 75: "śnieg silny",
    77: "ziarna śnieżne",
    80: "przelotny deszcz lekki", 81: "przelotny deszcz", 82: "przelotny deszcz gwałtowny",
    85: "przelotny śnieg lekki", 86: "przelotny śnieg silny",
    95: "burza", 96: "burza z gradem lekkim", 99: "burza z gradem silnym",
}

# City coordinates (lat, lon)
CITY_COORDS: dict[str, tuple[float, float]] = {
    "natolin": (52.136393, 20.622824),
    "warszawa": (52.23, 21.01),
    "warszawie": (52.23, 21.01),
    "warsaw": (52.23, 21.01),
    "pruszków": (52.17, 20.80),
    "pruszkow": (52.17, 20.80),
    "ožarów": (52.21, 20.81),
    "ozarow": (52.21, 20.81),
    "ožarowie": (52.21, 20.81),
    "piastów": (52.18, 20.85),
    "piastow": (52.18, 20.85),
    "ursus": (52.19, 20.88),
    "grodzisk": (52.11, 20.63),
    "milanówek": (52.12, 20.67),
    "milanowek": (52.12, 20.67),
    "kraków": (50.06, 19.94),
    "krakow": (50.06, 19.94),
    "wrocław": (51.11, 17.04),
    "wroclaw": (51.11, 17.04),
    "gdańsk": (54.35, 18.65),
    "gdansk": (54.35, 18.65),
    "poznań": (52.41, 16.93),
    "poznan": (52.41, 16.93),
    "łódź": (51.76, 19.46),
    "lodz": (51.76, 19.46),
}

DEFAULT_COORDS = (52.136393, 20.622824)  # Natolin 43, 05-825

WEATHER_KEYWORDS = re.compile(
    r'\b(pogoda|pogodę|pogody|temperatura|temperaturę|ciepło|zimno|deszcz|'
    r'śnieg|snieg|burza|burzy|wiatr|wietrznie|słonecznie|słoneczna|'
    r'stopni|parasol|mżawka|mzawka|pochmurno|mgła|mgle)\b',
    re.IGNORECASE
)


def extract_city(text: str) -> tuple[str, float, float]:
    """Try to find a known city in the query; returns (name, lat, lon)."""
    text_lower = text.lower()
    for name, coords in CITY_COORDS.items():
        if name in text_lower:
            return (name, *coords)
    return ("Natolin", *DEFAULT_COORDS)


async def fetch_weather(lat: float, lon: float) -> str:
    """Pobiera prognozę z Open-Meteo i zwraca sformatowany opis po polsku."""
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode"
        f"&current=temperature_2m,relative_humidity_2m,weathercode,wind_speed_10m"
        f"&timezone=Europe/Warsaw"
        f"&forecast_days=3"
    )
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return ""
                data = await resp.json()
    except Exception as e:
        print(f"   Weather API error: {e}")
        return ""

    lines = ["[PROGNOZA POGODY — Open-Meteo]"]

    # Current conditions
    current = data.get("current", {})
    if current:
        code = current.get("weathercode", 0)
        temp = current.get("temperature_2m", "?")
        wind = current.get("wind_speed_10m", "?")
        desc = WMO_CODES.get(code, f"kod {code}")
        lines.append(
            f"Teraz: {temp}°C, {desc}, wiatr {wind} km/h"
        )

    # Daily forecast
    daily = data.get("daily", {})
    dates = daily.get("time", [])
    codes = daily.get("weathercode", [])
    temps_max = daily.get("temperature_2m_max", [])
    temps_min = daily.get("temperature_2m_min", [])
    precip = daily.get("precipitation_sum", [])

    if dates:
        lines.append("Prognoza na kolejne dni:")
        for i, date in enumerate(dates):
            code = codes[i] if i < len(codes) else 0
            tmax = temps_max[i] if i < len(temps_max) else "?"
            tmin = temps_min[i] if i < len(temps_min) else "?"
            rain = precip[i] if i < len(precip) else 0
            desc = WMO_CODES.get(code, f"kod {code}")
            rain_str = f", opady {rain} mm" if rain > 0 else ""
            lines.append(f"  {date}: {tmin}–{tmax}°C, {desc}{rain_str}")

    return "\n".join(lines)

# In-memory cache (fast path)
conversations: dict[str, list[dict]] = {}
MAX_HISTORY = 20


def _conv_file(session_id: str) -> Path:
    safe = re.sub(r'[^a-zA-Z0-9_-]', '_', session_id)[:64]
    return CONV_DIR / f"{safe}.json"


def load_conversation(session_id: str) -> list[dict]:
    if session_id in conversations:
        return conversations[session_id]
    fpath = _conv_file(session_id)
    if fpath.exists():
        try:
            data = json.loads(fpath.read_text())
            if isinstance(data, list):
                conversations[session_id] = data
                return data
        except Exception:
            pass
    conversations[session_id] = []
    return conversations[session_id]


def save_conversation(session_id: str, history: list[dict]):
    conversations[session_id] = history
    try:
        _conv_file(session_id).write_text(json.dumps(history, ensure_ascii=False))
    except Exception as e:
        print(f"⚠️  Failed to save conversation {session_id}: {e}")


def prune_history(history: list[dict]) -> list[dict]:
    if len(history) > MAX_HISTORY:
        return history[-MAX_HISTORY:]
    return history


# ── Web search ────────────────────────────────────────────────
REALTIME_KEYWORDS = [
    # Pogoda / czas
    "pogoda", "pogodę", "temperatura", "dzisiaj", "dziś", "teraz",
    "aktualny", "aktualna", "aktualne", "aktualnie", "najnowszy",
    "wczoraj", "jutro", "jutrzejszy", "w tym tygodniu", "w weekend",
    "niedziela", "poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota",
    # Finanse / kursy
    "kurs", "cena", "cenę", "walut", "euro", "dolar", "złoty",
    # Newsy /wydarzenia
    "news", "wiadomości", "wiadomość", "co słychać", "co nowego",
    "wydarzyło", "stało się", "ogłosili", "wyniki", "wynik",
    "gdzie jest", "kiedy jest", "ile kosztuje", "o której",
    "imieniny", "imienin", "święto", "święta",
    # Wypadki / drogi / ruch
    "wypadek", "kolizja", "kolizję", "zderzenie", "wypadku",
    "zawody", "blokady", "blokada", "protest", "zamknięta", "zamknięty",
    "objazd", "utrudnienie", "utrudnienia", "droga", "drogowy",
    "trasa", "trasie", "autostrada", "korek", "korki",
    "S8", "A2", "DK92", "DK7", "DK8", "S7", "S2", "A1",
    # Lokacje (lokalne)
    "Pruszków", "Pruszkowa", "Tolin", "Tolina", "Warszawa", "Warszawie",
    "Ożarów", "Ożarowie", "Piastów", "Piastowie", "Ursus",
]

REALTIME_PATTERN = re.compile(
    r'\b(' + '|'.join(re.escape(k) for k in REALTIME_KEYWORDS) + r')\b',
    re.IGNORECASE
)


def needs_search(text: str) -> bool:
    """Check if the query likely needs real-time data."""
    return bool(REALTIME_PATTERN.search(text))


async def search_web(query: str, max_results: int = 5) -> str:
    """Search DuckDuckGo and return formatted results for the AI prompt."""
    try:
        results = await asyncio.to_thread(
            lambda: list(DDGS().text(query, max_results=max_results))
        )
        if not results:
            return ""
        lines = ["[WYNIKI WYSZUKIWANIA Z INTERNETU:]"]
        for i, r in enumerate(results, 1):
            title = r.get("title", "")
            body = r.get("body", "")
            lines.append(f"{i}. {title}\n   {body}")
        return "\n".join(lines)
    except Exception as e:
        print(f"Search error: {e}")
        return ""


# ── Routes ───────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "voices": list(VOICES.keys()),
        "ai_ready": DS_API_KEY is not None,
    }


@app.get("/api/tts")
async def tts(
    text: str = Query(..., description="Tekst do wypowiedzenia"),
    voice: str = Query("zofia", description="Głos: zofia lub marek"),
    rate: str = Query("+0%", description="Szybkość: -50% do +50%"),
    pitch: str = Query("+0Hz", description="Wysokość: -20Hz do +20Hz"),
):
    voice_id = VOICES.get(voice)
    if not voice_id:
        raise HTTPException(400, f"Nieznany głos. Dostępne: {list(VOICES.keys())}")

    safe_text = text.strip()[:2000]
    if not safe_text:
        raise HTTPException(400, "Brak tekstu")

    communicate = edge_tts.Communicate(
        text=safe_text,
        voice=voice_id,
        rate=rate,
        pitch=pitch,
    )

    async def audio_stream():
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                yield chunk["data"]

    return StreamingResponse(
        audio_stream(),
        media_type="audio/mpeg",
        headers={
            "X-Voice": voice_id,
            "Cache-Control": "no-cache",
        },
    )


@app.get("/api/tts/download")
async def tts_download(
    text: str = Query(...),
    voice: str = Query("zofia"),
    rate: str = Query("+0%"),
    pitch: str = Query("+0Hz"),
):
    voice_id = VOICES.get(voice)
    if not voice_id:
        raise HTTPException(400, f"Nieznany głos. Dostępne: {list(VOICES.keys())}")

    safe_text = text.strip()[:2000]
    communicate = edge_tts.Communicate(text=safe_text, voice=voice_id, rate=rate, pitch=pitch)
    mp3_bytes = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            mp3_bytes.write(chunk["data"])

    mp3_bytes.seek(0)
    safe_filename = re.sub(r'[^\w\s-]', '', safe_text)[:50] or "mowa"
    return Response(
        content=mp3_bytes.getvalue(),
        media_type="audio/mpeg",
        headers={"Content-Disposition": f'attachment; filename="{safe_filename}.mp3"'},
    )


@app.post("/api/chat")
async def chat(request: Request):
    """Endpoint AI z wyszukiwarką internetową i pamięcią trwałą."""
    if not DS_API_KEY:
        raise HTTPException(503, "AI nie jest skonfigurowane — brak klucza API DeepSeek")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Nieprawidłowy JSON")

    user_text = (body.get("text") or "").strip()
    session_id = body.get("session_id", "default")

    if not user_text:
        raise HTTPException(400, "Brak tekstu (pole 'text')")

    # Load from disk if not in memory
    history = load_conversation(session_id)

    # ── Web search if needed ─────────────────────────────────
    search_context = ""
    weather_context = ""

    # Weather first (dedicated API, always accurate)
    if WEATHER_KEYWORDS.search(user_text):
        city_name, lat, lon = extract_city(user_text)
        print(f"🌤️  Fetching weather for {city_name} ({lat},{lon})...")
        weather_context = await fetch_weather(lat, lon)
        if weather_context:
            print(f"   Got weather data ({weather_context.count(chr(10))} lines)")

    # General web search for other queries
    if needs_search(user_text):
        print(f"🔍 Searching web for: {user_text[:80]}...")
        search_context = await search_web(user_text)
        if search_context:
            print(f"   Got {search_context.count(chr(10))} lines of results")

    # Build messages
    messages = [{"role": "system", "content": build_system_prompt()}]

    # Add weather data as context (before search results — weather is authoritative)
    if weather_context:
        messages.append({
            "role": "system",
            "content": f"{weather_context}\n\nUżyj tych danych pogodowych w odpowiedzi — są aktualne i dokładne."
        })

    # Add search results as a system message
    if search_context:
        messages.append({
            "role": "system",
            "content": f"Aktualne dane z internetu:\n{search_context}\n\nUżyj tych danych w odpowiedzi."
        })

    messages.extend(history)
    messages.append({"role": "user", "content": user_text})

    # Call DeepSeek API
    headers = {
        "Content-Type": "application/json",
        "x-api-key": DS_API_KEY,
        "anthropic-version": "2023-06-01",
    }

    payload = {
        "model": DS_MODEL,
        "max_tokens": 1024,
        "messages": messages,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{DS_BASE_URL}/v1/messages",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=35),
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    print(f"DeepSeek API error {resp.status}: {error_text[:300]}")
                    raise HTTPException(502, f"Błąd API AI: {resp.status}")

                result = await resp.json()

        ai_text = ""
        for block in result.get("content", []):
            if block.get("type") == "text":
                ai_text += block.get("text", "")

        if not ai_text:
            ai_text = "Przepraszam, nie mogę teraz odpowiedzieć. Spróbuj jeszcze raz."

        # Update + persist history
        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": ai_text})
        history = prune_history(history)
        save_conversation(session_id, history)

        return JSONResponse({
            "response": ai_text,
            "session_id": session_id,
            "history_length": len(history),
            "searched": bool(search_context),
        })

    except aiohttp.ClientError as e:
        print(f"DeepSeek API connection error: {e}")
        raise HTTPException(502, f"Nie można połączyć się z API AI: {e}")
    except Exception as e:
        print(f"Chat error: {e}")
        raise HTTPException(500, f"Błąd wewnętrzny: {e}")


@app.delete("/api/chat/{session_id}")
async def clear_chat(session_id: str):
    """Wyczyść historię konwersacji dla danej sesji (RAM + dysk)."""
    if session_id in conversations:
        del conversations[session_id]
    try:
        fpath = _conv_file(session_id)
        if fpath.exists():
            fpath.unlink()
    except Exception:
        pass
    return {"status": "ok", "message": "Historia wyczyszczona"}


@app.get("/api/search")
async def web_search(
    q: str = Query(..., description="Zapytanie do wyszukiwarki"),
    n: int = Query(3, description="Liczba wyników"),
):
    """Bezpośrednie wyszukiwanie w DuckDuckGo."""
    try:
        results = await search_web(q, max_results=n)
        return JSONResponse({
            "query": q,
            "results": results,
        })
    except Exception as e:
        raise HTTPException(500, f"Błąd wyszukiwania: {e}")


# Serwuj statyczne pliki frontendu
app.mount("/", StaticFiles(directory="static", html=True), name="static")
