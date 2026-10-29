# 코드 역할과 수정 위치

이 문서는 현재 저장소 코드의 동작을 설명합니다. 먼저 [실습 순서](PRACTICE_GUIDE.md)를 실행한 뒤 필요한 항목만 수정하세요. 실행 옵션으로 가능한 변경은 코드 수정 없이 처리합니다. `configs/tagged-pucks.json`은 사양 기록이며 **자동 설정 로더가 아닙니다**.

## 1. 전체 데이터 흐름

```text
Sim 생성기 ── images + YOLO labels + manifest + scene.usda
                   │                    │
              train_yolo.py      centerpose_pucks.py
                   │                    │
             YOLO best.pt        CenterPose best.pt
                   └─────────┬──────────┘
RGB + 카메라 K + 태그 크기 → tagged_perception.combine()
                             ├─ YOLO: 클래스/상자
                             ├─ CenterPose: crop → 중심/코너 → PnP
                             └─ AprilTag: ID/코너 → PnP
                                      ↓
                           물체-태그 연결 → JSON
```

`live_tagged_perception.py`는 이미지와 CameraInfo를 동기화한 뒤 같은 `combine()`을 호출합니다. 파일 추론과 실시간 추론은 인식 함수를 공유합니다.

## 2. 주요 파일 읽는 순서

| 순서 | 파일·함수 | 하는 일 |
|---|---|---|
| 1 | [train_yolo.py](../scripts/train_yolo.py) `main()` | argparse로 옵션 읽기 → `YOLO(a.model)` → `.train()` |
| 2 | [tagged_perception.py](../scripts/tagged_perception.py) `main()` | manifest의 K 구성, 모델 로드, 이미지 읽기, 결과 JSON/overlay 저장 |
| 3 | 같은 파일 `combine()` | YOLO 추론 → 각 bbox에서 CenterPose → bbox 안의 태그 중심으로 대응 |
| 4 | 같은 파일 `detect_tags()` | Apriltags3 ID/코너 검출 → 코너 순서 변환 → IPPE PnP → 태그 pose |
| 5 | [centerpose_pucks.py](../scripts/centerpose_pucks.py) `crop_image()` | bbox를 1.5배 정사각 영역으로 잘라 128×128 입력 생성; 변환행렬 반환 |
| 6 | 같은 파일 `infer()` | heatmap 최대점+offset → 원본 중심/코너 좌표 → 알려진 크기로 PnP/LM 정제 |
| 7 | 같은 파일 `Samples`, `loss_for`, `main` | manifest 정답 로딩, crop/증강, 중심·코너 손실, val 최저 모델 저장 |
| 8 | [generate_tagged_pucks.py](../sim/generate_tagged_pucks.py) | 실제 규격 USD 물체·태그 생성, RTX 렌더/상자와 pose 정답 저장 |
| 9 | [evaluate_tagged_perception.py](../scripts/evaluate_tagged_perception.py) | test 정답과 예측 매칭, 위치/회전/ID/연결 성능 집계 |
| 10 | [live_tagged_perception.py](../scripts/live_tagged_perception.py) | ROS 수신·동기화·통합 인식·발행·기록 |

CenterPose의 중심은 `hm` heatmap 최대 위치와 `reg` 소수점 offset으로 얻습니다. `hps`는 8개 코너의 상대 위치를 예측합니다. crop에서 원본 영상으로 되돌린 코너와 `CORNERS`, 카메라 K를 사용해 PnP가 미터 단위 위치를 풉니다. 태그 기반 중심을 CenterPose 예측으로 대체하지 않습니다.

`loss_for()`는 중심 focal 형태 손실 + 8코너 Smooth L1 + 중심 offset L1을 합칩니다. 90도 회전 대칭마다 **전체 코너 배열**을 일관되게 바꾸고 최소 코너 손실을 선택합니다. 기본 학습률은 Adam 0.0005, seed 317입니다. `best.pt`는 가장 작은 val_loss를 저장합니다. 이 맞춤 체크포인트는 NVIDIA 기본 Isaac ROS CenterPose decoder에 바로 넣을 수 없습니다.

태그 대응은 상자 안에 태그 중심이 하나 있을 때 후보가 됩니다. 같은 ID가 여러 물체에 연결되면 연결을 해제합니다. 기하학적으로 가까운 순서나 과거 프레임 ID로 억지 연결하지 않습니다. 복잡한 가림과 상자 중첩은 `ambiguous`로 남을 수 있습니다.

## 3. 어디를 바꾸면 되는가

| 바꿀 내용 | 먼저 바꿀 곳 | 함께 확인할 것 |
|---|---|---|
| 라벨링한 자료 위치 | `configs/pucks-local.yaml`의 `path/train/val/test` | 실제 이미지·labels 짝과 names 순서 |
| 학습 데이터 | `train_yolo.py --data ...` | YAML 위치와 데이터 루트를 혼동하지 않기 |
| YOLO 시작 가중치 | `--model yolov8n.pt` 또는 기존 best.pt | COCO pretrained부터 시작 / 퍽 모델 미세조정 |
| epoch, batch, 입력 크기, GPU | `--epochs`, `--batch`, `--imgsz`, `--device` | TensorRT export는 현재 별도로 640 고정 |
| 학습 결과 이름 | `--name` | 실제 출력 경로 자동 증가 가능 |
| 추론할 사진·모델 | `tagged_perception.py --image/--yolo/--centerpose` | 사진 카메라에 맞는 manifest |
| YOLO confidence/NMS | `tagged_perception.py`의 `combine()`: `conf=.25`, `iou=.45` | 현재 CLI 옵션 없음; 낮추면 오검출도 증가 |
| YOLO 색 증강 | `train_yolo.py`: `hsv_h=0.0`, `hsv_s=.2`, `hsv_v=.2` | 빨강/초록이 클래스 의미이므로 hue 변환 주의 |
| CenterPose epoch/batch | `centerpose_pucks.py --epochs/--batch` | 출력 폴더는 새 경로 |
| CenterPose 추가 학습 | `--resume 기존/best.pt` | optimizer 복원 아닌 가중치 초기화 |
| CenterPose 학습률 | `main()`의 `Adam(..., lr=.0005)` | 변경 전후 val loss 비교 |
| CenterPose 유효 판정 | `infer()`의 `error<10`, `score>=.25`, 양의 깊이 | 기준을 낮춘다고 실측 정확도가 좋아지지 않음 |
| Sim 생성 수량 | `--train/--val/--test/--video-frames` | 작은 세트는 실행 확인용 |
| 조명·배경·시점 | 생성기의 `DomeLight`, `DistantLight`, 카메라 및 장면 무작위화 부분 | 새 데이터 생성 후 학습·평가 |
| 태그 검은 경계 크기 | 생성기 `--tag-size`, live `--tag-size`, 이미지 manifest의 `tag_size_m` | 모두 m; 인쇄는 `make_apriltag.py --black-size-mm`로 mm |
| 인쇄할 ID | `make_apriltag.py --id` | tag36h11 0~586, Sim 기본 patterns는 0~15 |
| 태그 종류(family) | `tag_detector()`와 인쇄기/패턴/Sim/ROS launch 전체 | 한 군데 문자열만 바꾸면 서로 불일치 |
| 태그 부착 위치 | `detect_tags()`의 `.03003`과 태그→물체 변환 | 옆면은 이동량만 바꾸는 것으로 충분하지 않음; 회전 포함 변환 필요 |
| ROS 토픽 | live 파일의 subscribe/publish 문자열 | publisher·CameraInfo도 함께; 현재 CLI 토픽 옵션 없음 |
| ROS domain | Sim `--domain`, receiver `ROS_DOMAIN_ID` | 동일 값 사용 |
| Sim 설치 위치 | `run_live_tagged.sh`의 환경변수 `SIM_VENV` | Sim 실행 Python 경로도 수정 |

학습 명령의 `--device cpu`는 YOLO 학습에서 사용할 수 있지만, 현재 통합 추론은 YOLO `device=0`와 CenterPose CUDA가 코드에 고정되어 있습니다. GPU 없는 시스템에서 통합 경로를 쓰려면 device를 모든 함수에 전달하도록 코드 변경이 필요합니다.

## 4. 물체 규격·클래스를 바꾸는 경우

현재 두 형상은 같은 30×30×60mm 경계 cuboid를 사용합니다. 규격 변경은 다음 항목을 함께 수정해야 합니다.

1. 생성기의 Cylinder radius/height, Cube scale 및 장면 배치의 높이·간격.
2. 생성기의 tag 타일 Z, pose 정답용 코너 좌표, manifest의 dimensions_m.
3. CenterPose `CORNERS`와 체크포인트 저장의 dimensions_m. 현재 load_model은 dimensions_m을 읽어 크기를 자동 전환하지 않습니다.
4. 통합 평가기의 회전 복원 분모 `.03/.03/.06`와 형상 대칭 가정.
5. `detect_tags()`의 물체 중심 offset `.03003`, 인쇄기·생성기의 태그 최대 크기 제한.
6. `configs/tagged-pucks.json` 사양 기록 및 관련 문서. 새 자료·모델을 만들고 mm 오차를 다시 평가.

클래스 추가/순서 변경은 YOLO YAML 외에도 `NAMES`(통합 추론·생성기), 생성기의 짝수=원기둥/앞 두 클래스=빨강 로직, 평가기의 `class_id % 2`, ROS decoder 클래스 수·표시 이름을 바꿔야 합니다. [pucks.launch.py](../launch/pucks.launch.py)는 4클래스용입니다. YOLO만 단독 실행하는 경우와 전체 통합 경로를 변경하는 경우의 범위를 구분하세요.

동일 클래스의 여러 인스턴스를 학습·평가하려면 `Samples`의 `boxes[0]` 선택을 instance ID 매칭으로 바꾸고, 평가기의 class/IoU 대응도 일대일로 바꿔야 합니다. 자세한 데이터 계약은 [DATASET_GUIDE.md](DATASET_GUIDE.md)에 있습니다.

## 5. 나머지 도구

| 파일 | 역할 / 주의점 |
|---|---|
| `validate_labels.py` | YOLO txt 숫자 검사. 이미지 짝/내용 검사는 별도 |
| `make_synthetic.py` | 단순 2D 도형 자료. 실제 규격 3D Sim 생성기와 구분 |
| `verify_pipeline.py` | 설치부터 작은 학습·추적·export까지 광범위 실행. 문서 변경마다 재학습할 필요 없음 |
| `track_yolo.py` | ByteTrack 영상 추적. ID는 임시 추적 번호이며 AprilTag 물리 ID와 다름 |
| `evaluate_sim_video.py` | manifest 영상 정답과 추적/검출 평가 |
| `export_onnx.py` | YOLO를 640, batch1, static, NMS 미포함 ONNX로 export |
| `inspect_onnx.py` | ONNX 입력·출력 규격 확인 |
| `build_engine.sh` | 대상 GPU용 TensorRT engine 생성 |
| `check_trt_output.py`, `compare_ros_boxes.py` | ONNX/TRT 수치 및 ROS 상자 비교 |
| `make_apriltag.py` | 실물 크기를 지정한 인쇄 SVG 생성 |
| `verify_tag_render.py` | Sim 태그 흰 여백 렌더 확인 |
| `run_live_tagged.sh` | YOLO venv와 Sim bundled Jazzy 라이브러리 연결 |
| `verify_tagged_topics.py` | 통합 JSON과 별도 NVIDIA GPU AprilTag 토픽 수신 확인 |
| `third_party/centerpose/` | NVIDIA DLA34 코드와 출처/라이선스. 외부 코드 수정은 신중히 분리 |

## 6. 수정 후 확인 순서

데이터 변경이면 라벨·파일 짝 검사 → 라벨 시각화 → 짧은 학습 → val 평가 순서로 확인합니다. 추론 코드 변경이면 단위 테스트 → 기존 이미지 추론 → 별도 평가 → Sim 실시간 순서입니다. 이미지 출력이 정상이어도 3D 단위와 K가 틀릴 수 있으므로 JSON을 같이 확인합니다.

```bash
python -m unittest discover -s tests -v
```

테스트 통과는 실제 카메라·로봇 정확도를 보장하지 않습니다. 수정 전후 모델 경로, 데이터 버전, 설정, 평가 결과를 함께 기록하고, 최종 단계에서 남겨 둔 test 세션으로 확인하세요.
