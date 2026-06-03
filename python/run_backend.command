#!/bin/zsh
cd "/Users/efeduzcay/Desktop/robot-3.0.0/python"
echo "═══════════════════════════════════════════"
echo "  OYTS Backend — Terminal launcher"
echo "  (kamera iznini Terminal.app'ten miras alır)"
echo "═══════════════════════════════════════════"
exec /usr/bin/python3 web_app.py --port 5050 --autostart
