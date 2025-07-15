from ultralytics import YOLO
from PIL import Image
import io
import numpy as np
import os

class ObjectDetectionHandler:
    def __init__(self):
        try:
            # yolov12n.pt 가중치 파일이 컨테이너 내부에 있어야 한다. 그리고 ultralytics에서 제공하는 모델이 아닌 yolov12 기텁에서 제공하는 모델을 사용
            model_path = os.path.join(os.path.dirname(__file__), "yolov12n.pt")
            self.model = YOLO(model_path)
            print("YOLOv12 model (yolov12n.pt) loaded successfully.")
        except Exception as e:
            print(f"Error loading YOLOv12 model: {e}")
            self.model = None

    async def detect_objects(self, image_bytes: bytes) -> list:
        if not self.model:
            return [{"error": "Model not loaded."}]
        try:
            image = Image.open(io.BytesIO(image_bytes))
            if image.mode != "RGB":
                image = image.convert("RGB")
            
            image_np = np.array(image)
            
            results = self.model(image_np, device="cpu") # 추론 실행
            
            detected_objects = []
            # results[0].boxes에서 탐지된 객체 정보 추출
            # results[0].names는 클래스 이름 딕셔너리 (예: {0: 'person', 1: 'car', ...})
            names = results[0].names if hasattr(results[0], 'names') else {}
            for box in results[0].boxes:
                label = names[int(box.cls)] if names and int(box.cls) in names else str(int(box.cls))
                detected_objects.append({
                    "label": label,
                    "score": float(box.conf), 
                    "box": { 
                        "xmin": int(box.xyxy[0][0]),
                        "ymin": int(box.xyxy[0][1]),
                        "xmax": int(box.xyxy[0][2]),
                        "ymax": int(box.xyxy[0][3])
                    }
                })
            return detected_objects
        except Exception as e:
            print(f"Error during YOLOv12 detection: {e}")
            return [{"error": f"Error processing image: {str(e)}"}]

# 핸들러 인스턴스 생성 (서버 시작 시 모델 로드)
object_detection_handler = ObjectDetectionHandler() 