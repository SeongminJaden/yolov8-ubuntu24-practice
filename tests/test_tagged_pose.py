import unittest
import sys
from pathlib import Path
import cv2
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from centerpose_pucks import CORNERS,crop_image

class TaggedPoseTests(unittest.TestCase):
    def test_printed_tag_convention_and_metric_scale(self):
        from tagged_perception import detect_tags
        image=np.full((640,640,3),255,np.uint8)
        marker=cv2.aruco.generateImageMarker(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11),0,80)
        image[280:360,280:360]=marker[:,:,None]
        tags=detect_tags(image,np.array([[800.,0,320],[0,800.,320],[0,0,1.]]))
        self.assertEqual([t['id'] for t in tags],[0])
        np.testing.assert_allclose(tags[0]['tag_center_camera_m'],[0,0,.16],atol=.001)
        # Raster corner noise makes planar tilt ambiguous; check offset direction/depth.
        self.assertAlmostEqual(tags[0]['tag_derived_object_center_camera_m'][2],.19003,delta=.001)
        self.assertLess(tags[0]['rotation_matrix'][2][2],-.99)
    def test_dimensions_are_exact(self):
        np.testing.assert_allclose(CORNERS.max(0)-CORNERS.min(0),[.03,.03,.06])
    def test_calibrated_cuboid_pnp_recovers_metric_center(self):
        K=np.array([[733.,0,320],[0,733.,320],[0,0,1]])
        r=np.array([.2,-.3,.4]);t=np.array([.01,-.02,.4])
        uv,_=cv2.projectPoints(CORNERS,r,t,K,None)
        ok,r2,t2=cv2.solvePnP(CORNERS,uv,K,None,flags=cv2.SOLVEPNP_EPNP)
        self.assertTrue(ok);np.testing.assert_allclose(t2.ravel(),t,atol=1e-6)
    def test_tag_to_object_offset_rotates_with_tag(self):
        K=np.array([[733.,0,320],[0,733.,320],[0,0,1]])
        h=.008;pts=np.array([[-h,h,0],[h,h,0],[h,-h,0],[-h,-h,0]])
        r=np.array([.3,-.2,.1]);R=cv2.Rodrigues(r)[0];center=np.array([.02,.03,.5]);tag=center+R[:,2]*.03003
        uv,_=cv2.projectPoints(pts,r,tag,K,None)
        ok,rr,tt=cv2.solvePnP(pts,uv,K,None,flags=cv2.SOLVEPNP_IPPE_SQUARE)
        self.assertTrue(ok);np.testing.assert_allclose(tt.ravel()-cv2.Rodrigues(rr)[0][:,2]*.03003,center,atol=1e-6)
    def test_crop_projection_round_trip(self):
        _,m=crop_image(np.zeros((640,640,3),np.uint8),[20,100,80,220])
        points=np.array([[34.,111.],[64.,205.]])
        uv=points@m[:,:2].T+m[:,2];inv=cv2.invertAffineTransform(m)
        np.testing.assert_allclose(uv@inv[:,:2].T+inv[:,2],points,atol=1e-4)

if __name__=='__main__':unittest.main()
