import struct
import unittest
from waw2bo2 import animnotes, weapons


class AnimationSoundTests(unittest.TestCase):
    def raw(self):
        prefix = struct.pack('<HH', 17, 100) + b'opaque motion\0\0'
        return prefix + b'\x02flip\0' + struct.pack('<H', 25) + b'other\0' + struct.pack('<H', 75), prefix

    def test_adds_native_audio_at_source_frame_and_preserves_original_event(self):
        original, prefix = self.raw()
        converted, added = animnotes.add_sound_events(original, {'flip': 'waw/switch'})
        self.assertEqual(converted[:len(prefix)], prefix)
        self.assertEqual(converted[len(prefix)], 3)
        self.assertIn(b'flip\0\x19\x00sndnt#waw/switch\0\x19\x00', converted)
        self.assertTrue(converted.endswith(b'other\0\x4b\x00'))
        self.assertEqual(added, [{'source': 'flip', 'sound': 'waw/switch', 'frame': 25}])
        self.assertEqual(animnotes.add_sound_events(converted, {'flip': 'waw/switch'}), (converted, []))

    def test_shared_animation_can_have_different_weapon_aliases(self):
        original, _ = self.raw()
        one, _ = animnotes.add_sound_events(original, {'flip': 'waw/gun_one'})
        two, _ = animnotes.add_sound_events(original, {'flip': 'waw/gun_two'})
        self.assertNotEqual(one, two)

    def test_unmapped_motion_is_untouched_and_unknown_format_is_rejected(self):
        original, _ = self.raw()
        self.assertEqual(animnotes.add_sound_events(original, {'unmatched': 'waw/unused'}), (original, []))
        with self.assertRaises(weapons.WeaponError):
            animnotes.add_sound_events(b'\x12\x00' + original[2:], {'flip': 'waw/switch'})
