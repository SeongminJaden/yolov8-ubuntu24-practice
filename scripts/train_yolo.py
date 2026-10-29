import argparse

def main():
    p=argparse.ArgumentParser(description="YOLOv8 four-class puck training")
    p.add_argument('--data', default='configs/pucks-local.yaml')
    p.add_argument('--model', default='yolov8n.pt')
    p.add_argument('--epochs', type=int, default=50)
    p.add_argument('--batch', type=int, default=4)
    p.add_argument('--imgsz', type=int, default=640)
    p.add_argument('--device', default='0')
    p.add_argument('--name', default='pucks')
    a=p.parse_args()
    from ultralytics import YOLO
    YOLO(a.model).train(data=a.data, epochs=a.epochs, batch=a.batch,
        imgsz=a.imgsz, device=a.device, workers=2, seed=317,
        hsv_h=0.0, hsv_s=0.2, hsv_v=0.2, project='runs/detect', name=a.name)
if __name__=='__main__': main()
