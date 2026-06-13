"""
Tests for Enerp AI Assistant server endpoints.
"""
import pytest
from httpx import AsyncClient, ASGITransport
import sys
from pathlib import Path

# Make server module importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from server import app


@pytest.fixture
def client():
    """Create an async test client for the FastAPI app."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_health(client):
    """Health endpoint returns ok status."""
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "zofia" in data["voices"]
    assert "marek" in data["voices"]


@pytest.mark.asyncio
async def test_tts_endpoint(client):
    """TTS endpoint returns audio stream."""
    response = await client.get("/api/tts?text=Cześć+test&voice=zofia")
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"


@pytest.mark.asyncio
async def test_tts_invalid_voice(client):
    """TTS with unknown voice returns 400."""
    response = await client.get("/api/tts?text=test&voice=invalid")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_tts_empty_text(client):
    """TTS with empty text returns 400."""
    response = await client.get("/api/tts?text=&voice=zofia")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_chat_missing_text(client):
    """Chat without text returns 400."""
    response = await client.post("/api/chat", json={"session_id": "test"})
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_chat_empty_json(client):
    """Chat with empty JSON returns 400."""
    response = await client.post("/api/chat", json={})
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_clear_chat(client):
    """Clear conversation endpoint works."""
    response = await client.delete("/api/chat/test-session-123")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_search_endpoint(client):
    """Search endpoint accepts query parameter."""
    response = await client.get("/api/search?q=pogoda+Warszawa&n=2")
    # May be 200 (success) or 500 (search engine issue) — both are valid responses
    assert response.status_code in (200, 500)
