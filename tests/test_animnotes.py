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

    def test_native_sound_name_containing_mapped_key_is_untouched(self):
        prefix = struct.pack('<HH', 17, 60) + b'opaque motion\0\0'
        original = prefix + b'\x01sndnt#evt_bottle_break\0' + struct.pack('<H', 57)
        self.assertEqual(animnotes.add_sound_events(
            original, {'bottle_break': 'waw/bottle_break'}), (original, []))

    def test_native_sound_and_mapped_event_keep_their_frames(self):
        prefix = struct.pack('<HH', 17, 60) + b'opaque motion\0\0'
        original = (prefix + b'\x02sndnt#evt_bottle_break\0' + struct.pack('<H', 57)
                    + b'flip\0' + struct.pack('<H', 59))
        converted, added = animnotes.add_sound_events(
            original, {'bottle_break': 'waw/bottle_break', 'flip': 'waw/switch'})
        self.assertEqual(converted, prefix + b'\x03' + original[len(prefix) + 1:]
                         + b'sndnt#waw/switch\0' + struct.pack('<H', 59))
        self.assertEqual(added, [{'source': 'flip', 'sound': 'waw/switch', 'frame': 59}])

    def test_frame_high_byte_equal_to_remaining_count_is_not_a_second_section(self):
        # Hotel: frame 331 (4B 01) before the last note also parses as "1 note"
        # running to the end of the file; the full section must still win.
        prefix = struct.pack('<HH', 17, 421) + b'opaque motion\0\0'
        notes = [('clip_out', 42), ('rechamber_forward', 331), ('draw', 387)]
        original = prefix + bytes([len(notes)]) + b''.join(
            name.encode() + b'\0' + struct.pack('<H', frame) for name, frame in notes)
        converted, added = animnotes.add_sound_events(original, {'clip_out': 'waw/out', 'draw': 'waw/draw'})
        self.assertEqual(converted[len(prefix)], 5)
        self.assertEqual([a['source'] for a in added], ['clip_out', 'draw'])
        self.assertIn(b'rechamber_forward\0\x4b\x01', converted)

    def test_unmapped_motion_is_untouched_and_unknown_format_is_rejected(self):
        original, _ = self.raw()
        self.assertEqual(animnotes.add_sound_events(original, {'unmatched': 'waw/unused'}), (original, []))
        with self.assertRaises(weapons.WeaponError):
            animnotes.add_sound_events(b'\x12\x00' + original[2:], {'flip': 'waw/switch'})

    def test_malformed_notification_section_is_still_rejected(self):
        original, _ = self.raw()
        with self.assertRaisesRegex(weapons.WeaponError, 'no valid notification suffix'):
            animnotes.add_sound_events(original[:-1], {'flip': 'waw/switch'})
