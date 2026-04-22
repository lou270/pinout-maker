########################################
# Pinout image builder — KiCad board parser
# Louis Barbier
# MIT License
########################################
"""Extract pad positions, net names and net classes from a KiCad BOARD.

Only usable inside KiCad (requires pcbnew). The parser produces plain Pin
objects (defined in Pin.py) plus sidecar metadata dicts — the same shape
the existing renderer consumes.
"""

import json
import os
import re

from Pin import Pin

try:
    import pcbnew
except ImportError:
    pcbnew = None


def _to_mm(value_nm):
    """Wrap pcbnew.ToMM which handles both ints and VECTOR2I types across KiCad versions."""
    if hasattr(pcbnew, 'ToMM'):
        return pcbnew.ToMM(value_nm)
    return value_nm / 1e6


def load_netclass_map(path=None):
    """Load the net-name → function regex rules."""
    if path is None:
        path = os.path.join(os.path.dirname(__file__), 'netclass_map.json')
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('rules', [])


def match_function(net_name, net_class, rules):
    """Return the first matching function name, or ''."""
    for key in (net_name or '', net_class or ''):
        for rule in rules:
            if re.match(rule['pattern'], key, re.IGNORECASE):
                return rule['function']
    return ''


def list_footprints(board):
    """Return [(reference, footprint)] for every footprint on the board."""
    if pcbnew is None:
        raise RuntimeError('pcbnew is not available — this function must run inside KiCad.')
    return [(fp.GetReference(), fp) for fp in board.GetFootprints()]


def _pad_radius_mm(pad):
    """Approximate pad radius in mm (max of X/Y half-size)."""
    size = pad.GetSize()
    sx = _to_mm(size.x) if hasattr(size, 'x') else _to_mm(size[0])
    sy = _to_mm(size.y) if hasattr(size, 'y') else _to_mm(size[1])
    return max(sx, sy) / 2.0


def _board_bbox_mm(board):
    """Return (min_x, min_y, width, height) in mm of the board edge."""
    bbox = board.GetBoardEdgesBoundingBox()
    return (
        _to_mm(bbox.GetX()),
        _to_mm(bbox.GetY()),
        _to_mm(bbox.GetWidth()),
        _to_mm(bbox.GetHeight()),
    )


def _detect_side(cx, cy, bbox_mm):
    """left / right / top / bottom based on board aspect ratio + pad position."""
    min_x, min_y, w, h = bbox_mm
    cxr = cx - min_x
    cyr = cy - min_y
    if w >= h * 1.5:
        return 'left' if cxr < w / 2 else 'right'
    if h >= w * 1.5:
        return 'top' if cyr < h / 2 else 'bottom'
    # Roughly square: pick the closest edge.
    distances = {
        'left':   cxr,
        'right':  w - cxr,
        'top':    cyr,
        'bottom': h - cyr,
    }
    return min(distances, key=distances.get)


def parse_footprint(footprint, board, rules=None):
    """Extract pins from a single footprint.

    Returns (pins, metadata) where metadata is a dict pin.number → {
        'net_name', 'net_class', 'suggested_function', 'pad_name'
    }. The pin numbering follows the pad order reported by KiCad.
    """
    if pcbnew is None:
        raise RuntimeError('pcbnew is not available — this function must run inside KiCad.')
    if rules is None:
        rules = load_netclass_map()

    bbox_mm = _board_bbox_mm(board)
    pins = []
    meta = {}

    for idx, pad in enumerate(footprint.Pads(), start=1):
        pos = pad.GetPosition()
        cx = _to_mm(pos.x) if hasattr(pos, 'x') else _to_mm(pos[0])
        cy = _to_mm(pos.y) if hasattr(pos, 'y') else _to_mm(pos[1])
        r = _pad_radius_mm(pad)
        side = _detect_side(cx, cy, bbox_mm)

        pin = Pin(cx=cx, cy=cy, r=r, number=idx, side=side)
        net_name = pad.GetNetname() if pad.GetNet() else ''
        try:
            net_class = pad.GetNetClassName()
        except AttributeError:
            net_class = ''

        meta[idx] = {
            'net_name':          net_name,
            'net_class':         net_class,
            'suggested_function': match_function(net_name, net_class, rules),
            'pad_name':          pad.GetName() or str(idx),
        }
        pins.append(pin)

    return pins, meta


def parse_board(board, footprint_ref=None, rules=None):
    """Entry point. Extract pins from a chosen footprint (or all through-hole pads).

    Args:
        board: pcbnew.BOARD instance.
        footprint_ref: reference (e.g. 'J1') to restrict extraction to one footprint.
                       If None, scans every footprint whose reference starts with J/CN/P.
        rules: optional pre-loaded netclass_map rules.

    Returns: (pins: list[Pin], meta: dict, svg_size_mm: tuple[float, float])
    """
    if pcbnew is None:
        raise RuntimeError('pcbnew is not available — this function must run inside KiCad.')

    rules = rules or load_netclass_map()
    bbox = _board_bbox_mm(board)
    svg_size_mm = (bbox[2], bbox[3])

    if footprint_ref:
        fps = [fp for ref, fp in list_footprints(board) if ref == footprint_ref]
    else:
        fps = [fp for ref, fp in list_footprints(board)
               if re.match(r'^(J|CN|P)\d', ref)]

    all_pins, all_meta = [], {}
    offset = 0
    for fp in fps:
        pins, meta = parse_footprint(fp, board, rules)
        # Shift pads to origin of the board bounding box (SVG lives in that frame).
        for pin in pins:
            pin.cx -= bbox[0]
            pin.cy -= bbox[1]
            pin.number += offset
        all_pins.extend(pins)
        for k, v in meta.items():
            all_meta[k + offset] = v
        offset += len(pins)

    return all_pins, all_meta, svg_size_mm
