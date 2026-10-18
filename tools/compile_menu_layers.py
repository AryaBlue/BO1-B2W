"""Rebuild the checked-in T6 32-bit menu wrapper using hksc configured for T6."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('compiler', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    source = Path('src/waw2bo2/compat/menu_layers.lua')
    binary = source.with_suffix('.luac')
    subprocess.run([str(args.compiler.resolve()), '-mwindows', '-m32', '-s', '-o', str(binary), str(source)], cwd=root, check=True)
    subprocess.run([str(args.compiler.resolve()), '-mwindows', '-m32', '-b', '-p', str(binary)], cwd=root, check=True)
    hashes = {name: hashlib.sha256((root / path).read_bytes()).hexdigest() for name, path in [('source_sha256', source), ('bytecode_sha256', binary)]}
    (root / source.with_suffix('.json')).write_text(json.dumps(hashes, indent=2) + '\n')


if __name__ == '__main__':
    main()
