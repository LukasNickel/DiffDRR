# AUTOGENERATED! DO NOT EDIT! File to edit: ../notebooks/api/03_data.ipynb.

# %% ../notebooks/api/03_data.ipynb 3
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torchio import LabelMap, ScalarImage, Subject
from torchio.transforms import Resample
from torchio.transforms.preprocessing import ToCanonical

# %% auto 0
__all__ = ['load_example_ct', 'read']

# %% ../notebooks/api/03_data.ipynb 4
def load_example_ct(
    labels=None, orientation="AP", bone_attenuation_multiplier=1.0
) -> Subject:
    """Load an example chest CT for demonstration purposes."""
    datadir = Path(__file__).resolve().parent / "data"
    volume = datadir / "cxr.nii.gz"
    labelmap = datadir / "mask.nii.gz"
    structures = pd.read_csv(datadir / "structures.csv")
    return read(
        volume,
        labelmap,
        labels,
        orientation=orientation,
        bone_attenuation_multiplier=bone_attenuation_multiplier,
        structures=structures,
    )

# %% ../notebooks/api/03_data.ipynb 5
def read(
    volume: str | Path | ScalarImage,  # CT volume
    labelmap: str | Path | LabelMap = None,  # Labelmap for the CT volume
    labels: int | list = None,  # Labels from the mask of structures to render
    orientation: str = "AP",  # Frame-of-reference change
    bone_attenuation_multiplier: float = 1.0,  # Scalar multiplier on density of high attenuation voxels
    **kwargs,  # Any additional information to be stored in the torchio.Subject
) -> Subject:
    """
    Read an image volume from a variety of formats, and optionally, any
    given labelmap for the volume. Converts volume to a RAS+ coordinate
    system and moves the volume isocenter to the world origin.
    """
    # Read the volume
    if isinstance(volume, ScalarImage):
        pass
    else:
        volume = ScalarImage(volume)

    # Convert the volume to density
    density = transform_hu_to_density(volume.data, bone_attenuation_multiplier)
    density = ScalarImage(tensor=density, affine=volume.affine)

    # Read the mask if passed
    if labelmap is not None:
        if isinstance(labelmap, LabelMap):
            mask = labelmap
        else:
            mask = LabelMap(labelmap)
    else:
        mask = None

    # Frame-of-reference change
    if orientation == "AP":
        # Rotates the C-arm about the x-axis by 90 degrees
        # Rotates the C-arm about the z-axis by -90 degrees
        reorient = torch.tensor(
            [
                [0.0, 1.0, 0.0, 0.0],
                [0.0, 0.0, -1.0, 0.0],
                [-1.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ]
        )
    elif orientation == "PA":
        # Rotates the C-arm about the x-axis by 90 degrees
        # Rotates the C-arm about the z-axis by 90 degrees
        reorient = torch.tensor(
            [
                [0.0, 1.0, 0.0, 0.0],
                [0.0, 0.0, 1.0, 0.0],
                [-1.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ]
        )
    elif orientation is None:
        # Identity transform
        reorient = torch.tensor(
            [
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 1.0, 0.0, 0.0],
                [0.0, 0.0, 1.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ]
        )
    else:
        raise ValueError(f"Unrecognized orientation {orientation}")

    # Package the subject
    subject = Subject(
        volume=volume,
        mask=mask,
        reorient=reorient,
        density=density,
        **kwargs,
    )

    # Canonicalize the images by converting to RAS+ and moving the
    # Subject's isocenter to the origin in world coordinates
    subject = canonicalize(subject)

    # Apply mask
    if labels is not None:
        if isinstance(labels, int):
            labels = [labels]
        mask = torch.any(
            torch.stack([subject.mask.data.squeeze() == idx for idx in labels]), dim=0
        )
        subject.density = subject.density * mask

    return subject

# %% ../notebooks/api/03_data.ipynb 6
def canonicalize(subject):
    # Convert to RAS+ coordinate system
    subject = ToCanonical()(subject)

    # Move the Subject's isocenter to the origin in world coordinates
    for image in subject.get_images(intensity_only=False):
        isocenter = image.get_center()
        Tinv = np.array(
            [
                [1.0, 0.0, 0.0, -isocenter[0]],
                [0.0, 1.0, 0.0, -isocenter[1]],
                [0.0, 0.0, 1.0, -isocenter[2]],
                [0.0, 0.0, 0.0, 1.0],
            ]
        )
        image.affine = Tinv.dot(image.affine)

    return subject

# %% ../notebooks/api/03_data.ipynb 7
def transform_hu_to_density(volume, bone_attenuation_multiplier):
    volume = volume.to(torch.float32)

    air = torch.where(volume <= -800)
    soft_tissue = torch.where((-800 < volume) & (volume <= 350))
    bone = torch.where(350 < volume)

    density = torch.empty_like(volume)
    density[air] = volume[soft_tissue].min()
    density[soft_tissue] = volume[soft_tissue]
    density[bone] = volume[bone] * bone_attenuation_multiplier
    density -= density.min()
    density /= density.max()

    return density
