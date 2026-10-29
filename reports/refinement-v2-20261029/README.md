# 6면 태그 추가 보강 v2 — 2026-10-29

## 목적과 데이터 분리

v1 모델의 새 검증 자료에서 가림·밝은 조명 조건의 CenterPose 중심 오차 P95가 상대적으로 컸습니다. 동일한 조건을 포함하는 새로운 6면 장면 train 800장을 추가해 기존 1600장과 합쳤습니다. val은 이전 200장으로 고정했고, 최종 시험에는 기존 test를 재사용하지 않고 새 300장을 생성했습니다. 새 seed 범위는 500000~501099입니다. 이전 test는 학습에 넣지 않았습니다.

`prepare-data.py`가 로컬 혼합 manifest/YAML을 만듭니다. 전체 2400/200/300개 seed는 서로 겹치지 않으며 `split-audit.json`에 기록했습니다. 이전 학습·검증 seed와도 새 시험 seed가 겹치지 않습니다. 같은 절차적 생성기와 카메라 분포를 사용하므로 실물 일반화 검증은 아닙니다.

## CenterPose 학습 및 선택

v1 best.pt에서 20 epoch, batch16, 초기 lr 0.00005, cosine으로 최종 10%까지 학습률을 낮춥니다. val loss가 초기 모델보다 낮을 때만 best.pt를 갱신합니다. `--cosine`은 선택 옵션이며 기존 기본 학습 동작은 유지합니다.

추론 후보는 단일 crop과 세 크기 crop(기존 bbox의 0.9/1.0/1.1배)입니다. 세 크기는 기존 학습 jitter 범위에 해당합니다. 각각의 예측 코너를 원본 이미지로 복원하고, 90도 대칭에 따른 전체 코너 순열을 기준 crop에 정렬한 뒤 평균내어 PnP를 풉니다. 유효하지 않은 추가 crop은 제외하고 기준 crop이 유효하지 않으면 그대로 반환합니다. 서로 무관한 코너를 개별적으로 정렬하지 않습니다.

`select-centerpose.py`는 **검증** 중심 P95가 가장 낮고, 중앙값과 유효 pose 수가 v1보다 나쁘지 않은 후보만 선택합니다. test로 모델을 고르지 않습니다. TTA가 선택되면 `best-tta.pt`에 `inference_tta=true`를 저장하며 `load_model()`이 자동 적용합니다. 최대 3회 네트워크 추론이 필요합니다.

## YOLO 학습 및 선택

v1 best.pt에서 6 epoch, batch4, AdamW 초기 lr 0.00005, cosine으로 추가 학습합니다. 동일 val의 mAP50–95가 더 높은 모델을 선택하고 동률이면 기존 모델을 유지합니다.

## AprilTag 실험

`compare-tag-scales.py`는 원본·2배·3배 cubic 확대를 검증했습니다. 2/3배 확대는 ID 검출이 670개에서 672/674개로 늘었지만 위치 P95가 16.12mm에서 17.20/17.65mm로 악화되어 채택하지 않았습니다.

`compare-tag-refinement.py`의 subpixel corner 보정(window 1/2/3)도 위치 오차가 악화됐습니다. `compare-tag-pnp.py`의 LM 보정은 중앙값이 미세하게 줄었지만 P95가 증가했습니다. 따라서 태그의 실제 크기나 좌표를 임의로 보정하지 않고 v1 검출·PnP 방식을 유지했습니다. 동일 ID 여러 면 처리도 유지합니다.

## 재현 명령

프로젝트 루트에서 다음 명령으로 학습했습니다. 경로는 이번 실험에 고정돼 있으므로 재실행 시 새 폴더로 변경하세요.

```bash
OMNI_KIT_ACCEPT_EULA=YES /home/seongmin/isaacsim6_venv/bin/python \
  sim/generate_tagged_pucks.py --output data/tagged-sixface-v2-20261029 \
  --train 800 --val 0 --test 300 --video-frames 0 \
  --seed-base 500000 --prism-tags six_faces
.venv-yolo/bin/python reports/refinement-v2-20261029/prepare-data.py
.venv-yolo/bin/python scripts/centerpose_pucks.py \
  --manifest data/tagged-sixface-v2-mixed-20261029/manifest.json \
  --resume models/centerpose-sixface-reinforced-20261029/best.pt \
  --output models/centerpose-sixface-v2-20261029 \
  --epochs 20 --batch 16 --lr 0.00005 --cosine
bash reports/refinement-v2-20261029/finish.sh
```

전체 프레임 JSON·로그는 로컬 보존하고 Git에는 요약·선택 근거·검증 결과를 저장합니다. 기존 모델과 데이터는 보존합니다.

## 최종 선택과 결과

단일 crop v2는 유효 pose 수가 718→717로 줄어 단독 채택하지 않았습니다. TTA 역시 717개여서, 새 모델이 유효하지 않을 때만 v1 추론으로 보완하는 후보를 추가했습니다. 이 구성은 검증 718개를 유지하면서 중심 중앙값 2.14→1.64mm, P95 11.27→9.21mm를 달성해 선택했습니다. 보완 가중치는 `fallback_model`로 추론 패키지 안에 포함하며 추가 학습의 state_dict/optimizer에는 등록하지 않습니다.

새 test 300장에서는 중앙값 2.14→1.83mm, P95 11.16→9.73mm, 유효 출력 1077→1080개입니다. 보완 경로는 2개 물체에 사용됐습니다. YOLO 후보는 검증 mAP50–95가 기존보다 낮아 기존 YOLO를 유지했습니다. 선택 근거는 `centerpose-selection.json`, `yolo-selection.json`이며 전체 결과는 [실행 문서](../../docs/SIX_FACE_V2.md)에 있습니다.

단위 테스트 27개 통과. 90도 대칭 코너 순열을 가진 3개 예측의 정렬/PnP 복원과, 정답 없이 이전 모델로 보완하는 경로를 회귀 검사했습니다. 추론 패키지는 CPU에서 다시 로드해 TTA/보완 가중치와 학습 state_dict 분리도 확인했습니다.
