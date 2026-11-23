"""Placement and purchasing rules for the Space Octopus PCB assembly."""
import json
from pathlib import Path


def load_board_parts():
    parts = {}
    for sheet in ('input-supplies-mcu-driver-inverter', 'sensing-fault-interfaces-brake', 'mechanical'):
        for part in json.loads(Path(f'data/{sheet}.json').read_text()):
            parts[part['ref']] = part
    return parts


def is_fitted(part):
    return (
        not part['dnp']
        and part.get('assembly') != 'wire-termination'
        and part['kind'] not in ('hole', 'fiducial', 'testpoint')
        and part['ref'] != 'JP701'
    )


def assembly_suffix(parts):
    """Keep each revision's validated quote and stock files together."""
    if 'F1' not in parts and 'F2' in parts and parts['J1']['pins']['1'] == 'VBUS':
        return '-upstream-fuse-smd-brake'
    if any(p.get('assembly') == 'wire-termination' for p in parts.values()):
        return '-wire-terminations'
    if all(parts[ref].get('holder') for ref in ('F1', 'F2')):
        return ''
    return '-soldered'
