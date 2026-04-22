########################################
# Pinout image builder — Functions
# Louis Barbier
# MIT License
########################################

import os
import xml.etree.ElementTree as ET
from PIL import Image
import base64
import random
import io
import svg
from Pin import Pin

SVG_NS = 'http://www.w3.org/2000/svg'

def detect_side_pin(cx, cy, svg_size):
    # TODO find top and bottom pin
    if cx < svg_size[0] / 2:
        return 'left'
    else:
        return 'right'

def detect_pin(elements, svg_size):
    pin_detected = []
    i = 0
    for element in elements:
        detected = False
        if element.tag.endswith('circle'):  # Check for 'circle' element
            cx = float(element.attrib['cx'])
            cy = float(element.attrib['cy'])
            r = float(element.attrib['r'])
            detected = True
        elif element.tag.endswith('path'):  # Check for 'path' element
            min_x, max_x, min_y, max_y = svg.get_min_max_pos(element)
            width, height = svg.get_size(min_x, max_x, min_y, max_y)
            cx = min_x + width/2
            cy = min_y + height/2
            r = max(width/2, height/2)
            if r < 2:
                detected = True

        if detected is True:
            i = i + 1
            side = detect_side_pin(cx, cy, svg_size)
            pin_detected.append(Pin(cx, cy, r, i, side))
            # pin_detected.append({'cx': cx, 'cy': cy, 'r': r})

    return pin_detected

line_length = 3  # Length of the horizontal line
box_width = 10  # Width of the box for information
box_height = 0.85*2  # Height of the box
stroke_width = 0.05

def add_pin_graphics(svg_root, pin):
    if pin.side == 'left':
        v = -1
    else:
        v = 1

    # Add a line
    line_element = ET.Element('ns0:path', {
        'd': f'M {pin.cx},{pin.cy} l {v*line_length},{0}',
        'fill': '#dcdcdc',
        'stroke': '#dcdcdc',
        'stroke-width': str(stroke_width)
    })
    # Add pin number (circle)
    pin_number_element = ET.Element('ns0:circle', {
        'cx': str(pin.cx+v*line_length+v*pin.r),
        'cy': str(pin.cy),
        'r': str(pin.r),
        'fill': '#dcdcdc',
        'stroke': 'none',
        'stroke-width': str(stroke_width)
    })
    # Add pin number (text)
    pin_number_text = ET.Element('ns0:text', {
        'x': str(pin.cx+v*line_length+v*pin.r),
        'y': str(pin.cy),
        'text-anchor': 'middle',
        'style': 'font-family:Consolas;font-size:'+str(pin.r*1.1)+';',
        'dominant-baseline': 'central',
        'fill': '#000000',
        'stroke': '#000000',
        'stroke-width': str(stroke_width)
    })
    pin_number_text.text = str(pin.number)

    # Add function
    el_functions = ET.Element('ns0:g', {'id': "g_pin_"+str(pin.number)+"_functions"})
    for i,func in enumerate(pin.functions):
        box_l = box_width
        box_h = box_height
        slope = 0.1
        initial_point_x = pin.cx+v*line_length+v*2*pin.r+v*line_length-v*box_l*slope+v*box_l/2
        initial_point_y = pin.cy-box_height/2
        # Add a line
        line_element_1 = ET.Element('ns0:path', {
            'd': f'M {pin.cx+v*line_length+v*2*pin.r},{pin.cy} l {v*line_length},{0}',
            'fill': '#dcdcdc',
            'stroke': '#dcdcdc',
            'stroke-width': str(stroke_width)
        })
        # Add pin function (box)
        original_d = f"M {initial_point_x},{initial_point_y} l {-box_l*(1-slope)+box_l/2},{0} l {-box_l*slope},{box_h} l {box_l*(1-slope)},{0} l {box_l*slope},{-box_h} Z"
        rounded_d = svg.round_path_corners(original_d, 0.3)
        box_element = ET.Element('ns0:path', {
            'd': rounded_d,
            'fill': func['color'],
            'stroke': func['color'],
            'stroke-width': str(stroke_width*2)
        })
        # Add pin number (text)
        box_element_text = ET.Element('ns0:text', {
            'x': str(initial_point_x),
            'y': str(pin.cy),
            'text-anchor': 'middle',
            'style': 'font-family:Monospace;font-size:'+str(pin.r*1.05)+';',
            'dominant-baseline': 'central',
            'fill': '#FFFFFF',
            'stroke': '#FFFFFF',
            'stroke-width': str(stroke_width)
        })
        box_element_text.text = func['name']

        # svg.shift_element(line_element_1, i*v*(box_width+line_length), 0)
        # svg.shift_element(box_element, i*v*(box_width+line_length), 0)
        # svg.shift_element(box_element_text, i*v*(box_width+line_length), 0)

        el_functions.append(line_element_1)
        el_functions.append(box_element)
        el_functions.append(box_element_text)

        for el in el_functions[-3::1]:
            svg.shift_element(el, i*v*(box_width+line_length-box_l*slope), 0)

    # Add elements to a pin group and to the SVG root
    group = ET.Element('ns0:g', {'id': "g_pin_"+str(pin.number)})
    group.tail = "\n"
    group.append(line_element)
    group.append(pin_number_element)
    group.append(pin_number_text)
    group.append(el_functions)
    svg_root.append(group)

def pixels_to_mm(pixels, dpi):
    """Convert pixels to millimeters."""
    return (pixels / dpi) * 25.4

def scale_image_to_svg(image_width_mm, image_height_mm, svg_width_mm, svg_height_mm):
    """Scale the image dimensions proportionally to fit within the SVG dimensions."""
    scale_x = svg_width_mm / image_width_mm
    scale_y = svg_height_mm / image_height_mm
    scale_factor = min(scale_x, scale_y)  # Scale proportionally

    # Calculate the scaled image size
    scaled_width_mm = image_width_mm * scale_factor
    scaled_height_mm = image_height_mm * scale_factor

    return scaled_width_mm, scaled_height_mm

def add_board_image(svg_root, image_path, svg_width, svg_height):
    image_base64, width, height, dpi, mime_type = read_image(image_path)

    # Convert target dimensions from mm to pixels
    target_width_px = (svg_width / 25.4) * dpi
    target_height_px = (svg_height / 25.4) * dpi

    # Scale the image dimensions to fit within the target size in mm
    scale_x = svg_width / pixels_to_mm(width, dpi)
    scale_y = svg_height / pixels_to_mm(height, dpi)

    svg_root.append(svg.create_image_element(image_base64, svg_width, svg_height, mime_type))

def read_image(image_path):
    """Reads an image (PNG, JPG, BMP) and returns its base64-encoded data along with dimensions and MIME type."""
    with open(image_path, 'rb') as img_file:
        image = Image.open(img_file)
        width, height = image.size

        # Get DPI (dots per inch), default to 96 if DPI info is missing
        dpi = image.info.get('dpi', (96, 96))[0]
        
        # Get the image format and map it to the corresponding MIME type
        format_to_mime = {
            'PNG': 'image/png',
            'JPEG': 'image/jpeg',
            'JPG': 'image/jpeg',
            'BMP': 'image/bmp'
        }
        
        image_format = image.format
        if image_format not in format_to_mime:
            raise ValueError(f"Unsupported image format: {image_format}")
        
        mime_type = format_to_mime[image_format]

        # Convert image to base64-encoded string
        image_buffer = io.BytesIO()
        image.save(image_buffer, format=image_format)
        image_base64 = base64.b64encode(image_buffer.getvalue()).decode('utf-8')

    return image_base64, width, height, dpi, mime_type

def prettify_svg(root, indent="  "):
    """Prettify the ElementTree structure without using xml.dom.minidom and save it to a file."""
    
    def indent_element(elem, level=0):
        """Recursively adds indentation to an element and its children."""
        i = "\n" + level * indent
        if len(elem):  # If the element has children
            if not elem.text or not elem.text.strip():
                elem.text = i + indent
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
            for child in elem:
                indent_element(child, level + 1)
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
        else:  # If the element has no children
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i
    
    # Apply indentation to the root element
    indent_element(root)


def create_svg_root(width_mm, height_mm):
    """Create a blank SVG root sized in millimetres.

    Uses the same ns0: namespace aliasing that ElementTree applies when parsing
    a KiCad gerber SVG, so the child elements built by add_pin_graphics() and
    create_image_element() (which use literal 'ns0:*' tag names) serialize
    correctly.
    """
    root = ET.Element(f'{{{SVG_NS}}}svg')
    root.set('width', f'{width_mm}mm')
    root.set('height', f'{height_mm}mm')
    root.set('viewBox', f'0 0 {width_mm} {height_mm}')
    return root


def render_pinout(pins, board_image_path, svg_size_mm, output_path,
                  export_png=True, png_dpi=300):
    """Render an annotated pinout SVG from a pre-built Pin list.

    Entry point used by the KiCad plugin where pads come from pcbnew
    rather than a gerber SVG.

    When export_png=True, also writes a PNG next to output_path (same
    basename, .png extension) if a rasteriser is available.
    """
    width, height = svg_size_mm
    root = create_svg_root(width, height)

    for pin in pins:
        add_pin_graphics(root, pin)

    if board_image_path and os.path.isfile(board_image_path):
        add_board_image(root, board_image_path, width, height)

    svg.update_bounding_box(root, margin=10)
    prettify_svg(root)
    ET.ElementTree(root).write(output_path)

    if export_png:
        png_path = os.path.splitext(output_path)[0] + '.png'
        ok = svg_to_png(output_path, png_path, dpi=png_dpi)
        if not ok:
            print('[pinout] PNG export skipped (no rasteriser found). '
                  'Install svglib+reportlab, cairosvg, inkscape, or librsvg to enable.')

    return output_path


def svg_to_png(svg_path, png_path, dpi=300):
    """Rasterise an SVG to PNG.

    Tries cairosvg first (pure-Python with native cairo), then inkscape,
    then rsvg-convert. Returns True on success, False otherwise.
    """
    # 1. cairosvg — may fail if libcairo isn't installed on the host.
    try:
        import cairosvg
        cairosvg.svg2png(url=svg_path, write_to=png_path, dpi=dpi)
        if os.path.isfile(png_path) and os.path.getsize(png_path) > 0:
            return True
    except Exception:
        pass

    # 2. svglib + reportlab (pure-Python fallback, no native deps).
    try:
        from svglib.svglib import svg2rlg
        from reportlab.graphics import renderPM
        drawing = svg2rlg(svg_path)
        if drawing is not None:
            renderPM.drawToFile(drawing, png_path, fmt='PNG', dpi=dpi)
            if os.path.isfile(png_path) and os.path.getsize(png_path) > 0:
                return True
    except Exception:
        pass

    # 3 & 4. External binaries.
    import subprocess
    candidates = [
        ('inkscape',     ['inkscape', f'--export-dpi={dpi}',
                          '--export-type=png', f'--export-filename={png_path}',
                          svg_path]),
        ('rsvg-convert', ['rsvg-convert', '-d', str(dpi), '-p', str(dpi),
                          '-o', png_path, svg_path]),
    ]
    for _name, cmd in candidates:
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=60)
            if result.returncode == 0 and os.path.isfile(png_path) \
                    and os.path.getsize(png_path) > 0:
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    return False
