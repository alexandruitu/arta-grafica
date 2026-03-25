#!/bin/bash
# =============================================================================
#  deploy_pi.sh — Deploy Arta Grafica pe Raspberry Pi
#  Ruleaza O SINGURA DATA pe Pi dupa ce ai copiat proiectul acolo.
#  Sau ruleaza din nou pentru a actualiza aplicatia.
# =============================================================================
set -e

APP_DIR="/home/pi/arta-grafica"
SERVICE="arta-grafica"

echo "=== [1/5] Instalare dependente sistem ==="
sudo apt-get update -qq
sudo apt-get install -y python3-venv python3-pip nodejs npm

echo "=== [2/5] Creare virtual environment Python ==="
cd "$APP_DIR/backend"
if [ ! -d "$APP_DIR/venv" ]; then
    python3 -m venv "$APP_DIR/venv"
fi
"$APP_DIR/venv/bin/pip" install --upgrade pip -q
"$APP_DIR/venv/bin/pip" install -r requirements.txt -q
echo "  Python deps instalate."

echo "=== [3/5] Build frontend React ==="
cd "$APP_DIR/frontend"
npm install --silent
npm run build
echo "  Frontend built in frontend/dist/"

echo "=== [4/5] Configurare serviciu systemd ==="
sudo cp "$APP_DIR/arta-grafica.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE"
sudo systemctl restart "$SERVICE"
echo "  Serviciu pornit si activat la boot."

echo "=== [5/5] Status ==="
sleep 2
sudo systemctl status "$SERVICE" --no-pager

echo ""
echo "============================================"
echo "  Aplicatia ruleaza la: http://$(hostname -I | awk '{print $1}'):8000"
echo "  Logs: sudo journalctl -u $SERVICE -f"
echo "============================================"
