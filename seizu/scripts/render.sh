#!/bin/sh
# SVG を PNG にして目視確認するための道具
CHROME=/opt/pw-browsers/chromium-1194/chrome-linux/chrome
SRC="$1"; OUT="$2"; W="${3:-800}"; H="${4:-900}"
"$CHROME" --headless --disable-gpu --no-sandbox --hide-scrollbars \
  --force-device-scale-factor=1 --window-size="$W,$H" \
  --screenshot="$OUT" "file://$SRC" 2>/dev/null
