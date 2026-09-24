import torch

# --- CRITICAL FIX FOR PYTORCH 2.6 UNPICKLING ERROR ---
_original_torch_load = torch.load
def _patched_torch_load(*args, **kwargs):
    kwargs['weights_only'] = False
    return _original_torch_load(*args, **kwargs)
torch.load = _patched_torch_load
# -----------------------------------------------------

import argparse
import cv2
import json
import os
from ultralytics import YOLO

class RoadGuardAI:
    def __init__(self, weights_name='bharatpothole.pt', frame_skip=3):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        resolved_weights = os.path.join(base_dir, 'weights', weights_name)
        
        if not os.path.exists(resolved_weights):
            print(f"Warning: Custom weights '{resolved_weights}' not found. Falling back to yolov8n.pt")
            resolved_weights = 'yolov8n.pt'
            
        print(f"Loading model: {resolved_weights}...")
        self.model = YOLO(resolved_weights)
        self.frame_skip = frame_skip

    def process_video(self, video_path, output_json_path='detection_outputs.json', output_video_path='annotated_output.mp4'):
        if not os.path.exists(video_path):
            print(f"Error: Video file '{video_path}' not found!")
            return

        output_json_dir = os.path.dirname(os.path.abspath(output_json_path))
        output_video_dir = os.path.dirname(os.path.abspath(output_video_path))
        if output_json_dir:
            os.makedirs(output_json_dir, exist_ok=True)
        if output_video_dir:
            os.makedirs(output_video_dir, exist_ok=True)

        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # Use a widely compatible codec for Windows and VS Code playback.
        # mp4v can be unreadable in some players and editors, so AVI + MJPG is more reliable.
        output_video_path = output_video_path if output_video_path.lower().endswith('.avi') else output_video_path.rsplit('.', 1)[0] + '.avi'
        fourcc = cv2.VideoWriter_fourcc(*'MJPG')
        out_video = cv2.VideoWriter(output_video_path, fourcc, fps / self.frame_skip, (width, height))

        frame_count = 0
        all_detections = []

        print(f"Processing video: {video_path}...")

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            frame_count += 1
            if frame_count % self.frame_skip != 0:
                continue

            timestamp_sec = round(frame_count / fps, 2)
            frame_area = width * height

            results = self.model.predict(source=frame, conf=0.20, verbose=False)[0]

            frame_boxes = []
            annotated_frame = frame.copy()

            if results.boxes is not None and len(results.boxes) > 0:
                for box in results.boxes:
                    xyxy = box.xyxy[0].tolist()
                    x1, y1, x2, y2 = map(int, xyxy)
                    confidence = float(box.conf[0])

                    # Sky filter (ignore detections in top 25% of frame)
                    if ((y1 + y2) / 2) < (height * 0.25):
                        continue

                    box_width = x2 - x1
                    box_height = y2 - y1
                    box_area = box_width * box_height
                    area_ratio = box_area / frame_area
                    severity_score = min(round((area_ratio * 100) * confidence * 10, 2), 10.0)

                    frame_boxes.append({
                        "class_name": "pothole",
                        "confidence": round(confidence, 2),
                        "bbox": [x1, y1, x2, y2],
                        "box_area_px": round(box_area, 2),
                        "severity_score": severity_score
                    })

                    label = f"Pothole ({confidence:.2f}) | Sev: {severity_score}"
                    cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                    cv2.rectangle(annotated_frame, (x1, max(y1 - 25, 0)), (x1 + len(label) * 9, max(y1, 25)), (0, 0, 255), -1)
                    cv2.putText(annotated_frame, label, (x1, max(y1 - 7, 18)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

            out_video.write(annotated_frame)

            if frame_boxes:
                all_detections.append({
                    "frame": frame_count,
                    "timestamp_sec": timestamp_sec,
                    "detections_count": len(frame_boxes),
                    "detections": frame_boxes
                })

        cap.release()
        out_video.release()

        with open(output_json_path, 'w') as f:
            json.dump(all_detections, f, indent=4)

        print(f"\nProcessing Complete!")
        print(f"1. Saved Detection Metadata: '{output_json_path}'")
        print(f"2. Saved Video Preview: '{output_video_path}'")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run pothole detection on a road video.')
    parser.add_argument('--video', type=str, help='Path to the input video file. Defaults to ml/sample_road_video.mp4 if it exists.')
    parser.add_argument('--weights', type=str, default='bharatpothole.pt', help='Model weights name or path.')
    parser.add_argument('--json-output', type=str, default=None, help='Output JSON path for detections.')
    parser.add_argument('--video-output', type=str, default=None, help='Output annotated video path.')
    parser.add_argument('--frame-skip', type=int, default=3, help='Process every Nth frame.')
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    default_video = os.path.join(base_dir, 'sample_road_video.mp4')
    video_file = args.video if args.video else default_video

    if not os.path.exists(video_file):
        print(f"No video file found at '{video_file}'.")
        print("Usage: python ml_engine.py --video path/to/video.mp4")
        raise SystemExit(1)

    json_output = args.json_output if args.json_output else os.path.join(base_dir, 'detection_outputs.json')
    video_output = args.video_output if args.video_output else os.path.join(base_dir, 'annotated_output.mp4')

    engine = RoadGuardAI(weights_name=args.weights, frame_skip=args.frame_skip)
    engine.process_video(video_file, json_output, video_output)