#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd -- "${script_dir}/.." && pwd)"

app_name="mp3qt"
build_dir="${project_root}/dist/${app_name}"

(cd "${project_root}" && pyinstaller \
  --distpath "${project_root}/dist" \
  --workpath "${project_root}/build" \
  "${project_root}/linux.spec")

if [[ ! -d "${build_dir}" ]]; then
  echo "Build not found after PyInstaller run: ${build_dir}"
  exit 1
fi

opt_dir="/opt/${app_name}"
apps_dir="/usr/share/applications"
icons_dir="/usr/share/icons/hicolor/64x64/apps"
bin_dir="/usr/local/bin"

sudo mkdir -p "${opt_dir}" "${apps_dir}" "${icons_dir}" "${bin_dir}"
sudo rsync -a --delete "${build_dir}/" "${opt_dir}/"
sudo chmod +x "${opt_dir}/${app_name}"

sudo install -m 644 "${project_root}/assets/mp3-logo.png" "${icons_dir}/${app_name}.png"

desktop_src="${project_root}/scripts/${app_name}.desktop"
desktop_dst="${apps_dir}/${app_name}.desktop"
sudo install -m 644 "${desktop_src}" "${desktop_dst}"

sudo ln -sfn "${opt_dir}/${app_name}" "${bin_dir}/${app_name}"

if command -v update-desktop-database >/dev/null 2>&1; then
  sudo update-desktop-database "${apps_dir}" >/dev/null 2>&1 || true
fi

echo "Installed to ${opt_dir}"
echo "Desktop entry: ${desktop_dst}"
echo "CLI: ${bin_dir}/${app_name}"
