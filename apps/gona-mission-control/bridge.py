"""Adaptateur in-process de la passerelle Atlas : lecture + création non assignée seulement."""
import importlib.util
import os
import subprocess
from pathlib import Path

spec = importlib.util.spec_from_file_location('atlas_bridge', Path(__file__).parent / 'upstream/bridge.py')
atlas = importlib.util.module_from_spec(spec)
spec.loader.exec_module(atlas)
import config
CLI = config.HERMES_CLI
OPS = {'list', 'show', 'create'}


def arguments(op, data):
    if op not in OPS:
        raise ValueError('Lecture et création non assignée uniquement')
    # Validation stricte héritée : pas de tenant, assignee, parent ni option arbitraire.
    args = atlas.arguments(op, data)
    return [CLI, '-p', 'gpt5', 'kanban', '--board', 'default'] + args[2:]


def execute(op, data, runner=subprocess.run):
    args = arguments(op, data)
    result = runner(args, capture_output=True, text=True, timeout=25, check=False)
    if result.returncode:
        raise RuntimeError('Commande Kanban refusée ou indisponible')
    import json
    return json.loads(result.stdout)
