# Doki-Doki-Postal-Club

mod for postal 2 that brings anime to it LOL

Mod que reemplaza al "Dude" de **POSTAL 2** (y a algunos NPC) por las 4 Dokis de DDLC, con modelos 3D,
selector de personaje, y musica de menu y voz opcionales. Funciona en Linux con Steam/Proton.

> Este repo **no incluye** archivos del juego ni modelos de terceros. El instalador genera las skins a partir
> de **tu** copia de POSTAL 2 y de los modelos del Workshop de Left 4 Dead 2 que tengas descargados.

## Requisitos

- **POSTAL 2 Complete** instalado en Steam (se busca en `~/.local/share/Steam/steamapps/common/POSTAL2Complete`;
  usa `POSTAL2_ROOT=/ruta` en `instalar_postal2_mod.sh` si esta en otro lado).
- **Python 3**.
- Los **4 modelos 3D del Workshop de Left 4 Dead 2** (ver abajo).
- Opcional, solo para la voz: `ffmpeg` y `rubberband`.
- Opcional, solo para el jiggle de los modelos: Blender (`blender_doki_jiggle_psk.py`).

## Modelos 3D (Workshop de L4D2)

Los modelos no estan en el repo. Suscribete a estos items en el Workshop de Left 4 Dead 2 y deja que Steam
los descargue (cada `.vpk` se llama como el ID del item):

| Doki | ID del Workshop | Modelo original que usa |
|---|---|---|
| Natsuki | [2565563118](https://steamcommunity.com/sharedfiles/filedetails/?id=2565563118) | `survivor_gambler` |
| Sayori | [2567184223](https://steamcommunity.com/sharedfiles/filedetails/?id=2567184223) | `survivor_producer` |
| Monika | [2561380893](https://steamcommunity.com/sharedfiles/filedetails/?id=2561380893) | `survivor_mechanic` |
| Yuri | [2564088900](https://steamcommunity.com/sharedfiles/filedetails/?id=2564088900) | `survivor_coach` |

`retarget.py` busca los `.vpk` en este orden:

1. La variable de entorno `L4D2_WORKSHOP_DIR`.
2. Una carpeta `l4d2_workshop_vpks/` junto a los scripts.
3. `Left 4 Dead 2/left4dead2/addons/workshop/` dentro de tu carpeta de Steam.

## Instalacion

```bash
./instalar_postal2_mod.sh        # comprueba POSTAL 2 y los .vpk; avisa si falta alguno
python3 install_doki_skins.py    # crea las skins y parchea los paquetes del juego
python3 install_doki_audio.py    # opcional: musica de menu y voz
```

`install_doki_skins.py` hace copias de seguridad (`*.bak_orig`) de cada archivo antes de tocarlo.

El audio necesita un archivo `DokiMenu.ogg` junto a los scripts: **no esta en el repo**, pon el tuyo.

## Selector de Dokis

Dentro del juego (teclas definidas en `User.ini`):

| Tecla | Doki |
|---|---|
| `F2` / `NumPad1` | Natsuki |
| `F3` / `NumPad2` | Sayori |
| `F4` / `NumPad3` | Monika |
| `F7` / `NumPad4` | Yuri |

Tambien por consola: `Natsuki`, `Sayori`, `Monika`, `Yuri` (o `Doki1`..`Doki4`).

## Desinstalar

```bash
./restore_postal2_originals.sh
```

Restaura los archivos originales desde los `*.bak_orig` y borra los archivos que anadio el mod.

## Contenido del repo

| Archivo | Para que sirve |
|---|---|
| `install_doki_skins.py` | Instalador principal: skins, parches de paquetes e `.ini` |
| `install_doki_audio.py` | Musica de menu y voz |
| `retarget.py` | Convierte los modelos de L4D2 a mallas de Postal 2 |
| `source_loader.py` | Lector de VPK/MDL/VVD/VTX/VMT/VTF de Source |
| `ue2_io.py` | Lectura y escritura de paquetes de Unreal Engine 2 |
| `blender_doki_jiggle_psk.py` | Script de Blender: volumen del pecho y huesos `jiggle_L`/`jiggle_R` |
| `DokiPostalPawn.uc` | Clase UnrealScript con la fisica secundaria |
| `restore_postal2_originals.sh` | Desinstalador |

## Aviso

Proyecto de fans, sin relacion con Team Salvato, Running With Scissors ni Valve. Doki Doki Literature Club y
POSTAL 2 son marcas de sus respectivos duenos. Los modelos del Workshop pertenecen a sus autores.
