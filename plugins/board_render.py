########################################
# Pinout image builder — KiCad board renderer
# Louis Barbier
# MIT License
########################################
"""Render a top-view PNG of the active board.

Tries three strategies, in order:
  1. pcbnew.PLOT_CONTROLLER → SVG → rasterise with cairosvg.
  2. Subprocess call to `kicad-cli pcb render` (KiCad 8+).
  3. Return None so the caller can prompt the user for a PNG manually.
"""

import os
import subprocess
import tempfile

try:
    import pcbnew
except ImportError:
    pcbnew = None

try:
    import cairosvg
except Exception:
    # cairosvg may be installed but fail to load its native cairo lib
    # (common on Windows without MSYS2). Treat as unavailable.
    cairosvg = None


def _tempfile(suffix):
    fd, path = tempfile.mkstemp(prefix='pinout_board_', suffix=suffix)
    os.close(fd)
    return path


def _plot_to_svg(board, out_svg):
    """Plot F.Cu + F.SilkS + F.Mask + Edge.Cuts to a single SVG using pcbnew."""
    if pcbnew is None:
        raise RuntimeError('pcbnew is not available')

    plot_ctrl = pcbnew.PLOT_CONTROLLER(board)
    opts = plot_ctrl.GetPlotOptions()
    out_dir = os.path.dirname(out_svg) or tempfile.gettempdir()
    opts.SetOutputDirectory(out_dir)
    opts.SetFormat(pcbnew.PLOT_FORMAT_SVG)
    opts.SetMirror(False)
    opts.SetPlotFrameRef(False)
    opts.SetUseAuxOrigin(False)
    opts.SetDrillMarksType(getattr(pcbnew, 'DRILL_MARKS_NO_DRILL_SHAPE', 0))

    layers = [
        ('Edge.Cuts', pcbnew.Edge_Cuts),
        ('F.Mask',    pcbnew.F_Mask),
        ('F.Cu',      pcbnew.F_Cu),
        ('F.SilkS',   pcbnew.F_SilkS),
    ]
    plot_ctrl.OpenPlotfile('TopView', pcbnew.PLOT_FORMAT_SVG, 'Pinout top view')
    for name, layer_id in layers:
        plot_ctrl.SetLayer(layer_id)
        plot_ctrl.PlotLayer()
    plot_ctrl.ClosePlot()

    # KiCad writes to <out_dir>/<board_name>-TopView.svg — find it.
    basename = os.path.splitext(os.path.basename(board.GetFileName()))[0]
    produced = os.path.join(out_dir, f'{basename}-TopView.svg')
    if os.path.isfile(produced):
        os.replace(produced, out_svg)
        return out_svg
    return None


def _svg_to_png(in_svg, out_png, target_width_px=2000):
    """Rasterise an SVG to PNG via cairosvg. Returns out_png or None on failure."""
    if cairosvg is None:
        return None
    try:
        cairosvg.svg2png(url=in_svg, write_to=out_png, output_width=target_width_px)
        return out_png
    except Exception:
        return None


def _kicad_cli_render(board_path, out_png):
    """Fallback: `kicad-cli pcb render --side top`."""
    exe = 'kicad-cli'
    try:
        result = subprocess.run(
            [exe, 'pcb', 'render', '--side', 'top', '--output', out_png, board_path],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0 and os.path.isfile(out_png):
            return out_png
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def render_top_view(board):
    """Produce a top-view PNG of the board. Returns path or None if all strategies failed."""
    out_png = _tempfile('.png')

    # Strategy 1: plot SVG + cairosvg.
    if pcbnew is not None and cairosvg is not None:
        svg_tmp = _tempfile('.svg')
        try:
            produced_svg = _plot_to_svg(board, svg_tmp)
            if produced_svg and _svg_to_png(produced_svg, out_png):
                return out_png
        finally:
            if os.path.isfile(svg_tmp):
                os.unlink(svg_tmp)

    # Strategy 2: kicad-cli.
    board_path = board.GetFileName() if pcbnew else None
    if board_path and os.path.isfile(board_path):
        result = _kicad_cli_render(board_path, out_png)
        if result:
            return result

    # Strategy 3: give up — caller prompts user.
    if os.path.isfile(out_png):
        os.unlink(out_png)
    return None
