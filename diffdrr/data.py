# AUTOGENERATED! DO NOT EDIT! File to edit: ../notebooks/api/03_data.ipynb.

# %% ../notebooks/api/03_data.ipynb 3
from __future__ import annotations

from pathlib import Path

import nibabel
import numpy as np

# %% auto 0
__all__ = ['read_nifti', 'load_example_ct']

# %% ../notebooks/api/03_data.ipynb 4
def read_nifti(filename: Path | str):
    """Read a NIFTI and return the volume, affine matrix, and voxel spacings."""
    img = nibabel.load(filename)
    volume = img.get_fdata()
    affine = img.affine
    spacing = img.header.get_zooms()

    # If affine matrix has negative spacing, flip axis
    for axis in range(volume.ndim):
        if affine[axis, axis] < 0:
            volume = np.flip(volume, axis)
    volume = np.copy(volume)

    # Get the origin in world coordinates from the affine matrix
    origin = tuple(affine[:3, 3])

    return volume, origin, spacing

# %% ../notebooks/api/03_data.ipynb 5
def load_example_ct():
    """Load an example chest CT for demonstration purposes."""
    datadir = Path(__file__).resolve().parent / "data"
    filename = datadir / "cxr.nii"
    return read_nifti(filename)
