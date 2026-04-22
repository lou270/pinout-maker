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
XLINK_NS = 'http://www.w3.org/1999/xlink'
SVG_TAG = lambda name: f'{{{SVG_NS}}}{name}'

# Register default namespace so serialisation emits plain <svg>/<path>/… rather
# than ns0:-prefixed tags. Some SVG renderers (and svglib in particular) don't
# resolve the ns0: prefix when it's written as a literal tag name.
ET.register_namespace('', SVG_NS)
ET.register_namespace('xlink', XLINK_NS)

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
    line_element = ET.Element(SVG_TAG('path'), {
        'd': f'M {pin.cx},{pin.cy} l {v*line_length},{0}',
        'fill': '#dcdcdc',
        'stroke': '#dcdcdc',
        'stroke-width': str(stroke_width)
    })
    # Add pin number (circle)
    pin_number_element = ET.Element(SVG_TAG('circle'), {
        'cx': str(pin.cx+v*line_length+v*pin.r),
        'cy': str(pin.cy),
        'r': str(pin.r),
        'fill': '#dcdcdc',
        'stroke': 'none',
        'stroke-width': str(stroke_width)
    })
    # Add pin number (text)
    pin_number_text = ET.Element(SVG_TAG('text'), {
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
    el_functions = ET.Element(SVG_TAG('g'), {'id': "g_pin_"+str(pin.number)+"_functions"})
    for i,func in enumerate(pin.functions):
        box_l = box_width
        box_h = box_height
        slope = 0.1
        initial_point_x = pin.cx+v*line_length+v*2*pin.r+v*line_length-v*box_l*slope+v*box_l/2
        initial_point_y = pin.cy-box_height/2
        # Add a line
        line_element_1 = ET.Element(SVG_TAG('path'), {
            'd': f'M {pin.cx+v*line_length+v*2*pin.r},{pin.cy} l {v*line_length},{0}',
            'fill': '#dcdcdc',
            'stroke': '#dcdcdc',
            'stroke-width': str(stroke_width)
        })
        # Add pin function (box)
        original_d = f"M {initial_point_x},{initial_point_y} l {-box_l*(1-slope)+box_l/2},{0} l {-box_l*slope},{box_h} l {box_l*(1-slope)},{0} l {box_l*slope},{-box_h} Z"
        rounded_d = svg.round_path_corners(original_d, 0.3)
        box_element = ET.Element(SVG_TAG('path'), {
            'd': rounded_d,
            'fill': func['color'],
            'stroke': func['color'],
            'stroke-width': str(stroke_width*2)
        })
        # Add pin number (text)
        box_element_text = ET.Element(SVG_TAG('text'), {
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
    group = ET.Element(SVG_TAG('g'), {'id': "g_pin_"+str(pin.number)})
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
    image_base64, _w, _h, _dpi, mime_type = read_image(image_path)
    image_el = svg.create_image_element(image_base64, svg_width, svg_height, mime_type)
    # Append image at the end
    svg_root.append(image_el)
    # svg_root.insert(0, image_el)

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
    """Create a blank SVG root sized in millimetres, in the default SVG namespace."""
    root = ET.Element(SVG_TAG('svg'))
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

    svg.update_bounding_box(root, margin=1)
    prettify_svg(root)
    ET.ElementTree(root).write(output_path)

    if export_png:
        png_path = os.path.splitext(output_path)[0] + '.png'
        ok = svg_to_png(output_path, png_path, dpi=png_dpi)
        if not ok:
            print('[pinout] PNG export skipped (no rasteriser found). '
                  'Install svglib+reportlab, cairosvg, inkscape, or librsvg to enable.')

    return output_path


def _rasterize(svg_path, png_path, dpi):
    """Try each available rasteriser in turn. Returns True on success."""
    try:
        import cairosvg
        cairosvg.svg2png(url=svg_path, write_to=png_path, dpi=dpi)
        if os.path.isfile(png_path) and os.path.getsize(png_path) > 0:
            return True
    except Exception:
        pass

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


def _decode_data_uri(uri):
    """Decode a base64 data URI into a PIL Image. Returns None on failure."""
    try:
        if not uri.startswith('data:'):
            return None
        _header, _, payload = uri.partition(',')
        if ';base64' not in _header:
            return None
        data = base64.b64decode(payload)
        return Image.open(io.BytesIO(data))
    except Exception:
        return None


def svg_to_png(svg_path, png_path, dpi=300):
    """Rasterise an SVG to PNG.

    Embedded <image> elements are NOT rasterised by the SVG engine — they are
    stripped out first and composited onto the final PNG with PIL at the exact
    mm coordinates read from the SVG. This avoids svglib/reportlab's quirky
    image placement (which shifts raster images vertically) and keeps output
    consistent regardless of which rasteriser is available.
    """
    import tempfile
    import xml.etree.ElementTree as ET

    svg_ns = 'http://www.w3.org/2000/svg'
    xlink_ns = 'http://www.w3.org/1999/xlink'
    ET.register_namespace('', svg_ns)
    ET.register_namespace('xlink', xlink_ns)

    tree = ET.parse(svg_path)
    root = tree.getroot()

    # Viewport → pixel scaling, derived from the SVG's own viewBox (which
    # reflects the true drawing extent after update_bounding_box).
    viewbox = root.attrib.get('viewBox', '').split()
    if len(viewbox) == 4:
        vb_x, vb_y, vb_w, vb_h = [float(v) for v in viewbox]
    else:
        vb_x = vb_y = 0.0
        vb_w = float(root.attrib.get('width', '100mm').replace('mm', ''))
        vb_h = float(root.attrib.get('height', '100mm').replace('mm', ''))

    # Collect and remove <image> elements.
    images = []
    image_tag = f'{{{svg_ns}}}image'
    href_key = 'href'
    xlink_href_key = f'{{{xlink_ns}}}href'
    for parent in list(root.iter()):
        for child in list(parent):
            if child.tag == image_tag:
                href = child.attrib.get(href_key) or child.attrib.get(xlink_href_key, '')
                try:
                    x = float(child.attrib.get('x', 0))
                    y = float(child.attrib.get('y', 0))
                    w = float(child.attrib.get('width', 0))
                    h = float(child.attrib.get('height', 0))
                except (TypeError, ValueError):
                    parent.remove(child)
                    continue
                images.append((href, x, y, w, h))
                parent.remove(child)
    print(images)
    # Write the stripped SVG to a temp file and rasterise that.
    tmp_fd, tmp_svg = tempfile.mkstemp(suffix='.svg')
    os.close(tmp_fd)
    try:
        tree.write(tmp_svg)
        if not _rasterize(tmp_svg, png_path, dpi):
            return False
    finally:
        try:
            os.unlink(tmp_svg)
        except OSError:
            pass

    if not images:
        return True

    # Composite each image onto the final PNG at the right pixel position.
    try:
        base = Image.open(png_path).convert('RGBA')
    except Exception:
        return True  # SVG was rasterised; skip compositing rather than fail.

    base_w, base_h = base.size
    px_per_unit_x = base_w / vb_w if vb_w else 0
    px_per_unit_y = base_h / vb_h if vb_h else 0

    for href, x, y, w, h in images:
        img = _decode_data_uri(href)
        if img is None:
            continue
        img = img.convert('RGBA')
        target_w = max(1, int(round(w * px_per_unit_x)))
        target_h = max(1, int(round(h * px_per_unit_y)))
        img = img.resize((target_w, target_h), Image.LANCZOS)
        pos_x = int(round((x - vb_x) * px_per_unit_x))
        pos_y = int(round((y - vb_y) * px_per_unit_y))
        # Paste the board image UNDER the existing vector rendering.
        layer = Image.new('RGBA', base.size, (0, 0, 0, 0))
        layer.paste(img, (pos_x, pos_y))
        base = Image.alpha_composite(base, layer)

    base.convert('RGB').save(png_path)
    return True
