"""Native tool diagnostics must survive Windows' legacy default encoding."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from waw2bo2 import modzone, overheathud, progress


@contextlib.contextmanager
def ansi_default_writes():
    original = Path.write_text

    def write(path, data, encoding=None, errors=None, newline=None):
        return original(path, data, encoding=encoding or 'cp1252', errors=errors, newline=newline)

    with patch.object(Path, 'write_text', write):
        yield


class UnicodeBuildLogTests(unittest.TestCase):
    output = 'x' * 5156 + '\ufffd\nAsset: caf\u00e9 \u6d4b\u8bd5\n'

    def test_console_reconfigures_legacy_pipes_without_losing_unicode(self):
        stdout, stderr = io.BytesIO(), io.BytesIO()
        out = io.TextIOWrapper(stdout, encoding='cp1252')
        err = io.TextIOWrapper(stderr, encoding='cp1252')
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            progress.configure_console()
            print(self.output, end='')
            print(self.output, end='', file=err)
        self.assertEqual(stdout.getvalue().decode('utf-8').replace('\r\n', '\n'), self.output)
        self.assertEqual(stderr.getvalue().decode('utf-8').replace('\r\n', '\n'), self.output)

    def test_shader_logs_keep_unicode_and_preserve_each_native_failure(self):
        logs = ('shader_baseline/unlinker.log', 'shader_linker.log', 'shader_check.log')
        messages = ('material extraction failed', 'relink failed', 'roundtrip failed')
        for failed_stage in range(3):
            with self.subTest(stage=failed_stage), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                work, project = root / 'work', root / 'project'
                (work / 'zone_source').mkdir(parents=True)
                zone = '// caf\u00e9 \u6d4b\u8bd5\n'
                (work / 'zone_source/mod.zone').write_text(zone, encoding='utf-8')
                ff = root / 'mod.ff'
                ff.write_bytes(b'zone')
                calls = []

                def native(command, **kwargs):
                    index = len(calls)
                    calls.append(command)
                    if index == 1 and index != failed_stage:
                        linked = work / 'shader_out/mod.ff'
                        linked.parent.mkdir(parents=True)
                        linked.write_bytes(b'linked')
                    return subprocess.CompletedProcess(command, int(index == failed_stage), self.output, '')

                with ansi_default_writes(), patch.object(modzone, 'captured', side_effect=native):
                    with self.assertRaisesRegex(RuntimeError, messages[failed_stage]):
                        modzone.activate_mod_shaders(ff, project, work, root / 'Linker.exe',
                                                    root / 'Unlinker.exe', root / 'stock')
                for log in logs[:failed_stage + 1]:
                    self.assertEqual((work / log).read_text(encoding='utf-8'), self.output)
                if failed_stage:
                    self.assertEqual((work / 'shader_zone_source/mod.zone').read_text(encoding='utf-8'), zone)

    def test_lobby_verification_logs_unicode_before_reporting_native_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = subprocess.CompletedProcess([], 1, self.output, '')
            with ansi_default_writes(), patch.object(modzone, 'captured', return_value=result):
                with self.assertRaisesRegex(RuntimeError, 'cannot verify lobby tables'):
                    modzone.verify_lobby_tables(root / 'mod.ff', root / 'Unlinker.exe', root, 'zm_test')
            self.assertEqual((root / 'verify_mod_lobby.log').read_text(encoding='utf-8'), self.output)

    def test_successful_lobby_verification_survives_unicode_tool_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            def extract(command, **kwargs):
                dump = root / 'verify_mod_lobby/zm'
                dump.mkdir(parents=True)
                (dump / 'mapstable.csv').write_text('zm_test,cdc,cia\n', encoding='utf-8')
                (dump / 'gametypestable.csv').write_text(
                    '5,,zm_test,default,,,,\n6,,zm_test,default,zclassic,,,YES\n', encoding='utf-8')
                return subprocess.CompletedProcess(command, 0, self.output, '')

            with ansi_default_writes(), patch.object(modzone, 'captured', side_effect=extract):
                modzone.verify_lobby_tables(root / 'mod.ff', root / 'Unlinker.exe', root, 'zm_test')
            self.assertEqual((root / 'verify_mod_lobby.log').read_text(encoding='utf-8'), self.output)

    def test_overheat_extraction_logs_unicode_before_reporting_native_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            content = root / 'project/content_source'
            (content / 'weapons').mkdir(parents=True)
            (content / 'weapons.runtime.json').write_text(json.dumps({'weapons': ['hot']}), encoding='utf-8')
            (content / 'weapons/hot').write_text('WEAPONFILE\\overheatWeapon\\1', encoding='utf-8')
            result = subprocess.CompletedProcess([], 1, self.output, '')
            with ansi_default_writes(), patch.object(overheathud, 'captured', return_value=result):
                with self.assertRaisesRegex(RuntimeError, 'cannot extract stock overheat HUD'):
                    overheathud.stage(root / 'bo2', root / 'project', root, root / 'Unlinker.exe')
            self.assertEqual((root / 'overheat_hud_stock/extract.log').read_text(encoding='utf-8'), self.output)
