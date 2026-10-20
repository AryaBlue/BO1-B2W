import unittest
from waw2bo2 import techsets


class HudTechniqueTests(unittest.TestCase):
    def test_rope_uses_measured_native_rope_material_stream(self):
        result = techsets.match('m_rope', ['mc_lit_sm_r0c0_77e21qq8'])
        self.assertEqual(result.target, 'mc_lit_sm_r0c0_77e21qq8')
        with self.assertRaises(techsets.TechsetError):
            techsets.match('m_rope', ['wpc_lit_sm_r0c0_12345678'])

    def test_same_family_canopy_and_shadowcaster_are_not_rejected(self):
        self.assertEqual(techsets.match('mc_treecanopy', ['mc_treecanopy_4ze496f7']).target,
                         'mc_treecanopy_4ze496f7')
        self.assertEqual(techsets.match('wc_shadowcaster', ['wpc_shadowcaster_wj6w5j60']).target,
                         'wpc_shadowcaster_wj6w5j60')

    def test_2d_hud_uses_trivial_not_world_shader(self):
        result = techsets.match("2d", ["wc_unlit_blend_a1b2c3d4", "trivial_9z33feqw"])
        self.assertEqual(result.target, "trivial_9z33feqw")
        with self.assertRaises(techsets.TechsetError):
            techsets.match("2d", ["wc_unlit_blend_a1b2c3d4"])

    def test_unruled_techniques_get_generic_fallbacks(self):
        self.assertEqual(techsets.last_resort('mc_ambient_t0c0_dfoliage_sco')[0], 'mc_l_sm_t0c0')
        self.assertEqual(techsets.last_resort('wc_unlit_falloff_add')[0], 'wc_unlit_blend')
        self.assertEqual(techsets.last_resort('wc_water')[0], 'wc_l_sm_b0c0')
        self.assertEqual(techsets.last_resort('mc_ambient_r0c0_dfoliage_sco')[0], 'mc_l_sm_r0c0')
        self.assertEqual(techsets.last_resort('wc_l_sm_r0c0'), [])
        # the fallbacks go through the ordinary rules to real T6 donors
        self.assertEqual(techsets.match('mc_l_sm_t0c0', ['mc_lit_sm_t0c0_4ze496f7']).target, 'mc_lit_sm_t0c0_4ze496f7')
        self.assertEqual(techsets.match('wc_unlit_blend', ['wpc_unlit_blend_2840z6q0']).target,
                         'wpc_unlit_blend_2840z6q0')

    def test_bo1_unlit_replace_and_decal_blends_get_unlit_donors(self):
        donors = ['mc_unlit_replace_3j970129', 'mc_unlit_add_ww82zw88', 'wpc_unlit_replace_4688792e',
                  'wpc_unlit_blend_2840z6q0']
        def target(name, state=None):
            t4 = {'techniqueSet': name, 'stateBitsEntry': [0] * 5, 'stateBits': [state or {}]}
            return techsets.match(techsets.material_techset(t4), donors).target
        self.assertEqual(target('mc_unlit_replace'), 'mc_unlit_replace_3j970129')
        self.assertEqual(target('wc_unlit_replace'), 'wpc_unlit_replace_4688792e')
        self.assertEqual(target('wc_unlit_replace', {'blendOpRgb': 'add', 'dstBlendRgb': 'one'}),
                         'wpc_unlit_blend_2840z6q0')
        self.assertEqual(target('wc_unlitdecalblend_add'), 'wpc_unlit_blend_2840z6q0')
        self.assertEqual(target('wc_unlitdecalblend_multiply'), 'wpc_unlit_blend_2840z6q0')
        self.assertEqual(target('mc_unlitdecalblend_add'), 'mc_unlit_add_ww82zw88')
        self.assertEqual(techsets.match('mc_sm_treecanopy_sway', ['mc_treecanopy_sm_68zw237j',
                                                                  'mc_lit_sm_t0c0_90wz6fe2']).target,
                         'mc_lit_sm_t0c0_90wz6fe2')
        self.assertEqual(techsets.match('mc_l_r0c0n0s0sc0x0', ['mc_lit_sm_r0c0n0s0_7426e277']).target,
                         'mc_lit_sm_r0c0n0s0_7426e277')
        # BO1 programs that read the tangent need a donor that streams it
        tangent = ['mc_lit_sm_r0c0_77e21qq8', 'mc_lit_sm_r0c0n0_2z223015', 'mc_lit_sm_b0c0n0_10449597']
        self.assertEqual(techsets.match('mc_sw4_3d_rotate', tangent).target, 'mc_lit_sm_r0c0n0_2z223015')
        self.assertEqual(techsets.match('mc_sw4_3d_clan_tag_transparent', tangent).target, 'mc_lit_sm_b0c0n0_10449597')
        # the world decal keeps its own multiply blend over the donor's
        multiply = {'srcBlendRgb': 'destColor', 'dstBlendRgb': 'zero', 'blendOpRgb': 'add', 'colorWriteRgb': True}
        donor = {'techniqueSet': 'wpc_unlit_blend_2840z6q0', 'textures': [],
                 'stateBits': [{'srcBlendRgb': 'srcAlpha', 'dstBlendRgb': 'invSrcAlpha', 'colorWriteRgb': True}]}
        out = techsets.build_material({'techniqueSet': 'wc_unlitdecalblend_multiply', 'stateBitsEntry': [0] * 5,
                                       'stateBits': [multiply]}, donor, [])
        self.assertEqual(out['stateBits'][0]['srcBlendRgb'], 'destColor')
        self.assertEqual(out['stateBits'][0]['dstBlendRgb'], 'zero')

    def test_donor_thermal_variant_is_not_inherited(self):
        donor = {"techniqueSet": "mc_lit_sm_r0c0_x", "thermalMaterial": "mc/mtl_t6_wpn_zmb_raygun2_1_thermal",
                 "textures": [{"name": "colorMap", "semantic": "color", "image": "stock"}]}
        out = techsets.build_material({"textures": [{"name": "colorMap", "image": "waw_body"}]}, donor, [])
        self.assertNotIn("thermalMaterial", out)
        self.assertEqual(out["textures"][0]["image"], "waw_body")

    def test_two_sided_source_keeps_both_faces(self):
        donor = {"techniqueSet": "mc_lit_sm_r0c0_x", "textures": [],
                 "stateBits": [{"cullFace": "back", "colorWriteRgb": False},
                               {"cullFace": "back", "colorWriteRgb": True}]}
        two_sided = {"stateBits": [{"cullFace": "back", "colorWriteRgb": False},
                                   {"cullFace": "none", "colorWriteRgb": True}]}
        out = techsets.build_material(two_sided, donor, [])
        self.assertEqual([s["cullFace"] for s in out["stateBits"]], ["none", "none"])
        one_sided = {"stateBits": [{"cullFace": "back", "colorWriteRgb": True}]}
        out = techsets.build_material(one_sided, donor, [])
        self.assertEqual([s["cullFace"] for s in out["stateBits"]], ["back", "back"])
        self.assertEqual(donor["stateBits"][0]["cullFace"], "back")    # the donor is not modified

    def test_wireframe_pass_does_not_make_a_two_sided_source_one_sided(self):
        # wc/chainlink_fence: every drawn pass is cull none; the debug wireframe
        # pass (technique 53, polymodeLine) culls back and is never drawn.
        donor = {"techniqueSet": "wc_lit_sm_t0c0n0s0", "textures": [],
                 "stateBits": [{"cullFace": "back", "colorWriteRgb": True}]}
        fence = {"stateBits": [{"cullFace": "none", "colorWriteRgb": True},
                               {"cullFace": "back", "colorWriteRgb": True, "polymodeLine": True}]}
        out = techsets.build_material(fence, donor, [])
        self.assertEqual([s["cullFace"] for s in out["stateBits"]], ["none"])
        wire_only = {"stateBits": [{"cullFace": "none", "colorWriteRgb": True, "polymodeLine": True}]}
        out = techsets.build_material(wire_only, donor, [])
        self.assertEqual([s["cullFace"] for s in out["stateBits"]], ["back"])


if __name__ == "__main__":
    unittest.main()
