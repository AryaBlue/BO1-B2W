#include "SkinnedVertsLinker.h"

namespace BSP
{
    SkinnedVertsLinker::SkinnedVertsLinker(MemoryManager& memory, ISearchPath& searchPath, AssetCreationContext& context)
        : m_memory(memory),
          m_search_path(searchPath),
          m_context(context)
    {
    }

    T6::SkinnedVertsDef* SkinnedVertsLinker::LinkSkinnedVerts([[maybe_unused]] const BSPData& bsp) const
    {
        // maxSkinnedVerts sizes the per-frame cache of deformed (multi-bone) model vertices: t6zm
        // allocates maxSkinnedVerts * 32 bytes (sub_481D80 -> sub_74B3E0), and above 90% use it scales
        // every skinned model's LOD distance up (cg_EnableAdaptiveSkinLodScale, sub_72FD80), so a
        // few zombies drop to their far LODs. It has nothing to do with the world: stock zombie maps
        // use 163840 (zm_transit 131072).
        constexpr unsigned int STOCK_ZOMBIES_MAX_SKINNED_VERTS = 163840;
        auto* skinnedVerts = m_memory.Alloc<T6::SkinnedVertsDef>();
        skinnedVerts->name = m_memory.Dup("skinnedverts");
        skinnedVerts->maxSkinnedVerts = STOCK_ZOMBIES_MAX_SKINNED_VERTS;

        return skinnedVerts;
    }
} // namespace BSP
