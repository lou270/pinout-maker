# Pinout Maker

Generate annotated pinout SVGs for PCBs. Works either:

- **Inside KiCad** as an *Action Plugin* (install via KiCad's Plugin and Content Manager, click the toolbar icon).
- **Standalone** via CLI or a Tkinter GUI, starting from a gerber F.Mask SVG + a PNG render.

## Install in KiCad (PCM)

### One-click via third-party repository

1. Open KiCad → *Plugin and Content Manager* → *Manage repositories…* → *+*.
2. Add `https://github.com/lou270/pinout-maker/releases/latest/download/metadata.json` (or whatever the published URL is).
3. Select the new repository, find **Pinout Maker** under *Plugins*, click *Install*.
4. Restart the PCB editor — a new toolbar icon appears.

### Manual install (any KiCad 7+)

1. Download `com.berry_rocket.pinout_maker.zip` from the [Releases](https://github.com/lou270/pinout-maker/releases) page.
2. KiCad → *Plugin and Content Manager* → *Install from file* → select the zip.

### Using it

1. Open your board in the PCB editor.
2. Click the Pinout Maker toolbar icon (or *Tools → External Plugins → Pinout Maker*).
3. A dialog shows every pad detected on your connector footprints (`J*`, `CN*`, `P*`).
   - Labels are pre-filled with net names.
   - Functions are pre-filled by matching net names/classes against `plugins/netclass_map.json`.
4. Edit freely — add or remove rows, change sides, override functions.
5. Choose the output SVG path and click **Generate**.

## Standalone CLI

```bash
# 1. Produce a template CSV from a gerber F.Mask SVG
python main.py --input-svg examples/br_micro_sensor-F_Mask.svg --generate-template

# 2. Fill in pins_template.csv (number, label, function)

# 3. Render the pinout
python main.py \
    --input-svg   examples/br_micro_sensor-F_Mask.svg \
    --board-image examples/br_micro_sensor_top_view.png \
    --pins        examples/pins_template.csv \
    --output      examples/output_pinout.svg
```

## Standalone Tkinter GUI

```bash
python gui.py
```

## Repository layout

```
pinout-maker/
├── metadata.json         # KiCad PCM manifest
├── resources/icon.png    # Toolbar icon (64×64)
├── plugins/              # Everything PCM copies when installing
│   ├── __init__.py             registers ActionPlugin
│   ├── pinout_plugin.py        ActionPlugin class
│   ├── board_parser.py         pcbnew.BOARD → Pin list
│   ├── board_render.py         Top-view PNG rendering
│   ├── dialog.py               wxPython edit dialog
│   ├── function.py / Pin.py / svg.py / save.py    shared rendering modules
│   ├── config.json             function categories and colours
│   └── netclass_map.json       net-name/class → function rules
├── main.py / gui.py      Standalone CLI and Tkinter GUI
├── examples/             Sample boards and CSVs
└── scripts/
    └── build_pcm_package.py   Build the PCM zip for release
```

## Releasing

Tagging `vX.Y.Z` triggers `.github/workflows/release.yml`, which runs
`scripts/build_pcm_package.py` and uploads `com.berry_rocket.pinout_maker.zip`
plus `metadata.json` as release assets. Point your PCM third-party repository URL
at the release's `metadata.json` to distribute it.

## License

MIT — see individual source files.
