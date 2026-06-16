"""Generate a snappyHexMeshDict for a 3D wing."""

from aerosynthx.geometry.wing import Wing


def generate_snappy_dict(wing: Wing) -> str:
    """
    Generates a snappyHexMeshDict as a string for a given wing.

    This uses a set of sensible default refinement levels.
    """
    # For simplicity, define a bounding box for refinement around the wing
    min_coords = wing.coordinates[0][0]
    max_coords = wing.coordinates[-1][-1]

    # A simple bounding box for the refinement region
    refinement_box_min = f"({min_coords[0] - 0.5} {min_coords[1] - 0.5} {min_coords[2] - 0.5})"
    refinement_box_max = f"({max_coords[0] + 0.5} {max_coords[1] + 0.5} {max_coords[2] + 0.5})"

    return f"""
/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /   O peration     | Version:  v2312                                 |
|   \\\\  /    A nd           | Web:      www.OpenFOAM.com                      |
|    \\\\/     M anipulation  |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      snappyHexMeshDict;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

castellatedMesh true;
snap            true;
addLayers       false;

geometry
{{
    wing.stl
    {{
        type triSurfaceMesh;
        name wing;
    }}

    refinementBox
    {{
        type searchableBox;
        min {refinement_box_min};
        max {refinement_box_max};
    }}
}};

castellatedMeshControls
{{
    maxLocalCells 1000000;
    maxGlobalCells 2000000;
    minRefinementCells 0;
    nCellsBetweenLevels 3;

    features
    [
        {{
            file "wing.stl";
            level 2;
        }}
    ];

    refinementSurfaces
    {{
        wing
        {{
            level (2 3);
        }}
    }}

    refinementRegions
    {{
        refinementBox
        {{
            mode inside;
            levels ((1.0 2));
        }}
    }}

    locationInMesh (0 0 -10); // A point guaranteed to be outside the wing
    resolveFeatureAngle 30;
}}

snapControls
{{
    nSmoothPatch 3;
    tolerance 2.0;
    nSolveIter 30;
    nRelaxIter 5;
}}

addLayersControls
{{
    relativeSizes true;
    layers
    {{
        wing
        {{
            nSurfaceLayers 1;
        }}
    }}
    expansionRatio 1.0;
    finalLayerThickness 0.3;
    minThickness 0.1;
    nGrow 0;
}}

meshQualityControls
{{
    maxNonOrtho 65;
    maxBoundarySkewness 20;
    maxInternalSkewness 4;
    maxConcave 80;
    minVol 1e-13;
    minTetQuality 1e-9;
    minArea -1;
    minTwist 0.02;
    minDeterminant 0.001;
    minFaceWeight 0.05;
    minVolRatio 0.01;
    minTriangleTwist -1;
}}
"""
