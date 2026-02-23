#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd -- "${script_dir}/.." && pwd)"

app_name="mp3qt"
build_dir="${project_root}/dist/${app_name}"
system_install=false

usage() {
  cat <<EOF
Usage: $(basename "$0") [--system]

Options:
  --system   Install system-wide (requires sudo).
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

pyinstaller \
  --distpath "${project_root}/dist" \
  --workpath "${project_root}/build" \
  "${project_root}/app.spec"

if [[ ! -d "${build_dir}" ]]; then
  echo "Build not found after PyInstaller run: ${build_dir}"
  exit 1
fi

if [[ "${system_install}" == "true" ]]; then
  opt_dir="/opt/${app_name}"
  apps_dir="/usr/share/applications"
  icons_dir="/usr/share/icons/hicolor/64x64/apps"
  bin_dir="/usr/local/bin"
  install_cmd=(sudo install)
  rsync_cmd=(sudo rsync)
  mkdir_cmd=(sudo mkdir -p)
  ln_cmd=(sudo ln -sfn)
else
  data_home="${XDG_DATA_HOME:-${HOME}/.local/share}"
  opt_dir="${HOME}/.local/opt/${app_name}"
  apps_dir="${data_home}/applications"
  icons_dir="${data_home}/icons/hicolor/64x64/apps"
  bin_dir="${HOME}/.local/bin"
  install_cmd=(install)
  rsync_cmd=(rsync)
  mkdir_cmd=(mkdir -p)
  ln_cmd=(ln -sfn)
fi

if [[ "${system_install}" == "true" ]]; then
  "${mkdir_cmd[@]}" "${opt_dir}" "${apps_dir}" "${icons_dir}"
else
  "${mkdir_cmd[@]}" "${opt_dir}" "${apps_dir}" "${icons_dir}" "${bin_dir}"
fi

"${rsync_cmd[@]}" -a --delete "${build_dir}/" "${opt_dir}/"
if [[ "${system_install}" == "true" ]]; then
  sudo chmod +x "${opt_dir}/${app_name}"
else
  chmod +x "${opt_dir}/${app_name}"
fi

"${install_cmd[@]}" -m 644 "${project_root}/assets/mp3-logo.png" "${icons_dir}/${app_name}.png"

desktop_src="${project_root}/scripts/${app_name}.desktop"
desktop_dst="${apps_dir}/${app_name}.desktop"
if [[ "${system_install}" == "true" ]]; then
  sed "s#\\\${INSTALL_DIR}#${opt_dir}#g" "${desktop_src}" | sudo tee "${desktop_dst}" >/dev/null
else
  sed "s#\\\${INSTALL_DIR}#${opt_dir}#g" "${desktop_src}" > "${desktop_dst}"
fi

"${ln_cmd[@]}" "${opt_dir}/${app_name}" "${bin_dir}/${app_name}"

if command -v update-desktop-database >/dev/null 2>&1; then
  if [[ "${system_install}" == "true" ]]; then
    sudo update-desktop-database "${apps_dir}" >/dev/null 2>&1 || true
  else
    update-desktop-database "${apps_dir}" >/dev/null 2>&1 || true
  fi
fi

echo "Installed to ${opt_dir}"
echo "Desktop entry: ${desktop_dst}"
echo "CLI: ${bin_dir}/${app_name}"
