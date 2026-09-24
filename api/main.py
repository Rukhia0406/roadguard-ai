import math
import os
import secrets
import tempfile
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional

import cv2
from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.calculations import calculate_repair_metrics
from api.database import Defect, SessionLocal, initialize_database
from api.geocoding import resolve_coordinates


BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "ml" / "weights" / "bharatpothole.pt"
FALLBACK_MODEL_PATH = BASE_DIR / "yolov8n.pt"
DEDUPLICATION_RADIUS_METERS = 5.0
FRAME_INTERVAL = 5
OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

app = FastAPI(title="RoadGuard AI API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")

_model = None
_model_lock = Lock()


@app.get("/")
def health_check() -> dict:
    return {
        "service": "RoadGuard AI API",
        "status": "running",
        "docs_url": "/docs",
        "openapi_url": "/openapi.json",
    }


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                import torch
                from ultralytics import YOLO

                original_torch_load = torch.load

                def compatible_torch_load(*args, **kwargs):
                    kwargs["weights_only"] = False
                    return original_torch_load(*args, **kwargs)

                torch.load = compatible_torch_load
                weights = MODEL_PATH if MODEL_PATH.exists() else FALLBACK_MODEL_PATH
                _model = YOLO(str(weights))
    return _model


def haversine_meters(latitude_a: float, longitude_a: float, latitude_b: float, longitude_b: float) -> float:
    earth_radius_m = 6_371_000.0
    lat_a, lat_b = math.radians(latitude_a), math.radians(latitude_b)
    delta_lat = math.radians(latitude_b - latitude_a)
    delta_lon = math.radians(longitude_b - longitude_a)
    hav = math.sin(delta_lat / 2) ** 2 + math.cos(lat_a) * math.cos(lat_b) * math.sin(delta_lon / 2) ** 2
    return 2 * earth_radius_m * math.asin(math.sqrt(hav))


def bounding_box_iou(box_a, box_b) -> float:
    left = max(box_a[0], box_b[0])
    top = max(box_a[1], box_b[1])
    right = min(box_a[2], box_b[2])
    bottom = min(box_a[3], box_b[3])
    intersection = max(0, right - left) * max(0, bottom - top)
    area_a = max(0, box_a[2] - box_a[0]) * max(0, box_a[3] - box_a[1])
    area_b = max(0, box_b[2] - box_b[0]) * max(0, box_b[3] - box_b[1])
    union = area_a + area_b - intersection
    return intersection / union if union else 0.0


def apply_metrics(defect: Defect, severity_score: float) -> None:
    metrics = calculate_repair_metrics(severity_score)
    defect.severity_score = metrics.severity_score
    defect.urgency_level = metrics.urgency_level
    defect.surface_area_sqm = metrics.surface_area_sqm
    defect.patch_depth_m = metrics.patch_depth_m
    defect.asphalt_volume_m3 = metrics.asphalt_volume_m3
    defect.asphalt_weight_tonnes = metrics.asphalt_weight_tonnes
    defect.bags_25kg = metrics.bags_25kg
    defect.tack_coat_liters = metrics.tack_coat_liters
    defect.estimated_cost_usd = metrics.estimated_cost_usd
    defect.estimated_cost_inr = metrics.estimated_cost_inr


def find_nearby_open_defect(db: Session, latitude: float, longitude: float) -> Optional[Defect]:
    open_defects = db.scalars(select(Defect).where(Defect.status == "OPEN")).all()
    return next(
        (
            defect
            for defect in open_defects
            if haversine_meters(latitude, longitude, defect.latitude, defect.longitude)
            <= DEDUPLICATION_RADIUS_METERS
        ),
        None,
    )


def defect_payload(defect: Defect) -> dict:
    return {
        "id": defect.id,
        "defect_code": defect.defect_code,
        "latitude": defect.latitude,
        "longitude": defect.longitude,
        "severity_score": defect.severity_score,
        "urgency_level": defect.urgency_level,
        "surface_area_sqm": defect.surface_area_sqm,
        "patch_depth_m": defect.patch_depth_m,
        "asphalt_volume_m3": defect.asphalt_volume_m3,
        "asphalt_weight_tonnes": defect.asphalt_weight_tonnes,
        "bags_25kg": defect.bags_25kg,
        "tack_coat_liters": defect.tack_coat_liters,
        "estimated_cost_usd": defect.estimated_cost_usd,
        "estimated_cost_inr": defect.estimated_cost_inr,
        "telemetry_verified": defect.telemetry_verified,
        "status": defect.status,
        "created_at": defect.created_at.isoformat(),
    }


@app.on_event("startup")
def startup() -> None:
    initialize_database()


@app.get("/api/v1/geocode")
def geocode_location(street_name: str = Query(..., min_length=1)) -> dict:
    latitude, longitude = resolve_coordinates(street_name, None, None)
    return {
        "street_name": street_name.strip(),
        "latitude": latitude,
        "longitude": longitude,
    }


@app.post("/api/v1/scan-video")
def scan_video(
    request: Request,
    file: UploadFile = File(...),
    street_name: Optional[str] = Form(None),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    z_impact_spike: float = Form(0.0),
    db: Session = Depends(get_db),
) -> dict:
    if not file.filename:
        raise HTTPException(status_code=400, detail="A video filename is required")

    latitude, longitude = resolve_coordinates(street_name, latitude, longitude)

    temporary_path = None
    capture = None
    output_video = None
    try:
        suffix = Path(file.filename).suffix or ".video"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temporary_file:
            temporary_path = temporary_file.name
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                temporary_file.write(chunk)

        capture = cv2.VideoCapture(temporary_path)
        if not capture.isOpened():
            raise HTTPException(status_code=400, detail="The uploaded file is not a readable video")

        model = get_model()
        frame_number = 0
        frames_processed = 0
        detections_seen = 0
        created_count = 0
        updated_count = 0
        frame_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        frame_area = max(frame_width * frame_height, 1)
        fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
        output_name = "{}-{}.avi".format(Path(file.filename).stem, secrets.token_hex(4))
        output_path = OUTPUT_DIR / output_name
        output_video = cv2.VideoWriter(
            str(output_path),
            cv2.VideoWriter_fourcc(*"MJPG"),
            fps,
            (frame_width, frame_height),
        )
        if not output_video.isOpened():
            raise HTTPException(status_code=500, detail="Could not create the annotated output video")
        affected_codes = []
        video_tracks = []
        updated_codes = set()
        reused_database_codes = set()
        has_gps = True

        while True:
            read_success, frame = capture.read()
            if not read_success:
                break
            frame_number += 1
            annotated_frame = frame.copy()

            if frame_number % FRAME_INTERVAL == 0:
                frames_processed += 1
                result = model.predict(source=frame, conf=0.20, verbose=False)[0]
                if result.boxes is not None:
                    for box in result.boxes:
                        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                        if ((y1 + y2) / 2) < frame_height * 0.25:
                            continue
                        confidence = float(box.conf[0])
                        box_area = max(0, x2 - x1) * max(0, y2 - y1)
                        severity = min(round((box_area / frame_area * 100) * confidence * 10, 2), 10.0)
                        detections_seen += 1
                        detection_box = [x1, y1, x2, y2]
                        cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                        label = "Pothole | {:.2f} | Sev: {:.2f}".format(confidence, severity)
                        cv2.putText(
                            annotated_frame,
                            label,
                            (x1, max(y1 - 8, 20)),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.55,
                            (0, 0, 255),
                            2,
                        )
                        track = next(
                            (
                                item for item in video_tracks
                                if bounding_box_iou(item["bbox"], detection_box) >= 0.25
                            ),
                            None,
                        )
                        existing = track["defect"] if track else None
                        if existing is None and has_gps:
                            existing = find_nearby_open_defect(db, latitude, longitude)
                            if existing is not None and existing.defect_code in reused_database_codes:
                                existing = None

                        if existing is not None:
                            if existing.defect_code not in affected_codes:
                                affected_codes.append(existing.defect_code)
                            if severity > existing.severity_score:
                                apply_metrics(existing, severity)
                                if existing.defect_code not in updated_codes:
                                    updated_codes.add(existing.defect_code)
                                    updated_count += 1
                            if z_impact_spike != 0.0:
                                existing.telemetry_verified = True
                            if track is None:
                                video_tracks.append({"bbox": detection_box, "defect": existing})
                                reused_database_codes.add(existing.defect_code)
                            else:
                                track["bbox"] = detection_box
                            continue

                        defect = Defect(
                            defect_code="DEF-{}".format(secrets.token_hex(2).upper()),
                            latitude=latitude,
                            longitude=longitude,
                            telemetry_verified=z_impact_spike != 0.0,
                        )
                        apply_metrics(defect, severity)
                        db.add(defect)
                        db.flush()
                        affected_codes.append(defect.defect_code)
                        video_tracks.append({"bbox": detection_box, "defect": defect})
                        created_count += 1

            output_video.write(annotated_frame)

        capture.release()
        capture = None
        output_video.release()
        output_video = None
        db.commit()
        affected_defects = db.scalars(
            select(Defect).where(Defect.defect_code.in_(affected_codes))
        ).all() if affected_codes else []
        total_materials = {
            "asphalt_volume_m3": round(sum(defect.asphalt_volume_m3 for defect in affected_defects), 4),
            "asphalt_weight_tonnes": round(sum(defect.asphalt_weight_tonnes for defect in affected_defects), 4),
            "bags_25kg": sum(defect.bags_25kg for defect in affected_defects),
            "tack_coat_liters": round(sum(defect.tack_coat_liters for defect in affected_defects), 4),
            "estimated_cost_usd": round(sum(defect.estimated_cost_usd for defect in affected_defects), 2),
            "estimated_cost_inr": round(sum(defect.estimated_cost_inr for defect in affected_defects), 2),
        }
        video_url = "/outputs/{}".format(output_name)
        video_url = "{}{}".format(str(request.base_url).rstrip("/"), video_url)
        return {
            "filename": file.filename,
            "annotated_video_url": video_url,
            "location": {
                "street_name": street_name.strip() if street_name else None,
                "latitude": latitude,
                "longitude": longitude,
            },
            "frames_processed": frames_processed,
            "detections_seen": detections_seen,
            "defects_created": created_count,
            "defects_updated": updated_count,
            "deduplication_radius_m": DEDUPLICATION_RADIUS_METERS,
            "defects": [defect_payload(defect) for defect in affected_defects],
            "total_materials_and_cost": total_materials,
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Video processing failed: {exc}") from exc
    finally:
        if capture is not None:
            capture.release()
        if output_video is not None:
            output_video.release()
        if temporary_path:
            try:
                os.unlink(temporary_path)
            except OSError:
                pass


@app.get("/api/v1/map-pins")
def map_pins(db: Session = Depends(get_db)) -> List[Dict]:
    defects = db.scalars(select(Defect)).all()
    return [
        {
            "defect_code": defect.defect_code,
            "latitude": defect.latitude,
            "longitude": defect.longitude,
            "severity_score": defect.severity_score,
            "urgency_level": defect.urgency_level,
            "status": defect.status,
        }
        for defect in defects
    ]


@app.get("/api/v1/dispatch-queue")
def dispatch_queue(db: Session = Depends(get_db)) -> List[Dict]:
    defects = db.scalars(
        select(Defect).where(Defect.status == "OPEN").order_by(Defect.severity_score.desc())
    ).all()
    return [defect_payload(defect) for defect in defects]


@app.patch("/api/v1/tickets/{defect_code}/resolve")
def resolve_ticket(defect_code: str, db: Session = Depends(get_db)) -> dict:
    defect = db.scalar(select(Defect).where(Defect.defect_code == defect_code))
    if defect is None:
        raise HTTPException(status_code=404, detail="Defect not found")
    if defect.status == "RESOLVED":
        return defect_payload(defect)
    defect.status = "RESOLVED"
    db.commit()
    db.refresh(defect)
    return defect_payload(defect)