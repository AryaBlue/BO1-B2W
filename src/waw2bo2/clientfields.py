"""Static server/client clientfield audit for a staged map.

BO2 compares the server's and the client's clientfield registrations when a client connects and drops it
with EXE_CLIENT_FIELD_MISMATCH on any difference. This crawls the map's server scripts (maps/mp/<project>.gsc)
and client scripts (clientscripts/mp/<project>.csc) through the scripts they include or call, falling back to
BO2's stock raw scripts, and records every registerclientfield and visionset manager info on each side.

Visionset manager types register <type>_slot/<type>_lerp only once at least one info of that type exists,
and _zm_traps registers trap overlays from the map's entities (server: zombie_trap triggers, client: zm_traps
structs), so those are modelled from entities.json. Registrations with non-literal names are listed as
dynamic: they cannot be compared statically, the runtime check (tools/check_clientfields.py) covers them.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REFERENCE_RE = re.compile(r"#include\s+([\w\\/]+)\s*;|\b((?:maps|clientscripts|common_scripts)(?:[\\/]\w+)+)::", re.I)
CALL_RE = re.compile(r"\b(registerclientfield|vsmgr_register_info|vsmgr_register_visionset_info"
                     r"|vsmgr_register_overlay_info_style_\w+)\s*\(", re.I)
STRING_RE = re.compile(r'^"([^"]*)"$')
COMMENT_RE = re.compile(r'"(?:\\.|[^"\\\n])*"|//[^\n]*|/\*.*?\*/', re.S)
TRAP_OVERLAYS = {"electric": "zm_trap_electric", "fire": "zm_trap_burn"}
# _zm_powerups::add_zombie_powerup registers a toplayer field per included powerup (computed name)
POWERUP_SCRIPTS = {"server": ("maps/mp/zombies/_zm_powerups", "include_zombie_powerup", 8, 11),
                   "client": ("clientscripts/mp/zombies/_zm_powerups", "include_powerup", 1, 2)}


def _arguments(text: str, start: int) -> list[str]:
    """Top-level arguments of the call whose '(' ends at start."""
    depth, args, current = 1, [], ""
    for char in text[start:]:
        if char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
            if depth == 0:
                break
        if char == "," and depth == 1:
            args.append(current.strip())
            current = ""
        else:
            current += char
    return args + [current.strip()] if current.strip() else args


def _literal(arg: str) -> str | None:
    match = STRING_RE.match(arg)
    return match[1].lower() if match else None


def _int(arg: str) -> int | None:
    try:
        return int(arg.replace(" ", ""))
    except ValueError:
        return None


def _live(versions: list[int | None], highest: int) -> bool:
    """A field registered at version v exists once the server's highest version reaches v; a negative version
    -v removes it from version v on (e.g. _zm.csc's sndZombieContext 9000 / -12000)."""
    if None in versions:
        return True  # non-literal version: assume live
    reached = sorted((v for v in versions if abs(v) <= highest), key=abs)
    return bool(reached) and reached[-1] > 0


def _strip_comments(text: str) -> str:
    # one left-to-right pass: a "//*****" banner line is a line comment, not the start of a block comment
    return COMMENT_RE.sub(lambda m: m[0] if m[0].startswith('"') else "\n" * m[0].count("\n"), text)


class Side:
    def __init__(self, name: str, extension: str, roots: list[Path]):
        self.name, self.extension, self.roots = name, extension, roots
        self.files: dict[str, Path] = {}
        self.fields: dict[tuple[str, str], dict] = {}
        self.vsmgr: dict[str, dict[str, dict]] = {}
        self.dynamic: list[dict] = []

    def resolve(self, script: str) -> Path | None:
        relative = script.replace("\\", "/").lower() + self.extension
        for root in self.roots:
            if (root / relative).is_file():
                return root / relative
        return None

    def crawl(self, entry: str) -> None:
        pending = [entry]
        while pending:
            script = pending.pop().replace("\\", "/").lower()
            if script in self.files or (path := self.resolve(script)) is None:
                continue
            self.files[script] = path
            text = _strip_comments(path.read_text(encoding="utf-8", errors="replace"))
            pending += [m[1] or m[2] for m in REFERENCE_RE.finditer(text)]
            for match in CALL_RE.finditer(text):
                self._record(match[1].lower(), _arguments(text, match.end()),
                             f"{path}:{text.count(chr(10), 0, match.start()) + 1}")

    def _record(self, call: str, args: list[str], where: str) -> None:
        if call == "registerclientfield":
            if len(args) < 5:
                return
            cf_set, name = _literal(args[0]), _literal(args[1])
            if cf_set is None or name is None:
                # the visionset manager's own <type>_slot/_lerp registrations are modelled from its infos
                if "_visionset_mgr" not in where.replace("\\", "/"):
                    self.dynamic.append({"call": call, "args": args, "where": where})
                return
            info = self.fields.setdefault((cf_set, name), {"versions": [], "bits": args[3], "type": _literal(args[4]),
                                                           "where": []})
            info["versions"].append(_int(args[2]))
            info["where"].append(where)
            return
        if call == "vsmgr_register_info":
            vs_type, name, version = _literal(args[0]), _literal(args[1]) if len(args) > 1 else None, args[2:3]
        else:
            vs_type = "visionset" if call == "vsmgr_register_visionset_info" else "overlay"
            name, version = _literal(args[0]) if args else None, args[1:2]
        if vs_type is None or name is None:
            self.dynamic.append({"call": call, "args": args, "where": where})
            return
        self.vsmgr.setdefault(vs_type, {}).setdefault(name, {"version": (version or ["?"])[0], "where": []})["where"].append(where)

    def add_trap_overlays(self, trap_types: set[str], where: str) -> None:
        if "maps/mp/zombies/_zm_traps" in self.files or "clientscripts/mp/zombies/_zm_traps" in self.files:
            for trap in sorted(trap_types & TRAP_OVERLAYS.keys()):
                self.vsmgr.setdefault("overlay", {}).setdefault(TRAP_OVERLAYS[trap], {"version": "16000", "where": []})["where"].append(where)

    def add_powerups(self) -> None:
        script, include_call, field_arg, version_arg = POWERUP_SCRIPTS[self.name]
        if script not in self.files:
            return
        table = {}                                      # powerup -> (field, version)
        text = _strip_comments(self.files[script].read_text(encoding="utf-8", errors="replace"))
        for match in re.finditer(r"^[ \t]+add_zombie_powerup\s*\(", text, re.M):
            args = _arguments(text, match.end())
            name = _literal(args[0]) if args else None
            field = _literal(args[field_arg]) if len(args) > field_arg else None
            if name and field:
                version = _int(args[version_arg]) if len(args) > version_arg else None
                table[name] = (field, version or 1)
        included = set()
        for script_name, path in self.files.items():
            body = _strip_comments(path.read_text(encoding="utf-8", errors="replace"))
            included |= set(re.findall(r'\b' + include_call + r'\s*\(\s*"(\w+)"', body))
        where = f"powerups: {include_call} " + (", ".join(sorted(included)) if included else "(none: every powerup)")
        for name, (field, version) in table.items():
            if not included or name in included:
                info = self.fields.setdefault(("toplayer", field), {"versions": [], "bits": "2", "type": "int", "where": []})
                info["versions"].append(version)
                info["where"].append(where)

    def all_fields(self) -> dict[tuple[str, str], dict]:
        fields = dict(self.fields)
        for vs_type, infos in self.vsmgr.items():
            where = [f"visionset manager: {self.name} {vs_type} infos {', '.join(sorted(infos))}"]
            version = max((_int(i["version"]) or 0 for i in infos.values()), default=0)
            for suffix, kind in (("slot", "int"), ("lerp", "float")):
                fields.setdefault(("toplayer", f"{vs_type}_{suffix}"), {"versions": [version], "bits": "?", "type": kind,
                                                                         "where": where})
        return fields


def audit(project_root: Path, project: str, bo2_root: Path) -> dict:
    """Compare server and client clientfield registrations for a staged map (see the module docstring)."""
    stock = bo2_root / "raw"
    server = Side("server", ".gsc", [project_root, stock])
    client = Side("client", ".csc", [project_root, stock])
    server.crawl(f"maps/mp/{project}")
    client.crawl(f"clientscripts/mp/{project}")
    entities_json = project_root / "BSP" / "entities.json"
    entities = json.loads(entities_json.read_text(encoding="utf-8"))["entities"] if entities_json.is_file() else []
    server.add_trap_overlays({e.get("script_noteworthy", "") for e in entities if e.get("targetname") == "zombie_trap"},
                             "entities.json: zombie_trap triggers (server _zm_traps::register_visionsets)")
    client.add_trap_overlays({e.get("script_noteworthy", "") for e in entities if e.get("targetname") == "zm_traps"},
                             "entities.json: zm_traps structs (client _zm_traps::init)")
    server.add_powerups()
    client.add_powerups()
    server_fields, client_fields = server.all_fields(), client.all_fields()
    # both sides keep only the fields live at the server's highest registered version
    highest = max((v for info in server_fields.values() for v in info["versions"] if v and v > 0), default=0)
    retired = {side: sorted(f"{s}/{n}" for (s, n), info in fields.items() if not _live(info["versions"], highest))
               for side, fields in (("server", server_fields), ("client", client_fields))}
    server_fields = {k: v for k, v in server_fields.items() if _live(v["versions"], highest)}
    client_fields = {k: v for k, v in client_fields.items() if _live(v["versions"], highest)}
    report = {"project": project, "server_scripts": len(server.files), "client_scripts": len(client.files),
              "server_highest_version": highest, "retired_by_version": retired,
              "only_server": [], "only_client": [], "vsmgr_only_server": [], "vsmgr_only_client": [],
              "fields": {"server": {}, "client": {}}, "vsmgr": {"server": server.vsmgr, "client": client.vsmgr},
              "dynamic": {"server": server.dynamic, "client": client.dynamic}}
    for side, fields in (("server", server_fields), ("client", client_fields)):
        report["fields"][side] = {f"{s}/{n}": info for (s, n), info in sorted(fields.items())}
    # stock BO2 scripts register most of their fields under game mode/weapon conditions: lower confidence
    in_stock = lambda where: all(w.startswith(str(stock)) for w in where)
    for key in sorted(server_fields.keys() - client_fields.keys()):
        where = server_fields[key]["where"]
        report["only_server"].append({"field": f"{key[0]}/{key[1]}", "where": where, "stock": in_stock(where)})
    for key in sorted(client_fields.keys() - server_fields.keys()):
        where = client_fields[key]["where"]
        report["only_client"].append({"field": f"{key[0]}/{key[1]}", "where": where, "stock": in_stock(where)})
    for vs_type in sorted(server.vsmgr.keys() | client.vsmgr.keys()):
        s, c = server.vsmgr.get(vs_type, {}), client.vsmgr.get(vs_type, {})
        report["vsmgr_only_server"] += [f"{vs_type}/{n}" for n in sorted(s.keys() - c.keys())]
        report["vsmgr_only_client"] += [f"{vs_type}/{n}" for n in sorted(c.keys() - s.keys())]
    return report


def write_report(report: dict, destination: Path) -> list[str]:
    """Write clientfield_audit.json/.txt next to the build and return the likely mismatches (map/bridge scripts)."""
    destination.mkdir(parents=True, exist_ok=True)
    findings, notes = [], []
    for side in ("server", "client"):
        for entry in report[f"only_{side}"]:
            (notes if entry["stock"] else findings).append(f"only on {side}: {entry['field']}  <- {entry['where'][0]}")
        notes += [f"visionset info only on {side}: {n}" for n in report[f"vsmgr_only_{side}"]]
    report["findings"], report["notes"] = findings, notes
    (destination / "clientfield_audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = [f"clientfield audit for {report['project']}: {report['server_scripts']} server scripts, "
             f"{report['client_scripts']} client scripts, server highest version {report['server_highest_version']}", ""]
    lines += ["ONE-SIDED in map/bridge scripts (likely EXE_CLIENT_FIELD_MISMATCH):"] + [f"  {f}" for f in findings or ["none"]]
    lines += ["ONE-SIDED in stock BO2 scripts (usually registered only under a mode/weapon condition):"]
    lines += [f"  {f}" for f in notes or ["none"]] + [""]
    for side in ("server", "client"):
        lines.append(f"{side.upper()} FIELDS:")
        for name, info in report["fields"][side].items():
            versions = "/".join("?" if v is None else str(v) for v in info["versions"])
            lines.append(f"  {name:48} v{versions:>12} bits {info['bits']:>3} {info['type'] or '?':6} {info['where'][0]}")
        for vs_type, infos in sorted(report["vsmgr"][side].items()):
            lines.append(f"  visionset manager {vs_type}: {', '.join(sorted(infos))}")
        lines += [f"  retired at this version: {n}" for n in report["retired_by_version"][side]]
        lines += [f"  dynamic: {d['call']}({', '.join(d['args'])})  {d['where']}" for d in report["dynamic"][side]]
        lines.append("")
    (destination / "clientfield_audit.txt").write_text("\n".join(lines), encoding="utf-8")
    return findings
