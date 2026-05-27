#!/usr/bin/env bash
set -euo pipefail

app_name="mp3qt"

sudo rm -rf "/opt/${app_name}"
sudo rm -f "/usr/share/applications/${app_name}.desktop"
sudo rm -f "/usr/share/icons/hicolor/64x64/apps/${app_name}.png"
sudo rm -f "/usr/local/bin/${app_name}"

if command -v update-desktop-database >/dev/null 2>&1; then
  sudo update-desktop-database /usr/share/applications >/dev/null 2>&1 || true
fi

echo "Uninstalled ${app_name}"
