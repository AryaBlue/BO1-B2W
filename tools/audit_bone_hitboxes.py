"""Compare authored bone-space hitboxes with an unlinked T6 fastfile.

Usage: python tools/audit_bone_hitboxes.py <staged-project> <unlinked-fastfile>
Models absent from this fastfile are skipped (they may live in mod.ff).
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
from waw2bo2.modelhitboxes import audit


if __name__ == '__main__':
    result = audit(Path(sys.argv[1]), Path(sys.argv[2]))
    print(json.dumps(result, indent=2))
    sys.exit(bool(result['errors']) or result['models'] == 0)
