# AUTOGENERATED! DO NOT EDIT! File to edit: ../notebooks/api/07_utils.ipynb.

# %% auto 0
__all__ = ['get_focal_length', 'get_principal_point', 'parse_intrinsic_matrix', 'make_intrinsic_matrix', 'resample',
           'get_pinhole_camera']

# %% ../notebooks/api/07_utils.ipynb 4
def get_focal_length(
    intrinsic,  # Intrinsic matrix (3 x 3 tensor)
    delx: float,  # X-direction spacing (in units length)
    dely: float,  # Y-direction spacing (in units length)
) -> float:  # Focal length (in units length)
    fx = intrinsic[0, 0]
    fy = intrinsic[1, 1]
    return abs((fx * delx) + (fy * dely)).item() / 2.0

# %% ../notebooks/api/07_utils.ipynb 5
def get_principal_point(
    intrinsic,  # Intrinsic matrix (3 x 3 tensor)
    height: int,  # Y-direction length (in units pixels)
    width: int,  # X-direction length (in units pixels)
    delx: float,  # X-direction spacing (in units length)
    dely: float,  # Y-direction spacing (in units length)
):
    x0 = delx * (intrinsic[0, 2] - width / 2)
    y0 = dely * (intrinsic[1, 2] - height / 2)
    return x0.item(), y0.item()

# %% ../notebooks/api/07_utils.ipynb 6
def parse_intrinsic_matrix(
    intrinsic,  # Intrinsic matrix (3 x 3 tensor)
    height: int,  # Y-direction length (in units pixels)
    width: int,  # X-direction length (in units pixels)
    delx: float,  # X-direction spacing (in units length)
    dely: float,  # Y-direction spacing (in units length)
):
    focal_length = get_focal_length(intrinsic, delx, dely)
    x0, y0 = get_principal_point(intrinsic, height, width, delx, dely)
    return focal_length, x0, y0

# %% ../notebooks/api/07_utils.ipynb 7
import torch


def make_intrinsic_matrix(
    sdd: float,  # Source-to-detector distance (in units length)
    delx: float,  # X-direction spacing (in units length / pixel)
    dely: float,  # Y-direction spacing (in units length / pixel)
    height: int,  # Y-direction length (in units pixels)
    width: int,  # X-direction length (in units pixels)
    x0: float = 0.0,  # Principal point x-coordinate (in units length)
    y0: float = 0.0,  # Principal point y-coordinate (in units length)
):
    return torch.tensor(
        [
            [sdd / delx, 0.0, x0 / delx + width / 2],
            [0.0, sdd / dely, y0 / dely + height / 2],
            [0.0, 0.0, 1.0],
        ]
        # [
        #     [sdd / delx, 0.0, -x0 / delx + width / 2],
        #     [0.0, sdd / dely, -y0 / dely + height / 2],
        #     [0.0, 0.0, 1.0],
        # ]
    )

# %% ../notebooks/api/07_utils.ipynb 8
from kornia.geometry.transform import center_crop, resize, translate


def resample(
    img,
    focal_len,
    delx,
    x0=0,
    y0=0,
    new_focal_len=None,
    new_delx=None,
    new_x0=None,
    new_y0=None,
):
    """Resample an image with new intrinsic parameters."""
    if new_focal_len is None:
        new_focal_len = focal_len
    if new_delx is None:
        new_delx = delx
    if new_x0 is None:
        new_x0 = x0
    if new_y0 is None:
        new_y0 = y0

    x = img.clone()
    _, _, height, width = x.shape
    shape = torch.tensor([height, width])

    # Translate the image
    translation = torch.tensor([[new_x0 - x0, new_y0 - y0]]) / delx
    x = translate(x, translation.to(x))

    # Crop the image to change the focal length
    focal_scaling = new_focal_len / focal_len
    crop_size = (shape / focal_scaling).to(int).tolist()
    x = center_crop(x, crop_size)
    x = resize(x, (height, width))

    # Pad the image to resize pixels
    pixel_scaling = new_delx / delx
    padding = (shape * (pixel_scaling - 1) / 2).to(int).tolist()
    padding = [padding[1], padding[1], padding[0], padding[0]]
    x = torch.nn.functional.pad(x, padding)
    x = resize(x, (height, width))

    return x

# %% ../notebooks/api/07_utils.ipynb 10
from kornia.geometry.calibration import solve_pnp_dlt
from kornia.geometry.camera.pinhole import PinholeCamera

from .pose import RigidTransform


def get_pinhole_camera(drr, pose: RigidTransform) -> PinholeCamera:
    # Move everything to CPU and use double precision
    drr = drr.to(device="cpu", dtype=torch.float64)
    pose = pose.to(device="cpu", dtype=torch.float64)

    # Make the intrinsic matrix (in pixels)
    fx = drr.detector.sdd / drr.detector.delx
    fy = drr.detector.sdd / drr.detector.dely
    u0 = drr.detector.x0 / drr.detector.delx + drr.detector.width / 2
    v0 = drr.detector.y0 / drr.detector.dely + drr.detector.height / 2
    intrinsics = torch.tensor(
        [
            [
                [fx, 0.0, u0, 0.0],
                [0.0, fy, v0, 0.0],
                [0.0, 0.0, 1.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ]
        ],
        dtype=torch.float64,
    )

    # Get matching 3D and 2D points for PnP
    (xmin, xmax), (ymin, ymax), (zmin, zmax) = drr.subject.volume.get_bounds()
    X = torch.tensor(
        [
            [
                [xmin, ymin, zmin],
                [xmax, ymin, zmin],
                [xmin, ymax, zmin],
                [xmax, ymax, zmin],
                [xmin, ymin, zmax],
                [xmax, ymin, zmax],
                [xmin, ymax, zmax],
                [xmax, ymax, zmax],
            ]
        ],
        dtype=torch.float64,
    )
    x = drr.perspective_projection(pose, X)

    # Solve for the extrinsic matrix with PnP
    extrinsics = torch.eye(4, dtype=torch.float64)[None]
    extrinsics[:, :3, :] = solve_pnp_dlt(X, x, intrinsics[..., :3, :3])

    # Make the pinhole camera, converted back to single precision
    camera = PinholeCamera(
        intrinsics.to(torch.float32),
        extrinsics.to(torch.float32),
        torch.tensor([drr.detector.height]),
        torch.tensor([drr.detector.width]),
    )

    # Append the necessary intrinsics
    camera.f = drr.detector.sdd
    camera.delx = drr.detector.delx
    camera.dely = drr.detector.dely
    camera.x0 = drr.detector.x0
    camera.y0 = drr.detector.y0

    # Define a function to get the camera center
    camera.center = (
        lambda: -camera.extrinsics[0, :3, :3].T @ camera.extrinsics[0, :3, 3]
    )

    return camera
