########################################
# Pinout image builder — SVG
# Louis Barbier
# MIT License
########################################

import math
import re
import xml.etree.ElementTree as ET

# Helper function to calculate the distance between two points
def distance(p1, p2):
    return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)

# Helper function to normalize a vector (convert to unit vector)
def normalize(vector):
    length = math.sqrt(vector[0] ** 2 + vector[1] ** 2)
    if length == 0:
        return (0,0)
    return (vector[0] / length, vector[1] / length)

# Helper function to compute a point along a vector
def move_point_along_vector(point, vector, distance):
    return (point[0] + vector[0] * distance, point[1] + vector[1] * distance)

def scale_point(point, scale_x, scale_y):
    """Scale a 2D point by the given scale factors."""
    return (point[0] * scale_x, point[1] * scale_y)

def round_corner_with_bezier(p1, p2, p3, radius):
    # Calculate the direction vectors of the two segments
    v1 = (p2[0] - p1[0], p2[1] - p1[1])
    v2 = (p3[0] - p2[0], p3[1] - p2[1])
    
    # Normalize the vectors to get unit vectors
    v1_normalized = normalize(v1)
    v2_normalized = normalize(v2)
    
    # Calculate the angle between the two vectors
    angle_cosine = v1_normalized[0] * v2_normalized[0] + v1_normalized[1] * v2_normalized[1]
    angle = math.acos(angle_cosine)
    
    # Calculate the distance to move the points along each line to make room for the curve
    d = radius * math.tan(angle / 2)
    radius_start = distance(p1, p2) * 0.1
    radius_end = distance(p2, p3) * 0.1
    radius_start = d
    radius_end = d
    
    # Move along the first line to find the start of the curve
    arc_start = move_point_along_vector(p2, (-v1_normalized[0], -v1_normalized[1]), radius_start)
    
    # Move along the second line to find the end of the curve
    arc_end = move_point_along_vector(p2, v2_normalized, radius_end)
    
    # Calculate the bisector vector
    bisector = normalize((v1_normalized[0] + v2_normalized[0], v1_normalized[1] + v2_normalized[1]))
    
    # Calculate the control point for the Bezier curve
    control_point = move_point_along_vector(p2, bisector, radius)
    control_point = p2
    
    return arc_start, control_point, arc_end

def parse_svg_path(path_data):
    # Regex to find path commands (M, L, H, V, C, S, Q, T, A, Z) and associated numbers
    command_re = re.compile(r'([MLHVCQTAZmlhvcqtaz])|([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)')
    
    commands = []
    current_command = None
    current_numbers = []
    
    for match in command_re.finditer(path_data):
        token = match.group(0)

        if token.isalpha():
            # Append previous command and points
            if current_command:
                commands.append((current_command, current_numbers))
            
            # Start a new command
            current_command = token
            current_numbers = []
        else:
            # It's a number, append it to current command's numbers
            current_numbers.append(float(token))
    
    # Append the last command
    if current_command:
        commands.append((current_command, current_numbers))

    return commands

def extract_points_from_path(path_data):
    path_commands = parse_svg_path(path_data)
    points = []
    current_position = [0, 0]
    
    for command, numbers in path_commands:               
        if command.upper() == 'Z':  # Close path
            # Z closes the path, connecting to the initial point
            points.append(points[0])
        else:
            while len(numbers) > 0:
                # Find the function
                if command.upper() in 'ML':  # Move/Line
                    x, y = numbers[0:2]
                    del numbers[0:2]
                elif command.upper() == 'H': # Horizontal
                    x = numbers[0]
                    del numbers[0]
                    if command == 'H':
                        y = current_position[1]
                    else:
                        y = 0
                elif command.upper() == 'V': # Vertical
                    y = numbers[0]
                    del numbers[0]
                    if command == 'V':
                        x = current_position[1]
                    else:
                        x = 0
                elif command.upper() == 'Q':  # Quadratic Bezier Curve (absolute or relative)
                    # We take the end point of the curve
                    x, y = numbers[2:4]
                    del numbers[0:4]
                elif command.upper() == 'C':  # Cubic Bezier Curve (absolute or relative)
                    # We take the end point of the curve
                    x, y = numbers[4:6]
                    del numbers[0:6]

                # Add point
                if command.upper() == command:
                    current_position = [x, y]
                else:
                    current_position = [current_position[0] + x, current_position[1] + y]
                points.append(tuple(current_position))

    return points

def build_svg_path(new_path):
    """ ### Function to convert new path points into SVG path data """
    path_data = ""
    first_item = True
    for item in new_path:
        # Ensure it starts with 'M' for move to the first point
        if first_item:
            first_item = False
            path_data = f"M {item[0]} {item[1]} "
        elif isinstance(item, tuple) and item[0] == 'Q':
            # Bezier curve
            control_point = item[1]
            end_point = item[2]
            path_data += f"Q {control_point[0]} {control_point[1]} {end_point[0]} {end_point[1]} "
        else:
            # Line or move to (just a point)
            path_data += f"L {item[0]} {item[1]} "
    
    # Ensure it ends with 'Z' to close the path
    path_data = path_data.strip() + " Z"
    
    return path_data.strip()

def round_path_corners(d, radius):
    """
    ### Rounds the corners of a path.
    #### Args:
    - d (str): The path's `d` attribute (commands and coordinates).
    - radius (float): The radius for rounding the corners.
    #### Returns:
    - str: The modified `d` attribute with rounded corners.
    """
    points = extract_points_from_path(d)
    new_path = []
    for i in range(1, len(points)):
        p1 = points[i - 1]
        p2 = points[i]
        if i == len(points)-1:
            p3 = points[(i + 2)%len(points)]
        else:
            p3 = points[i + 1]

        # Apply rounding to the corner at p2
        arc_start, control_point, arc_end = round_corner_with_bezier(p1, p2, p3, radius)
        if i == 1:  # Add the first point (p1) initially
            new_path.append(p1)
        # Add the rounded corner
        new_path.append(arc_start)
        new_path.append(('Q', control_point, arc_end))  # Bezier curve
        # Only append p3 at the end, or if it's the last point
        if i == len(points) - 2:
            new_path.append(p3)

    new_d = build_svg_path(new_path)
    return new_d

def create_image_element(image_base64, width, height, mime_type, x_pos=0, y_pos=0):
    """Embeds the base64-encoded image (PNG, JPG, BMP) into the SVG as an <image> tag."""

    # Create the <image> element and embed the image data as base64
    image_element = ET.Element(
        'ns0:image',
        {
            'href': f'data:{mime_type};base64,{image_base64};',  # Embed image using data URI
            'id': "image1",
            'width': str(width),
            'height': str(height),
            'x': str(x_pos),  # Position the image at the top-left of the SVG canvas
            'y': str(y_pos),
            'preserveAspectRatio': 'none'
        }
    )

    return image_element

def get_min_max_pos(element):
    min_x = float('inf')
    max_x = float('-inf')
    min_y = float('inf')
    max_y = float('-inf')

    if element.tag.endswith('path'):
        print(element.attrib['d'])
        coords = extract_points_from_path(element.attrib['d'])
        print(coords)
        for cd in coords:
            min_x = min(float(cd[0]), min_x)
            min_y = min(float(cd[1]), min_y)
            max_x = max(float(cd[0]), max_x)
            max_y = max(float(cd[1]), max_y)
    elif element.tag.endswith('circle'):
        cx = float(element.attrib['cx'])
        cy = float(element.attrib['cy'])
        r = float(element.attrib['r'])
        min_x = cx - r
        max_x = cx + r
        min_y = cy - r
        max_y = cy + r
    # else:
        # raise ValueError("[get_min_max_pos] Element not recognize")

    return min_x, max_x, min_y, max_y

def shift_element(element, dx, dy):
    if element.tag.endswith('path'):
        extract_path = parse_svg_path(element.attrib['d'])
        new_path = ""
        for cmd in extract_path:
            if cmd[0] in 'ML':
                for idx in range(0, int(len(cmd[1])/2)):
                    cmd[1][idx*2] = cmd[1][idx*2] + dx
                    cmd[1][idx*2+1] = cmd[1][idx*2+1] + dy
            elif cmd[0] in 'H':
                cmd[1][0] = cmd[1][0] + dx
            elif cmd[0] in 'V':
                cmd[1][1] = cmd[1][1] + dy
            elif cmd[0] in 'Q':
                cmd[1][0:4:2] = map(lambda x: x + dx, cmd[1][0:4:2])
                cmd[1][1:4:2] = map(lambda y: y + dy, cmd[1][1:4:2])
            elif cmd[0] in 'C':
                cmd[1][0:6:2] = map(lambda x: x + dx, cmd[1][0:6:2])
                cmd[1][1:6:2] = map(lambda y: y + dy, cmd[1][1:6:2])
            new_path = new_path + cmd[0] + ' '.join(map(lambda x: str(x), cmd[1])) + ' '
        element.attrib['d'] = new_path
    elif element.tag.endswith('circle'):
        element.attrib['cx'] = str(float(element.attrib['cx']) + dx)
        element.attrib['cy'] = str(float(element.attrib['cy']) + dy)
    elif element.tag.endswith('text') or element.tag.endswith('image'):
        element.attrib['x'] = str(float(element.attrib['x']) + dx)
        element.attrib['y'] = str(float(element.attrib['y']) + dy)

    return element

def get_size(min_x, max_x, min_y, max_y):
    width = max_x - min_x
    height = max_y - min_y
    return width, height

def update_bounding_box(root, margin=0):
    min_x = float('inf')
    max_x = float('-inf')
    min_y = float('inf')
    max_y = float('-inf')

    # Get the min/max x,y
    for el in root.iter():
        el_min_x, el_max_x, el_min_y, el_max_y = get_min_max_pos(el)
        min_x = min(el_min_x, min_x)
        max_x = max(el_max_x, max_x)
        min_y = min(el_min_y, min_y)
        max_y = max(el_max_y, max_y)

    width, height = get_size(min_x, max_x, min_y, max_y)

    # # Shift every element to have min_x/min_y = 0
    # for el in root.iter():
    #     shift_element(el, -min_x, -min_y)
    # min_x, min_y = 0,0

    # Update metadata to match the true size
    root.attrib['width'] = str(width+margin)+"mm"
    root.attrib['height'] = str(height+margin)+"mm"
    view_box = [str(v) for v in [min_x,min_y,width,height]]
    root.attrib['viewBox'] = " ".join(view_box)

    return width,height

