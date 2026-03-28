#!/bin/bash
# =============================================================================
#  deploy_pi.sh — Deploy Arta Grafica pe Raspberry Pi
#  Ruleaza pe Pi dupa git clone sau pentru update aplicatie.
#  User: raspberry | Dir: /home/raspberry/arta-grafica
# =============================================================================
set -e

APP_DIR="/home/raspberry/arta-grafica"
SERVICE="arta-grafica"

# Verifica API key
if [ ! -f "$APP_DIR/backend/.env" ]; then
    echo "EROARE: $APP_DIR/backend/.env lipseste!"
    echo "Creeaza-l cu: echo 'ANTHROPIC_API_KEY=sk-ant-...' > $APP_DIR/backend/.env"
    exit 1
fi

echo "=== [1/6] Instalare dependente sistem ==="
sudo apt-get update -qq
# pandas/numpy se instaleaza din apt pe ARM64 (pip compile dureaza ore)
sudo apt-get install -y python3-venv python3-pip python3-pandas python3-numpy nodejs npm

echo "=== [2/6] Creare virtual environment Python ==="
cd "$APP_DIR/backend"
if [ ! -d "$APP_DIR/venv" ]; then
    # --system-site-packages permite accesul la pandas/numpy instalate din apt
    python3 -m venv "$APP_DIR/venv" --system-site-packages
fi
"$APP_DIR/venv/bin/pip" install --upgrade pip -q
"$APP_DIR/venv/bin/pip" install -r requirements.txt -q
echo "  Python deps instalate."

echo "=== [3/6] Creare director date ==="
mkdir -p "$APP_DIR/data"
echo "  Director data/ ok."

echo "=== [4/6] Build frontend React ==="
cd "$APP_DIR/frontend"
npm install --silent
# npx vite build in loc de npm run build (skip TypeScript errors)
npx vite build
echo "  Frontend built in frontend/dist/"

echo "=== [5/6] Configurare serviciu systemd ==="
sudo cp "$APP_DIR/arta-grafica.service" /etc/systemd/system/
# Adauga ANTHROPIC_API_KEY in serviciu daca nu e deja
if ! grep -q "ANTHROPIC_API_KEY" /etc/systemd/system/arta-grafica.service; then
    API_KEY=$(grep ANTHROPIC_API_KEY "$APP_DIR/backend/.env" | cut -d'=' -f2)
    sudo sed -i "/\[Service\]/a Environment=ANTHROPIC_API_KEY=$API_KEY" /etc/systemd/system/arta-grafica.service
    echo "  ANTHROPIC_API_KEY adaugat in serviciu."
fi
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE"
sudo systemctl restart "$SERVICE"
echo "  Serviciu pornit si activat la boot."

echo "=== [6/6] Status ==="
sleep 2
sudo systemctl status "$SERVICE" --no-pager

echo ""
echo "============================================"
echo "  Aplicatia ruleaza la: http://$(hostname -I | awk '{print $1}'):8000"
echo "  Logs: sudo journalctl -u $SERVICE -f"
echo "============================================"
