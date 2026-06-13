#!/bin/bash
# Skrypt instalacyjny asystentki
# Uruchom jako root lub z sudo: sudo bash setup.sh

set -e

echo "🔧 Instalacja Asystentki..."
echo ""

# 1. Install system packages
echo "📦 Instalacja pakietów systemowych..."
apt-get update -qq
apt-get install -y -qq python3-pip python3.12-venv nginx certbot python3-certbot-nginx

# 2. Python virtual environment
echo "🐍 Tworzenie środowiska Python..."
cd /home/rancher/assistant-web
python3 -m venv venv
./venv/bin/pip install edge-tts fastapi uvicorn

# 3. Test edge-tts
echo "🔊 Testowanie edge-tts..."
./venv/bin/python3 -c "
import asyncio
import edge_tts
async def test():
    communicate = edge_tts.Communicate('Test polskiego głosu.', 'pl-PL-ZofiaNeural')
    async for chunk in communicate.stream():
        if chunk['type'] == 'audio':
            print('✅ edge-tts działa poprawnie (pobrano dane audio)')
            return
asyncio.run(test())
"

# 4. Copy nginx config
echo "🌐 Konfiguracja nginx..."
cp /home/rancher/assistant-web/nginx-assistant.conf /etc/nginx/sites-available/assistant.enerp.pl
ln -sf /etc/nginx/sites-available/assistant.enerp.pl /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test nginx config
nginx -t

# 5. Install systemd service
echo "⚙️  Instalacja usługi systemd..."
cp /home/rancher/assistant-web/asystentka.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable asystentka
systemctl start asystentka

# 6. Start nginx
systemctl enable nginx
systemctl restart nginx

echo ""
echo "✅ Instalacja zakończona!"
echo "   Sprawdź usługę: systemctl status asystentka"
echo "   Logi: journalctl -u asystentka -f"
echo ""
echo "🌍 Następny krok: skonfiguruj DNS w Cloudflare:"
echo "   Dodaj rekord A: assistant.enerp.pl → $(hostname -I | awk '{print $1}')"
echo "   Potem uruchom: sudo certbot --nginx -d assistant.enerp.pl"
