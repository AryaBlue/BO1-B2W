#include "SkinnedVertsDumperT6.h"

#include <format>

using namespace T6;

namespace skinned_verts
{
    DumperT6::DumperT6(const AssetPool<AssetSkinnedVerts::Type>& pool)
        : AbstractAssetDumper(pool)
    {
    }

    void DumperT6::DumpAsset(AssetDumpingContext& context, const XAssetInfo<AssetSkinnedVerts::Type>& asset)
    {
        const auto assetFile = context.OpenAssetFile(std::format("{}.txt", asset.m_name));
        if (!assetFile)
            return;

        *assetFile << std::format("maxSkinnedVerts {}\n", asset.Asset()->maxSkinnedVerts);
    }
} // namespace skinned_verts
