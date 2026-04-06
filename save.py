########################################
# Pinout image builder — SVG
# Louis Barbier
# MIT License
########################################

import json

# Function to add a function
def add_function(data, name, color):
    if "function" not in data:
        data["function"] = []
    data["function"].append({
        "name": name,
        "color": color
    })
    return data

# Function to add a pin_info
def add_pin_info(data, name, number, position):
    data["pin_info"].append({
        "name": name,
        "number": number,
        "position": position
    })
    return data

# Function to save data to a JSON file
def to_json(filename, data):
    with open(filename, 'w') as json_file:
        json.dump(data, json_file, indent=4)

# Function to load data from a JSON file
def from_json(filename):
    with open(filename, 'r') as json_file:
        data = json.load(json_file)
    return data