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

# 2. Comprobar los modelos 3D (VPK del Workshop de Left 4 Dead 2)
#    Natsuki=2565563118  Sayori=2567184223  Monika=2561380893  Yuri=2564088900
VPK_IDS=(2565563118 2567184223 2561380893 2564088900)
WORKSHOP_DIR=""
for cand in \
  "${L4D2_WORKSHOP_DIR:-}" \
  "$ROOT/l4d2_workshop_vpks" \
  "$HOME/.local/share/Steam/steamapps/common/Left 4 Dead 2/left4dead2/addons/workshop" \
  "$HOME/.steam/steam/steamapps/common/Left 4 Dead 2/left4dead2/addons/workshop" \
  "$HOME/.var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps/common/Left 4 Dead 2/left4dead2/addons/workshop"; do
  if [[ -n "$cand" && -f "$cand/${VPK_IDS[0]}.vpk" ]]; then
    WORKSHOP_DIR="$cand"
    break
  fi
done

MISSING=()
for id in "${VPK_IDS[@]}"; do
  if [[ -z "$WORKSHOP_DIR" || ! -f "$WORKSHOP_DIR/$id.vpk" ]]; then
    MISSING+=("$id")
  fi
done

if (( ${#MISSING[@]} > 0 )); then
  echo "ERROR: faltan modelos 3D del Workshop de Left 4 Dead 2: ${MISSING[*]}" >&2
  echo "  Suscribete a esos items en https://steamcommunity.com/app/550/workshop/ ," >&2
  echo "  descargalos desde Steam, o apunta L4D2_WORKSHOP_DIR a la carpeta con los .vpk." >&2
  exit 1
fi
echo "-> Modelos 3D encontrados en: $WORKSHOP_DIR"

# 3. Respaldar originales (.bak_orig) si existen y copiar los archivos ya generados (si los hay)
INSTALLED_ANY=0
for sub in Animations Maps Music "Paradise Lost" ShareThePain Sounds System Textures; do
  if [[ -d "$ROOT/$sub" ]]; then
    echo "-> Instalando $sub/ ..."
    INSTALLED_ANY=1
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

if (( INSTALLED_ANY == 0 )); then
  echo "-> No hay archivos precompilados en el repo: genera el mod con:"
  echo "     python3 install_doki_skins.py     # skins 3D + selector de Dokis"
  echo "     python3 install_doki_audio.py     # musica de menu y voz (opcional, necesita DokiMenu.ogg)"
  exit 0
fi

echo "=== Mod Doki Doki Postal Club instalado correctamente en: $P2_DIR ==="
