import numpy as np
import torch
import pytorch3d

from pytorch3d.renderer import (
    PerspectiveCameras, RasterizationSettings, PointLights,
    MeshRasterizer, SoftPhongShader, MeshRenderer,
    TexturesUV,
)
from pytorch3d.structures import Meshes

from . import coor_utils
from .visualize_2d import draw_dots_image


"""
Dealing with vertices projections, possibly using pytorch3d

Pytorch3D has two Perspective Cameras:

- pytorch3d.render.FovPerspectiveCameras(znear, zfar, ar, fov)

- pytorch3d.render.PerspectiveCameras(focal_length, principal_point)
    - or pytorch3d.render.PerspectiveCameras(K: (4,4))


1. Coordinate System.

pytorch3d / pytorch3d-NDC

            ^ Y
            |
            |   / Z
            |  /
            | /
    X <------

OpenGL:

            ^ Y              Y ^
            |                  |  / Z
            |                  | /
            |                  |/
            /------> X          ------> X
           /
          /
       Z /

OpenCV, Open3D:

             / Z
            /
           /
          /
         ----------> X
         |
         |
         |
         v Y


2. Projection transforms.

In pytorch3d, the transforms are as follows:
model -> view -> ndc -> screen
In pinhole camera model, i.e. with simple 3x3 matrix K, the transforms is:
model -> screen


Ref:
[1] https://medium.com/maochinn/%E7%AD%86%E8%A8%98-camera-dee562610e71https://medium.com/maochinn/%E7%AD%86%E8%A8%98-camera-dee562610e71

"""

_R = torch.eye(3)
_T = torch.zeros(3)


def perspective_projection(mesh_data,
                           cam_f,
                           cam_p,
                           method=dict(
                               name='pytorch3d',
                               in_mesh=False,
                               in_ndc=True,
                               R=_R,
                               T=_R,
                               ),
                           image=None,
                           img_h=None,
                           img_w=None):
    """ Project verts/mesh by Perspective camera.
    Camera by default located at (0, 0, 0) and looks following z-axis.

    If `image` is None, will render a image with size (img_h, img_w).

    TODO: verify points coincides
    If method is 'naive', will compute perspective camera matrix K (4,4).

    Args:
        mesh_data: 
            - For naive_perspective_projection:
                (Verts, Faces)
                Tuple of verts (V, 3) and faces (F, 3). faces can be None
            - For pytorch3d:
                (Verts, Faces), 
                or,
                pytorch3d.Mesh if `method.in_mesh=True`

        cam_f: focal length (2,)
        cam_p: principal points (2,)
        method: dict
            - name: one of {'naive', 'pytorch3d'}.

            Other fields contains the parameters of that function

        in_ndc: bool
        R: (3, 3) camera extrinsic matrix.
        T: (3,) camera extrinsic matrix.
        image: (H, W, 3)
    
    Returns:
        (H, W, 3) image
    """
    method_name = method.pop('name')
    if image is None:
        image = np.ones([img_h, img_w, 3], dtype=np.uint8) * 255

    if method_name == 'naive':
        return naive_perspective_projection(
            mesh_data=mesh_data, cam_f=cam_f, cam_p=cam_p, image=image
        )
    elif method_name == 'pytorch3d':
        image = torch.as_tensor(
            image, dtype=torch.float32,
            device=mesh_data[0].device) / 255.
        img = pytorch3d_perspective_projection(
            mesh_data=mesh_data, cam_f=cam_f, cam_p=cam_p,
            **method, image=image
        )
        return img


def naive_perspective_projection(mesh_data,
                                 cam_f,
                                 cam_p,
                                 image):
    """ 
    Given image size, naive calculation of K should be
    
    fx = cx = img_w/2, fy = cy = img_h/2

    """
    verts, _faces = mesh_data
    fx, fy = cam_f
    cx, cy = cam_p
    points = coor_utils.project_3d_2d(verts.T, fx=fx, fy=fy, cx=cx, cy=cy).T
    img = draw_dots_image(image, points)
    return img


def pytorch3d_perspective_projection(mesh_data,
                                     cam_f,
                                     cam_p,
                                     in_mesh=False,
                                     in_ndc=True,
                                     R=_R,
                                     T=_T,
                                     image=None):
    """ 
    Args:
        image: (H, W, 3) torch.Tensor with values in [0, 1]
    """
    device = 'cuda'
    image_size = image.shape[:2]
    
    if not in_mesh:
        verts, faces = mesh_data
        verts, faces = map(torch.as_tensor, (verts, faces))

        V, F = verts.shape[0], faces.shape[0]
        obj_map = torch.ones([1, 1, 3]) * torch.Tensor([0.65, 0.74, 0.86])
        obj_faceuv = torch.zeros([F, 3]).long()
        obj_vertuv = torch.zeros([1, 2])
        obj_mesh = Meshes(
            verts=[verts], faces=[faces],
            textures=pytorch3d.renderer.TexturesUV(
                maps=[obj_map], faces_uvs=[obj_faceuv], verts_uvs=[obj_vertuv])
        ).to(device)
    else:
        obj_mesh = mesh_data

    R = torch.unsqueeze(torch.as_tensor(R), 0)
    T = torch.unsqueeze(torch.as_tensor(T), 0)
    cameras = pytorch3d.renderer.PerspectiveCameras(
        focal_length=[cam_f],
        principal_point=[cam_p],
        in_ndc=in_ndc,
        R=R,
        T=T,
        image_size=[image_size],   
    )

    raster_settings = RasterizationSettings(
        image_size=image_size, blur_radius=0, faces_per_pixel=1)
    lights = PointLights(location=[[0, 0, 0]])
    rasterizer = MeshRasterizer(cameras=cameras, raster_settings=raster_settings)
    shader = SoftPhongShader(cameras=cameras, lights=lights)
    renderer = MeshRenderer(
        rasterizer=rasterizer, shader=shader).to(device)

    rendered = renderer(obj_mesh)

    # Add background image
    if image is not None:
        image = image.to(device)
        frags = renderer.rasterizer(obj_mesh)
        is_bg = frags.pix_to_face[..., 0] < 0
        dst = rendered[..., :3]
        mask = is_bg[..., None].repeat(1, 1, 1, 3)
        out = dst.masked_scatter(
            mask, image[None][mask])
        out = out.cpu().numpy().squeeze()
    else:
        out = rendered.cpu().numpy().squeeze()[..., :3]
    return out