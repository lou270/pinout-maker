########################################
# Pinout image builder
# Louis Barbier
# MIT License
########################################

## Process
# Get real image of PCB
# Get gerber file
# Scale image with gerber file
# Find every holes in gerber
# Create a table to fill by user with pin number/function/name
# Export created image

import sys, os, argparse, csv
from PIL import Image
import math
import re
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'plugins'))

from function import *
import save
import svg
import Pin


def parse_args():
    parser = argparse.ArgumentParser(
        description='Pinout image builder — generates an annotated SVG pinout diagram.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Workflow:
  1. Generate a pin template CSV from your gerber mask:
       python main.py --input-svg mask.svg --generate-template

  2. Fill in pins_template.csv (number, label, function columns).

  3. Generate the final pinout:
       python main.py --input-svg mask.svg --board-image board.png --pins pins_template.csv

CSV format (one row per function box; multiple rows per pin for multiple functions):
  number,label,function
  1,VCC,Power
  2,GND,Ground
  3,TX,UART
  3,GPIO5,GPIO/PWM

Available function types are defined in config.json (Power, Ground, UART, etc.).
        """
    )
    parser.add_argument('--input-svg',   default=os.path.join('examples', 'br_micro_sensor-F_Mask.svg'),
                        help='Input SVG gerber mask file (default: %(default)s)')
    parser.add_argument('--board-image', default=os.path.join('examples', 'br_micro_sensor_top_view.png'),
                        help='Board top-view image PNG/JPG/BMP (default: %(default)s)')
    parser.add_argument('--output',      default=os.path.join('examples', 'output_pinout.svg'),
                        help='Output SVG file (default: %(default)s)')
    parser.add_argument('--pins',        metavar='FILE',
                        help='CSV file with pin labels and functions')
    parser.add_argument('--config',      default=os.path.join('plugins', 'config.json'),
                        help='Function config JSON (default: %(default)s)')
    parser.add_argument('--generate-template', action='store_true',
                        help='Detect pins and write pins_template.csv, then exit')
    parser.add_argument('--no-png', action='store_true',
                        help='Skip the PNG export alongside the SVG')
    parser.add_argument('--png-dpi', type=int, default=300,
                        help='DPI for the PNG export (default: %(default)s)')
    return parser.parse_args()


def load_pins_csv(csv_path, config):
    """Load pin definitions from a CSV file.

    CSV columns:
      number  – pin number (integer, matches detection order)
      label   – text shown in the function box
      function – function type name from config (determines colour)

    Multiple rows with the same number add multiple function boxes.
    Returns a dict: {pin_number: [{'name': label, 'color': hex}, ...]}
    """
    color_map = {f['name']: f['color'] for f in config.get('function', [])}

    pins_data = {}
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                number = int(row['number'])
            except (KeyError, ValueError):
                continue
            label    = row.get('label',    '').strip()
            func_key = row.get('function', '').strip()

            if not label and not func_key:
                continue  # skip empty rows

            color = color_map.get(func_key, '#888888')
            display_label = label or func_key or f'pin_{number}'

            pins_data.setdefault(number, []).append({
                'name':  display_label,
                'color': color,
            })

    return pins_data


def generate_template_csv(pins, output_path='pins_template.csv', config=None):
    """Write a template CSV pre-filled with detected pin numbers."""
    func_names = []
    if config:
        func_names = [f['name'] for f in config.get('function', [])]

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['number', 'label', 'function'])
        for pin in pins:
            writer.writerow([pin.number, '', ''])

    print(f"Template written to: {output_path}")
    print("Fill in 'label' (text shown in the box) and 'function' (colour category).")
    if func_names:
        print(f"Available functions: {', '.join(func_names)}")
    print("Add extra rows with the same 'number' to show multiple function boxes.")
    print(f"\nThen run:\n  python main.py --pins {output_path}")


def build_pinout(input_svg, board_image, output_file, pins_data,
                 export_png=True, png_dpi=300):
    """Core rendering logic, shared between CLI and GUI."""
    tree = ET.parse(input_svg)
    root = tree.getroot()

    svg_width  = float(root.attrib.get('width',  '100mm').replace('mm', ''))
    svg_height = float(root.attrib.get('height', '100mm').replace('mm', ''))
    svg_size   = (svg_width, svg_height)

    pin_detected = detect_pin(root.iter(), svg_size)
    print(f"Detected {len(pin_detected)} pins")

    for idx, pin in enumerate(pin_detected):
        pin.number    = idx + 1
        pin.displayed = True

        functions = pins_data.get(pin.number, [])
        if functions:
            for func in functions:
                pin.add_function(func['name'], func['color'])
        else:
            # Fallback: plain numbered label
            pin.add_function(f'pin_{pin.number}', '#888888')

        add_pin_graphics(root, pin)

    add_board_image(root, board_image, svg_width, svg_height)

    svg.update_bounding_box(root, margin=10)
    prettify_svg(root)
    tree.write(output_file)
    print(f"Pinout saved to: {output_file}")

    if export_png:
        png_path = os.path.splitext(output_file)[0] + '.png'
        if svg_to_png(output_file, png_path, dpi=png_dpi):
            print(f"PNG saved to:    {png_path}")
        else:
            print('PNG export skipped (no rasteriser found). '
                  'Install svglib+reportlab, cairosvg, inkscape, or librsvg to enable.')

    return pin_detected


def main():
    args = parse_args()

    if not os.path.isfile(args.input_svg):
        sys.exit(f"Error: input SVG not found: {args.input_svg}")
    if not os.path.isfile(args.config):
        sys.exit(f"Error: config file not found: {args.config}")

    config = save.from_json(args.config)

    # ── Generate template mode ────────────────────────────────────────────────
    if args.generate_template:
        tree = ET.parse(args.input_svg)
        root = tree.getroot()
        svg_width  = float(root.attrib.get('width',  '100mm').replace('mm', ''))
        svg_height = float(root.attrib.get('height', '100mm').replace('mm', ''))
        pins = detect_pin(root.iter(), (svg_width, svg_height))
        for idx, pin in enumerate(pins):
            pin.number = idx + 1
        generate_template_csv(pins, config=config)
        return

    # ── Normal render mode ────────────────────────────────────────────────────
    if not os.path.isfile(args.board_image):
        sys.exit(f"Error: board image not found: {args.board_image}")

    pins_data = {}
    if args.pins:
        if not os.path.isfile(args.pins):
            sys.exit(f"Error: pins CSV not found: {args.pins}")
        pins_data = load_pins_csv(args.pins, config)
        print(f"Loaded pin data for {len(pins_data)} pins from {args.pins}")

    build_pinout(args.input_svg, args.board_image, args.output, pins_data,
                 export_png=not args.no_png, png_dpi=args.png_dpi)


if __name__ == '__main__':
    main()
