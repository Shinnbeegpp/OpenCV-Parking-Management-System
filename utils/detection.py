# utils/detection.py
# Camera capture + YOLO + OCR detection worker

import cv2
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal, QMutex
from PyQt5.QtGui import QImage
import time
import re

# ─── LAZY IMPORTS (loaded once on first use) ──────────────────────────────────
_yolo_model = None
_ocr_reader = None
_import_errors = []

def load_models():
    global _yolo_model, _ocr_reader, _import_errors
    _import_errors = []
    try:
        from ultralytics import YOLO
        _yolo_model = YOLO('yolov8n.pt')
        print("YOLO loaded successfully:", _yolo_model)
    except Exception as e:
        print("YOLO FAILED:", e)
        _yolo_model = None
    try:
        import easyocr
        _ocr_reader = easyocr.Reader(['en'], gpu=True)
    except Exception:
        _ocr_reader = None
    return []

# YOLO class IDs that correspond to vehicles (COCO dataset)
VEHICLE_CLASSES = {
    2: 'Car', 3: 'Motorcycle', 5: 'Bus', 7: 'Truck'
}

def classify_vehicle(yolo_results):
    """Extract first detected vehicle class from YOLO results."""
    if yolo_results is None:
        return None, None
    for r in yolo_results:
        boxes = r.boxes
        if boxes is None:
            continue
        for i, cls_id in enumerate(boxes.cls.tolist()):
            cls_id = int(cls_id)
            if cls_id in VEHICLE_CLASSES:
                conf = float(boxes.conf[i])
                box = boxes.xyxy[i].tolist()
                return VEHICLE_CLASSES[cls_id], (box, conf)
    return None, None

def extract_plate_text(frame, box=None):
    """Run EasyOCR on a region and return best plate candidate."""
    if _ocr_reader is None:
        return None
    try:
        if box:
            x1, y1, x2, y2 = [int(v) for v in box]
            # Expand ROI slightly below vehicle for plate
            h = frame.shape[0]
            y2_plate = min(h, y2 + int((y2 - y1) * 0.3))
            roi = frame[max(0, y1):y2_plate, max(0, x1):x2]
        else:
            roi = frame

        if roi.size == 0:
            return None

        results = _ocr_reader.readtext(roi, detail=1)
        best = None
        best_conf = 0.15
        for (_, text, conf) in results:
            cleaned = re.sub(r'[^A-Z0-9]', '', text.upper())
            if 4 <= len(cleaned) <= 10 and conf > best_conf:
                best = cleaned
                best_conf = conf
        return best
    except Exception:
        return None

def draw_overlays(frame, yolo_results, plate_text, vehicle_type):
    """Draw bounding boxes and labels on frame."""
    annotated = frame.copy()

    if yolo_results:
        for r in yolo_results:
            boxes = r.boxes
            if boxes is None:
                continue
            for i, cls_id in enumerate(boxes.cls.tolist()):
                cls_id = int(cls_id)
                if cls_id not in VEHICLE_CLASSES:
                    continue
                x1, y1, x2, y2 = [int(v) for v in boxes.xyxy[i].tolist()]
                conf = float(boxes.conf[i])
                label = f"{VEHICLE_CLASSES[cls_id]} {conf:.0%}"
                # Draw box
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 200, 100), 2)
                # Label background
                (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
                cv2.rectangle(annotated, (x1, y1 - th - 8), (x1 + tw + 6, y1), (0, 200, 100), -1)
                cv2.putText(annotated, label, (x1 + 3, y1 - 4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA)

    if plate_text:
        label = f"PLATE: {plate_text}"
        h, w = annotated.shape[:2]
        cv2.rectangle(annotated, (8, h - 40), (len(label) * 12 + 16, h - 8), (30, 30, 30), -1)
        cv2.putText(annotated, label, (12, h - 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 230, 255), 2, cv2.LINE_AA)

    return annotated

def frame_to_qimage(frame):
    """Convert OpenCV BGR frame to QImage."""
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb.shape
    return QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888).copy()


# ─── CAMERA WORKER THREAD ─────────────────────────────────────────────────────

class CameraWorker(QThread):
    """
    Captures frames from webcam, runs YOLO + OCR,
    emits signals for UI updates and vehicle detection events.
    """
    frame_ready    = pyqtSignal(QImage)           # annotated frame for display
    vehicle_detected = pyqtSignal(str, str)       # plate, vehicle_type
    ocr_failed     = pyqtSignal()                 # trigger manual input popup
    error_signal   = pyqtSignal(str)

    COOLDOWN_SECONDS = 30   # don't re-detect same vehicle within N seconds

    def __init__(self, camera_index=0, mode='entry', parent=None):
        super().__init__(parent)
        self.camera_index = camera_index
        self.mode = mode  # 'entry' or 'exit'
        self._running = False
        self._mutex = QMutex()
        self._last_detection_time = 0
        self._last_plate = None

    def run(self):
        self._running = True
        cap = cv2.VideoCapture(self.camera_index)

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        if not cap.isOpened():
            self.error_signal.emit(f"Cannot open camera {self.camera_index}")
            return

        frame_count = 0
        vehicle_type = None
        plate_text = None
        yolo_results = None

        while self._running:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.05)
                continue

            frame_count += 1
            now = time.time()

            # Run detection every 5th frame to save CPU
            if frame_count % 5 == 0:
                if _yolo_model:
                    try:
                        yolo_results = _yolo_model(frame, verbose=False, conf=0.25)
                        v_type, box_info = classify_vehicle(yolo_results)
                        if v_type:
                            vehicle_type = v_type
                            box = box_info[0] if box_info else None
                            # OCR every 15th frame
                            if frame_count % 15 == 0:
                                plate_text = extract_plate_text(frame, box)
                    except Exception as e:
                        yolo_results = None

            # Draw overlays
            annotated = draw_overlays(frame, yolo_results, plate_text, vehicle_type)

            # Overlay mode label
            label_color = (0, 180, 80) if self.mode == 'entry' else (0, 100, 220)
            mode_label = f"{'ENTRY' if self.mode == 'entry' else 'EXIT'} CAM"
            cv2.rectangle(annotated, (0, 0), (130, 28), label_color, -1)
            cv2.putText(annotated, mode_label, (6, 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)

            # Emit frame
            self.frame_ready.emit(frame_to_qimage(annotated))

            # Emit detection event (with cooldown to avoid double-logging)
            if vehicle_type and (now - self._last_detection_time) > self.COOLDOWN_SECONDS:
                # Give OCR extra attempts before giving up — wait up to 3 seconds
                if not plate_text:
                    if not hasattr(self, '_ocr_wait_start'):
                        self._ocr_wait_start = now
                    elif (now - self._ocr_wait_start) > 3.0:
                        # OCR truly failed after 3 seconds of trying
                        self._last_detection_time = now
                        del self._ocr_wait_start
                        self.ocr_failed.emit()
                        vehicle_type = None
                        yolo_results = None
                else:
                    # Plate found — log it
                    if hasattr(self, '_ocr_wait_start'):
                        del self._ocr_wait_start
                    self._last_detection_time = now
                    self._last_plate = plate_text
                    self.vehicle_detected.emit(plate_text, vehicle_type)
                    vehicle_type = None
                    plate_text = None
                    yolo_results = None

            self.msleep(30)  # ~33 fps cap

        cap.release()

    def stop(self):
        self._running = False
        self.wait()
