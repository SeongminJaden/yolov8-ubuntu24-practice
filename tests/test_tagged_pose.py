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
    def test_six_face_same_id_has_no_unjustified_center(self):
        from tagged_perception import detect_tags
        image=np.full((640,640,3),255,np.uint8)
        marker=cv2.aruco.generateImageMarker(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11),0,80)
        image[280:360,280:360]=marker[:,:,None]
        tags=detect_tags(image,np.array([[800.,0,320],[0,800.,320],[0,0,1.]]),prism_tag_mount='six_faces')
        self.assertIsNone(tags[0]['tag_derived_object_center_camera_m'])
        self.assertEqual(len(tags[0]['object_center_candidates_camera_m']),2)

    def test_same_id_faces_merge_but_shared_objects_remain_ambiguous(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        import torch
        from tagged_perception import combine
        def box():return SimpleNamespace(cls=1,conf=.9,xyxy=torch.tensor([[0.,0.,100.,100.]]))
        tags=[dict(id=3,center_px=[20,20],corners_px=[[10,10],[30,10],[30,30],[10,30]]),
              dict(id=3,center_px=[50,50],corners_px=[[45,45],[55,45],[55,55],[45,55]])]
        model=SimpleNamespace(predict=lambda *a,**k:[SimpleNamespace(boxes=[box()])])
        with patch('tagged_perception.detect_tags',return_value=tags),patch('tagged_perception.infer',return_value={}):
            result=combine(None,model,None,None,prism_tag_mount='six_faces')
            self.assertEqual(result['objects'][0]['association_status'],'matched')
            self.assertEqual(result['objects'][0]['apriltag']['center_px'],[20,20])
            model.predict=lambda *a,**k:[SimpleNamespace(boxes=[box(),box()])]
            result=combine(None,model,None,None,prism_tag_mount='six_faces')
            self.assertTrue(all(o['apriltag'] is None for o in result['objects']))

    def test_tta_aligns_whole_symmetric_corner_sets(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        from centerpose_pucks import infer
        K=np.array([[733.,0,320],[0,733.,320],[0,0,1.]])
        r=np.array([.2,-.3,.4]);t=np.array([.01,-.02,.4])
        uv=cv2.projectPoints(CORNERS,r,t,K,None)[0].reshape(8,2)
        R=np.array([[0,-1,0],[1,0,0],[0,0,1]])
        perm=np.linalg.norm((CORNERS@R.T)[:,None]-CORNERS[None],axis=-1).argmin(1)
        def result(points):return dict(valid=True,confidence=.9,corners_px=points.tolist(),center_px=[338.325,283.35])
        with patch('centerpose_pucks.infer_single',side_effect=[result(uv),result(uv[perm]),result(uv[perm])]):
            out=infer(SimpleNamespace(inference_tta=True),None,[10,20,60,100],K)
        self.assertEqual(out['inference_crops'],3)
        np.testing.assert_allclose(out['center_camera_m'],t,atol=1e-6)
        np.testing.assert_allclose(out['corners_px'],uv,atol=1e-6)

    def test_invalid_new_pose_uses_preserved_model_without_ground_truth(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        from centerpose_pucks import infer
        previous=object();model=SimpleNamespace(inference_tta=True,pose_fallback=previous)
        with patch('centerpose_pucks.infer_single',side_effect=[{'valid':False},{'valid':True,'center_camera_m':[0,0,.4]}]) as mocked:
            result=infer(model,None,[0,0,10,10],np.eye(3))
        self.assertTrue(result['valid']);self.assertTrue(result['used_fallback'])
        self.assertIs(mocked.call_args_list[1].args[0],previous)

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
