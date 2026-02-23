#!/usr/bin/env bash
set -euo pipefail

app_name="mp3qt"
system_install=false

usage() {
  cat <<EOF
Usage: $(basename "$0") [--system]

Options:
  --system   Uninstall system-wide (requires sudo).
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --system)
      system_install=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ "${system_install}" == "true" ]]; then
  opt_dir="/opt/${app_name}"
  apps_dir="/usr/share/applications"
  icons_dir="/usr/share/icons/hicolor/64x64/apps"
  bin_dir="/usr/local/bin"
  rm_cmd=(sudo rm -f)
  rm_rf_cmd=(sudo rm -rf)
else
  data_home="${XDG_DATA_HOME:-${HOME}/.local/share}"
  opt_dir="${HOME}/.local/opt/${app_name}"
  apps_dir="${data_home}/applications"
  icons_dir="${data_home}/icons/hicolor/64x64/apps"
  bin_dir="${HOME}/.local/bin"
  rm_cmd=(rm -f)
  rm_rf_cmd=(rm -rf)
fi

"${rm_rf_cmd[@]}" "${opt_dir}"
"${rm_cmd[@]}" "${apps_dir}/${app_name}.desktop"
"${rm_cmd[@]}" "${icons_dir}/${app_name}.png"
"${rm_cmd[@]}" "${bin_dir}/${app_name}"

if command -v update-desktop-database >/dev/null 2>&1; then
  if [[ "${system_install}" == "true" ]]; then
    sudo update-desktop-database "${apps_dir}" >/dev/null 2>&1 || true
  else
    update-desktop-database "${apps_dir}" >/dev/null 2>&1 || true
  fi
fi

echo "Uninstalled ${app_name}"
