#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Instalador de Doki Doki Postal Club ==="

# 1. Detectar carpeta POSTAL2Complete
P2_DIR="${POSTAL2_ROOT:-}"
if [[ -z "$P2_DIR" ]]; then
  for cand in \
    "$HOME/.local/share/Steam/steamapps/common/POSTAL2Complete" \
    "$HOME/.steam/steam/steamapps/common/POSTAL2Complete" \
    "$HOME/.var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps/common/POSTAL2Complete"; do
    if [[ -d "$cand" ]]; then
      P2_DIR="$cand"
      break
    fi
  done
fi

if [[ -z "$P2_DIR" || ! -d "$P2_DIR" ]]; then
  P2_DIR="$HOME/.local/share/Steam/steamapps/common/POSTAL2Complete"
  echo "-> Creando ruta esperada de Postal 2 en: $P2_DIR"
  mkdir -p "$P2_DIR"
else
  echo "-> POSTAL 2 detectado en: $P2_DIR"
fi

# 2. Copiar tambien los .vpk 3D a la ruta de Left 4 Dead 2 Workshop por si se usan los scripts de retarget
if [[ -d "$ROOT/postal2-doki-skins/l4d2_workshop_vpks" ]]; then
  WORKSHOP_TARGET="$HOME/.local/share/Steam/steamapps/common/Left 4 Dead 2/left4dead2/addons/workshop"
  mkdir -p "$WORKSHOP_TARGET"
  cp -f "$ROOT/postal2-doki-skins/l4d2_workshop_vpks/"*.vpk "$WORKSHOP_TARGET/"
fi

# 3. Respaldar originales (.bak_orig) si existen y copiar los archivos modeados
for sub in Animations Maps Music "Paradise Lost" ShareThePain Sounds System Textures; do
  if [[ -d "$ROOT/$sub" ]]; then
    echo "-> Instalando $sub/ ..."
    while IFS= read -r -d '' src_file; do
      rel="${src_file#$ROOT/}"
      dst_file="$P2_DIR/$rel"
      mkdir -p "$(dirname "$dst_file")"
      if [[ -f "$dst_file" && ! -f "$dst_file.bak_orig" ]]; then
        cp -f "$dst_file" "$dst_file.bak_orig"
      fi
      cp -f "$src_file" "$dst_file"
    done < <(find "$ROOT/$sub" -type f -print0)
  fi
done

echo "=== Mod Doki Doki Postal Club instalado correctamente en: $P2_DIR ==="
