"""Compare exported WaW terrain with native T6 geometry and model ownership."""
import argparse
from collections import Counter
import json
from pathlib import Path

from waw2bo2 import fbx, world


def audit(source_path, native_path):
    source = world.read_collision(Path(source_path))
    native = json.loads(Path(native_path).read_text())
    owners = fbx.collision_triangle_models(source)
    slots, _ = fbx.collision_material_slots(source)

    def geometry(points):
        return tuple(sorted(tuple(round(value, 4) for value in point) for point in points))

    expected = Counter()
    for triangle, slot in enumerate(slots):
        if slot is None:
            continue
        material = source.materials[source.triangle_materials[triangle]]
        points = [source.vertices[index] for index in source.indices[triangle * 3:triangle * 3 + 3]]
        expected[(owners[triangle], material.content_flags & 0xffffffff,
                  material.surface_flags & 0xffffffff, geometry(points))] += 1

    def partitions(roots):
        pending = list(roots)
        visited, result = set(), set()
        while pending:
            index = pending.pop()
            if index in visited:
                continue
            visited.add(index)
            assert 0 <= index < len(native['aabbs']), f'Invalid AABB index {index}'
            node = native['aabbs'][index]
            if node['children']:
                pending.extend(range(node['index'], node['index'] + node['children']))
            else:
                assert 0 <= node['index'] < len(native['partitions'])
                result.add((node['index'], node['material']))
        return result

    def roots(leaf):
        first, count, _ = leaf
        assert not count or first <= 65535, 'Leaf root index overflow'
        assert count <= 65535, 'Leaf root count overflow'
        return range(first, first + count)

    world_parts = partitions(i for leaf in native['leafs'] for i in roots(leaf))
    groups = {0: world_parts}
    used = {p: 0 for p, _ in world_parts}
    for model, leaf in enumerate(native['models'][1:], 1):
        groups[model] = partitions(roots(leaf))
        for partition, _ in groups[model]:
            assert partition not in used, f'Partition {partition} belongs to both {used[partition]} and {model}'
            used[partition] = model
    actual, counts = Counter(), Counter()
    seen_triangles = set()
    for model, group in groups.items():
        for partition, material_index in group:
            first, count = native['partitions'][partition]
            material = native['materials'][material_index]
            for triangle in range(first, first + count):
                assert triangle not in seen_triangles, f'Triangle {triangle} owned twice'
                seen_triangles.add(triangle)
                points = [native['vertices'][index] for index in native['triangles'][triangle]]
                actual[(model, material['contents'] & 0xffffffff, material['surface_flags'] & 0xffffffff,
                        geometry(points))] += 1
                counts[model] += 1
    assert len(seen_triangles) == len(native['triangles']), 'Unreachable terrain triangles'
    assert expected == actual, (f'Terrain mismatch: {sum((expected - actual).values())} missing, '
                                f'{sum((actual - expected).values())} unexpected triangles')
    return {'triangles': sum(counts.values()), 'aabbs': len(native['aabbs']), 'coordinate_decimal_places': 4,
            'model_triangle_counts': dict(sorted(counts.items())), 'geometry_flags_and_ownership_match': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('native', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = audit(args.source, args.native)
    if args.output:
        args.output.write_text(json.dumps(result, indent=2))
    print(json.dumps(result))
