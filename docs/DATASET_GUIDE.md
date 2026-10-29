# 라벨링한 자료는 어디에 넣는가

## 1. 데이터 종류부터 구분

- **YOLO detection export**: 이미지와 `class x_center y_center width height` 형식의 txt. 형상·색상 학습에 사용합니다.
- **CenterPose 정답**: 중심 + 8개 3D 경계 상자 꼭짓점의 영상 투영과 카메라 정보. YOLO txt를 이름만 바꾸어 사용할 수 없습니다.
- **AprilTag**: ID마다 신경망을 학습하지 않습니다. tag36h11 태그, 실측 크기, 카메라 보정이 필요합니다. 검출/위치 성능 평가에는 별도의 ID·위치 정답이 필요합니다.

현재 태그 퍽용 Sim 자료는 `data/tagged-pucks-v4/`입니다. 실물 자료는 새 버전 폴더에 분리해서 넣으세요. `data/`, `models/`, `runs/`는 Git 제외 대상이므로 별도 백업이 필요합니다.

## 2. 실제 사진 저장 구조

프로젝트 루트에서 폴더만 생성합니다. 기존 파일을 지우지 않습니다.

```bash
cd /home/seongmin/Projects/yolov8-ubuntu24-practice
mkdir -p data/real-pucks-v1/images/{train,val,test}
mkdir -p data/real-pucks-v1/labels/{train,val,test}
```

라벨링 도구에서 **YOLO object detection 형식**으로 export하고 압축을 별도 임시 폴더에서 푼 뒤 이미지와 txt를 대응하는 위치에 복사합니다. COCO JSON, segmentation polygon, YOLO pose 키포인트 export는 이 학습 스크립트에 그대로 넣지 않습니다. export 폴더가 `train/images`, `valid/images` 구조라면 아래 구조로 옮기거나 YAML에 그 구조를 명시하세요.

```text
data/real-pucks-v1/
├── images/
│   ├── train/session01_0001.jpg
│   ├── val/session02_0001.jpg
│   └── test/session03_0001.jpg
└── labels/
    ├── train/session01_0001.txt
    ├── val/session02_0001.txt
    └── test/session03_0001.txt
```

이미지와 txt는 **같은 split, 같은 파일 stem**을 사용합니다. JPG와 PNG 모두 가능하지만 같은 split에 `a.jpg`와 `a.png`를 동시에 두면 라벨이 충돌하므로 이름을 구분합니다. 이미지 한 장에 물체 여러 개면 txt에 여러 줄을 기록합니다. 배경 사진은 물체가 정말 없음을 확인한 뒤 빈 txt를 만듭니다. 물체가 있는데 라벨이 없는 사진을 배경으로 취급하지 마세요. `classes.txt`는 labels 안에 넣지 않습니다.

촬영 세션 단위로 train/val/test를 먼저 나눕니다. 예를 들어 세션별 총량이 약 70/15/15가 되게 나누되 각 split에 네 클래스가 포함되도록 합니다. 같은 동영상의 연속 프레임을 무작위로 나누면 거의 같은 장면이 train과 test에 들어갑니다. 원본을 복제해 두 split에 넣지 마세요. 원본 촬영·보정 자료는 `data/raw-pucks/session-날짜/`처럼 별도로 보관합니다.

## 3. 라벨링 규칙

클래스 ID는 아래 순서를 고정합니다. export된 `data.yaml`의 `names`와 반드시 대조하세요. 이름만 고치고 숫자 라벨을 그대로 두면 학습 의미가 뒤바뀝니다.

| ID | 이름 | 대상 |
|---|---|---|
| 0 | red_cylinder | 빨간 원기둥 |
| 1 | red_prism | 빨간 직육면체 |
| 2 | green_cylinder | 초록 원기둥 |
| 3 | green_prism | 초록 직육면체 |

YOLO 상자는 **물체 본체의 보이는 영역을 감싸는 상자**로 일관되게 표시합니다. 윗면 태그만 상자로 표시하지 않습니다. 태그는 별도 YOLO 클래스가 아닙니다. 가려진 물체는 보이는 영역을 기준으로 하며 완전히 가려져 보이지 않는 물체에는 YOLO 상자를 만들지 않습니다. 형상·색을 판단하기 어려운 장면은 검토 대상으로 분리하세요. Sim의 tight bbox와 같은 정책으로 유지하는 것이 목적입니다.

```text
1 0.5 0.5 0.25 0.5
```

이 줄은 빨간 직육면체 한 개입니다. 640×480 이미지라면 중심 (320,240), 너비160, 높이240px, 즉 좌상단 (240,120), 우하단 (400,360)입니다. 정규화 공식은 다음과 같습니다.

```text
x_center = (x_min + x_max) / (2 * image_width)
y_center = (y_min + y_max) / (2 * image_height)
width    = (x_max - x_min) / image_width
height   = (y_max - y_min) / image_height
```

픽셀 좌표, 쉼표, 클래스 문자열을 txt에 쓰지 않습니다. 색상이 학습 대상이므로 원본 색을 보존하고 무리한 hue 증강을 피합니다. 태그 ID는 클래스 ID와 다릅니다. 같은 종류의 퍽도 서로 다른 태그 ID를 붙일 수 있으며, 같은 장면에서는 태그 ID를 중복하지 않습니다.

## 4. 학습 설정 파일

`configs/pucks-local.yaml`을 편집기로 만들고 다음을 저장합니다. 이미 있다면 기존 설정을 백업하거나 다른 `*-local.yaml` 이름을 사용하세요. `path`는 **images와 labels를 함께 포함하는 데이터 루트**입니다.

```yaml
path: /home/seongmin/Projects/yolov8-ubuntu24-practice/data/real-pucks-v1
train: images/train
val: images/val
test: images/test
names:
  0: red_cylinder
  1: red_prism
  2: green_cylinder
  3: green_prism
```

수백 개의 txt 경로를 설정 파일에 직접 나열할 필요는 없습니다. `configs/pucks.yaml`은 참고 템플릿이고 실제 학습 명령의 `--data`가 읽을 파일을 결정합니다. 다른 컴퓨터에서는 YAML의 절대 `path`를 그 컴퓨터 위치로 바꾸세요.

## 5. 학습 전 확인

```bash
source .venv-yolo/bin/activate
python scripts/validate_labels.py data/real-pucks-v1/labels --classes 4
```

이 검사는 클래스 범위·숫자·상자 경계를 검사합니다. 이미지 누락, 같은 장면의 split 누출, 상자가 실제 물체와 맞는지는 검사하지 않습니다. 아래는 권장 구조의 파일 짝·빈 split·동일 파일 복제·중복 stem을 확인하는 읽기 전용 예시입니다. JPEG 재압축이나 연속 프레임 누출은 찾지 못합니다.

```bash
python - <<'PY'
from pathlib import Path
import hashlib
root = Path('data/real-pucks-v1')
seen = {}
errors = []
for split in ('train', 'val', 'test'):
    images = sorted(p for p in (root/'images'/split).glob('*')
                    if p.suffix.lower() in {'.jpg', '.jpeg', '.png'})
    labels = {p.stem: p for p in (root/'labels'/split).glob('*.txt')}
    stems = set()
    if not images:
        errors.append(f'{split}: no images')
    for image in images:
        if image.stem in stems:
            errors.append(f'duplicate stem: {image}')
        stems.add(image.stem)
        if image.stem not in labels:
            errors.append(f'missing label: {image}')
        digest = hashlib.sha256(image.read_bytes()).hexdigest()
        if digest in seen:
            errors.append(f'duplicate image: {seen[digest]} / {image}')
        seen[digest] = image
    errors.extend(f'orphan label: {labels[s]}' for s in labels.keys() - stems)
    print(split, 'images=', len(images), 'labels=', len(labels))
if errors:
    raise SystemExit('\n'.join(errors))
print('PASS: file pairing and exact duplicates')
PY
```

학습 시작 직후 생성되는 `train_batch*.jpg` 등의 라벨 시각화도 열어 봅니다. 직접 원본과 상자를 대조하고, 각 클래스가 골고루 포함되는지 확인하세요.

## 6. 내 자료 학습 → 평가 → 예측

```bash
RUN_ID=$(date +%Y%m%d-%H%M%S)
NAME="real-pucks-$RUN_ID"
python scripts/train_yolo.py --data configs/pucks-local.yaml \
  --model yolov8n.pt --epochs 50 --batch 4 --imgsz 640 --device 0 --name "$NAME"
WEIGHTS="runs/detect/$NAME/weights/best.pt"
yolo detect val model="$WEIGHTS" data=configs/pucks-local.yaml split=test device=0
yolo detect predict model="$WEIGHTS" source=data/real-pucks-v1/images/test \
  device=0 save=True project=runs/detect name="real-preview-$RUN_ID"
```

Ultralytics가 모델을 처음 사용할 때 다운로드할 수 있습니다. 현재 Sim 모델에서 미세조정하려면 `--model runs/detect/tagged_pucks_v4/weights/best.pt`를 사용합니다. 클래스 순서는 유지하세요. test를 보고 반복 튜닝하지 말고 val을 사용합니다. 표의 수치뿐 아니라 오검출/미검출 사례를 확인하세요.

통합 실행에서는 `--yolo "$WEIGHTS"`를 새 모델로 바꿉니다. **YOLO를 실물로 학습해도 CenterPose가 자동으로 실물에 맞게 학습되지는 않습니다.** CenterPose는 별도로 검증해야 합니다.

## 7. CenterPose용 자료

현재는 Sim 생성기가 `manifest.json`에 정답을 자동 기록합니다. `centerpose_pucks.py`의 `Samples`가 이를 읽습니다. YOLO txt만 있는 실제 촬영 자료에는 이 정답이 없으므로 별도 pose 측정·어노테이션 또는 변환 도구가 필요합니다. 저장소에는 일반 라벨링 export를 CenterPose manifest로 자동 변환하는 도구가 없습니다.

| 필드 | 형식 및 용도 |
|---|---|
| `camera_intrinsics` | `fx, fy, cx, cy` — 같은 해상도의 왜곡 제거 영상 기준 |
| `tag_size_m` | 태그 검은 경계 한 변, 기본 0.016 |
| `samples[].image` | manifest 폴더를 기준으로 한 상대 이미지 경로 |
| `samples[].split` | `train`, `val`, `test` |
| `samples[].boxes[]` | `class_id`와 픽셀 단위 `xyxy` |
| `samples[].poses[].class_id` | 해당 물체 클래스 |
| `projected_cuboid` | 9×2 픽셀 배열: 기하 중심, 이어서 8개 꼭짓점 |
| `center_camera_m` | 평가용 물체 중심 3D 정답 |
| `cuboid_camera_m` | 평가용 9×3 배열: 중심 + 8개 꼭짓점 |
| `tag_id`, `tag_corners_camera_m` | 평가용 ID, 4×3 태그 코너 정답 |
| `samples[].condition` | 평가 결과에 기록할 장면 조건 |

학습 자체는 split/image/boxes/class_id/projected_cuboid를 사용하고, 통합 평가는 카메라·태그 및 3D 정답도 사용합니다. 실제 파일의 구조는 `data/tagged-pucks-v4/manifest.json`에서 확인하세요.

코너는 물체 좌표의 `x∈[-0.015,+0.015]`, `y∈[-0.015,+0.015]`, `z∈[-0.03,+0.03]`를 **x 바깥 루프 → y → z 안쪽 루프** 순서로 나열합니다. 중심을 맨 앞에 붙입니다. 원기둥도 해당 크기의 경계 cuboid를 사용합니다. 임의로 이미지의 왼쪽 위부터 정렬하면 대응 관계가 깨집니다.

**현재 학습기와 평가기는 같은 이미지에 클래스당 물체가 최대 하나인 구성을 전제합니다.** YOLO 학습·통합 추론 자체는 같은 클래스 여러 개를 검출할 수 있지만, CenterPose `Samples`는 class_id로 첫 상자를 선택하고 평가기도 class_id와 IoU로 매칭합니다. 동일 클래스 여러 개의 pose 학습·평가를 하려면 object instance ID로 box↔pose를 연결하고 평가에 일대일 매칭을 구현해야 합니다. 자료만 추가하면 올바르게 처리되는 구조가 아닙니다.

실물 CenterPose 정답은 보정된 장비·알려진 지그·검증한 pose 어노테이션 등으로 확보하세요. 태그에서 얻은 pose를 의사 정답으로 쓸 수 있지만 같은 태그 검출값을 정답으로도 써서 독립적인 위치 정확도를 주장해서는 안 됩니다.

## 8. 실제 카메라로 통합 추론할 때

단일 이미지 추론은 manifest에서 `camera_intrinsics`, `tag_size_m`만 읽으므로 실제 카메라용 JSON에 이 두 항목을 준비할 수 있습니다. fx/fy/cx/cy는 예시 숫자를 복사하지 말고 해당 rectified 이미지의 보정값을 넣습니다. 원본 크기와 다른 크기로 resize/crop하면 K도 함께 변환해야 합니다. 이 최소 JSON은 **학습·정답 평가용 manifest가 아닙니다**.

실시간 노드는 `CameraInfo.k`와 `--tag-size`를 사용합니다. `--tag-size`는 m 단위이고 검은 경계 기준입니다. 윗면 중앙 60mm 높이 물체의 태그→중심 이동은 현재 `.03003`m로 코드에 고정되어 있으므로 실물 부착 두께·위치에 맞게 [수정 지점](CODE_GUIDE.md)을 확인하세요. RGB 이미지만 있는 상태에서 Sim K를 복사해 mm 정확도를 판단하지 마세요.
