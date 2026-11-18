#!/usr/bin/env bash
set -euo pipefail
P2="/home/foidslayer/.local/share/Steam/steamapps/common/POSTAL2Complete"
MANAGED=(
  "Animations/Characters.ukx"
  "Animations/heads.ukx"
  "Animations/MoreHeads.ukx"
  "Paradise Lost/System/Default.ini"
  "Paradise Lost/System/PLGame.u"
  "Paradise Lost/System/PLInventory.u"
  "Paradise Lost/System/PLPawns.u"
  "ShareThePain/Animations/Characters.ukx"
  "ShareThePain/Animations/heads.ukx"
  "ShareThePain/System/BasePeople.u"
  "ShareThePain/System/Default.ini"
  "ShareThePain/System/Inventory.u"
  "ShareThePain/System/MultiStuff.u"
  "ShareThePain/System/People.u"
  "ShareThePain/System/Postal2MP.ini"
  "System/AWPStuff.u"
  "System/BasePeople.u"
  "System/Default.ini"
  "System/GameTypes.u"
  "System/Inventory.u"
  "System/People.u"
  "Paradise Lost/Music/HeadAboveTheWater.ogg"
  "Paradise Lost/Music/PL-MenuMusic.ogg"
  "Paradise Lost/Music/menu2mk2.ogg"
  "Maps/Startup.fuk"
  "Maps/Startup-Halloween.fuk"
  "Maps/AWstartup.fuk"
  "Paradise Lost/Maps/Startup.fuk"
  "Paradise Lost/Maps/Startup-Apocalypse.fuk"
  "Sounds/DudeDialog.uax"
  "Sounds/AWDialog.uax"
  "Paradise Lost/Sounds/PL-Dialog.uax"
  "Paradise Lost/Sounds/PL-Dialog2.uax"
  "Paradise Lost/Sounds/PL-Dialog3.uax"
)
ADDED=(
  "Textures/DokiSkins.utx"
  "Music/DokiMenu.ogg"
  "Paradise Lost/Music/DokiMenu.ogg"
)
for rel in "${MANAGED[@]}"; do
  if [[ -f "$P2/$rel.bak_orig" ]]; then
    mv -f "$P2/$rel.bak_orig" "$P2/$rel"
    echo "Restored $rel"
  fi
done
for rel in "${ADDED[@]}"; do
  if [[ -f "$P2/$rel" ]]; then
    rm -f "$P2/$rel"
    echo "Removed $rel"
  fi
done
echo "Original Postal 2 files restored."
