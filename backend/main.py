
from pathlib import Path
import csv
import re
import os
import subprocess
import sys
import threading
import time
import xml.etree.ElementTree as ET
import base64
import cv2
import numpy as np
from backend.database import get_db_connection

from fastapi import FastAPI, UploadFile, File, HTTPException
from ultralytics import YOLO
from fastapi.middleware.cors import CORSMiddleware

BASE_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = BASE_DIR / "data" / "results"
CONTROLLER_FILE = BASE_DIR / "backend" / "adaptive_controller.py"
LOG_FILE = RESULTS_DIR / "adaptive_controller.log"

app = FastAPI(
    title="SmartFlow AI API",
    description="Traffic simulation and adaptive signal performance API",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

simulation_lock = threading.Lock()
simulation_process = None
simulation_log = None
simulation_started_at = None
simulation_finished_at = None
simulation_last_exit_code = None
simulation_state = "idle"


def calculate_trip_metrics(file_path: Path):
    if not file_path.exists():
        return None

    completed = 0
    waiting = 0.0
    duration = 0.0
    time_loss = 0.0

    for _, trip in ET.iterparse(file_path, events=("end",)):
        if trip.tag == "tripinfo":
            completed += 1
            waiting += float(trip.get("waitingTime", 0))
            duration += float(trip.get("duration", 0))
            time_loss += float(trip.get("timeLoss", 0))
            trip.clear()

    if completed == 0:
        return {
            "completed_trips": 0,
            "average_waiting_time_seconds": 0,
            "average_trip_duration_seconds": 0,
            "average_time_loss_seconds": 0,
        }

    return {
        "completed_trips": completed,
        "average_waiting_time_seconds": round(waiting / completed, 2),
        "average_trip_duration_seconds": round(duration / completed, 2),
        "average_time_loss_seconds": round(time_loss / completed, 2),
    }


def save_simulation_result(mode: str, seed: int | None, metrics: dict):
    connection = get_db_connection()

    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO simulation_runs
            (
                mode, seed, status, completed_trips,
                average_waiting_time, average_trip_duration,
                average_time_loss
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                mode,
                seed,
                "completed",
                metrics["completed_trips"],
                metrics["average_waiting_time_seconds"],
                metrics["average_trip_duration_seconds"],
                metrics["average_time_loss_seconds"],
            ),
        )
        connection.commit()
        cursor.close()
    finally:
        connection.close()


def save_emergency_events_to_database(events: list):
    if not events:
        return 0

    connection = get_db_connection()
    saved_count = 0

    try:
        cursor = connection.cursor()

        for event in events:
            cursor.execute(
                """
                INSERT INTO emergency_events
                (vehicle_id, direction, detection_time, priority_status)
                VALUES (%s, %s, CURRENT_TIMESTAMP, %s)
                """,
                (
                    "ambulance",
                    event["direction"],
                    event["event_type"],
                ),
            )
            saved_count += 1

        connection.commit()
        cursor.close()
        return saved_count

    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

def save_signal_event(
    run_id,
    junction_id,
    previous_phase,
    new_phase,
    reason,
):
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO signal_events
            (run_id, junction_id, previous_phase, new_phase, reason)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                run_id,
                junction_id,
                previous_phase,
                new_phase,
                reason,
            ),
        )
        connection.commit()
        cursor.close()
    finally:
        connection.close()

def update_simulation_state():
    """Update status when the simulation process exits."""
    global simulation_state
    global simulation_finished_at
    global simulation_last_exit_code
    global simulation_log

    if simulation_process is not None and simulation_process.poll() is not None:
        simulation_last_exit_code = simulation_process.returncode

        if simulation_state == "running":
            simulation_state = (
                "completed" if simulation_last_exit_code == 0 else "failed"
            )

        if simulation_finished_at is None:
            simulation_finished_at = time.time()

        if simulation_log is not None and not simulation_log.closed:
            simulation_log.close()
            simulation_log = None


@app.get("/")
def home():
    return {
        "project": "SmartFlow AI",
        "status": "running",
        "message": "Traffic management API is ready",
    }


@app.get("/api/health")
def health():
    return {"status": "healthy"}


@app.get("/api/metrics")
def metrics():
    baseline = calculate_trip_metrics(
        RESULTS_DIR / "baseline_tripinfo.xml"
    )
    adaptive = calculate_trip_metrics(
        RESULTS_DIR / "adaptive_tripinfo.xml"
    )

    improvements = {}

    if baseline and adaptive:
        metric_names = [
            "average_waiting_time_seconds",
            "average_trip_duration_seconds",
            "average_time_loss_seconds",
        ]

        for metric in metric_names:
            before = baseline[metric]
            after = adaptive[metric]

            improvements[metric] = (
                round(((before - after) / before) * 100, 2)
                if before
                else 0
            )

    return {
        "baseline": baseline,
        "adaptive": adaptive,
        "improvements_percent": improvements,
    }


@app.post("/api/metrics/save")
def save_metrics_to_database():
    baseline = calculate_trip_metrics(
        RESULTS_DIR / "baseline_tripinfo.xml"
    )
    adaptive = calculate_trip_metrics(
        RESULTS_DIR / "adaptive_tripinfo.xml"
    )

    if baseline is None or adaptive is None:
        raise HTTPException(
            status_code=404,
            detail="Baseline or adaptive tripinfo XML file is missing.",
        )

    try:
        save_simulation_result("baseline", None, baseline)
        save_simulation_result("adaptive", None, adaptive)
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Could not save simulation metrics: {error}",
        ) from error

    return {
        "message": "Baseline and adaptive metrics saved to MySQL.",
        "baseline": baseline,
        "adaptive": adaptive,
    }

@app.get("/api/comparison")
def comparison():
    csv_path = RESULTS_DIR / "performance_comparison.csv"

    if not csv_path.exists():
        return {"message": "Comparison CSV has not been generated yet"}

    with csv_path.open("r", newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))

    return {"results": rows}

@app.get("/api/emergency-events")
def emergency_events():
    if not LOG_FILE.exists():
        return {"events": [], "message": "No simulation log found."}

    events = []

    event_patterns = {
        "EMERGENCY DETECTED": "Ambulance detected",
        "EMERGENCY PRIORITY ACTIVE": "Emergency priority activated",
        "EMERGENCY TRANSITION REQUESTED": "Signal transition requested",
        "AMBULANCE CLEARED": "Ambulance cleared",
    }

    with LOG_FILE.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()

            for pattern, description in event_patterns.items():
                if pattern in line:
                    direction_match = re.search(
                        r"Direction=([^|]+)", line
                    )
                    time_match = re.search(
                        r"Time=(\d+)s", line
                    )

                    events.append({
                        "event": description,
                        "event_type": pattern,
                        "direction": (
                            direction_match.group(1).strip()
                            if direction_match
                            else None
                        ),
                        "simulation_time_seconds": (
                            int(time_match.group(1))
                            if time_match
                            else None
                        ),
                        "raw_message": line,
                    })
                    break


    try:
        saved_count = save_emergency_events_to_database(events)
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Could not save emergency events to MySQL: {error}",
        ) from error

    return {
        "events": events,
        "count": len(events),
        "saved_to_database": saved_count,
    }


@app.get("/api/simulation/status")
def get_simulation_status():
    update_simulation_state()

    elapsed_seconds = None
    if simulation_started_at is not None:
        end_time = (
            simulation_finished_at
            if simulation_finished_at is not None
            else time.time()
        )
        elapsed_seconds = round(end_time - simulation_started_at, 1)

    return {
        "state": simulation_state,
        "running": (
            simulation_process is not None
            and simulation_process.poll() is None
        ),
        "elapsed_seconds": elapsed_seconds,
        "exit_code": simulation_last_exit_code,
        "log_file": str(LOG_FILE),
    }


@app.post("/api/simulation/start")
def start_simulation():
    global simulation_process
    global simulation_log
    global simulation_started_at
    global simulation_finished_at
    global simulation_last_exit_code
    global simulation_state

    with simulation_lock:
        update_simulation_state()

        if simulation_process is not None and simulation_process.poll() is None:
            raise HTTPException(
                status_code=409,
                detail="A simulation is already running.",
            )

        if not CONTROLLER_FILE.exists():
            raise HTTPException(
                status_code=500,
                detail=f"Controller file not found: {CONTROLLER_FILE}",
            )

        RESULTS_DIR.mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        sumo_home = env.get(
            "SUMO_HOME",
            r"C:\Program Files (x86)\SUMO",
        )
        env["SUMO_HOME"] = sumo_home
        env["PATH"] = (
            str(Path(sumo_home) / "bin")
            + os.pathsep
            + env.get("PATH", "")
        )
        env["PYTHONPATH"] = (
            str(Path(sumo_home) / "tools")
            + os.pathsep
            + env.get("PYTHONPATH", "")
        )

        try:
            simulation_log = LOG_FILE.open("w", encoding="utf-8")

            simulation_process = subprocess.Popen(
                [sys.executable, str(CONTROLLER_FILE)],
                cwd=str(BASE_DIR),
                env=env,
                stdout=simulation_log,
                stderr=subprocess.STDOUT,
            )

            simulation_started_at = time.time()
            simulation_finished_at = None
            simulation_last_exit_code = None
            simulation_state = "running"

        except Exception as exc:
            if simulation_log is not None and not simulation_log.closed:
                simulation_log.close()
            simulation_log = None
            simulation_state = "failed"

            raise HTTPException(
                status_code=500,
                detail=f"Could not start simulation: {exc}",
            ) from exc

    return {
        "message": "Adaptive simulation started.",
        "state": simulation_state,
        "process_id": simulation_process.pid,
    }


@app.post("/api/simulation/stop")
def stop_simulation():
    global simulation_state
    global simulation_finished_at
    global simulation_last_exit_code

    with simulation_lock:
        update_simulation_state()

        if simulation_process is None or simulation_process.poll() is not None:
            raise HTTPException(
                status_code=409,
                detail="There is no running simulation to stop.",
            )

        simulation_state = "stopping"

        try:
            simulation_process.terminate()

            try:
                simulation_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                simulation_process.kill()
                simulation_process.wait(timeout=5)

            simulation_last_exit_code = simulation_process.returncode
            simulation_finished_at = time.time()
            simulation_state = "stopped"

            if simulation_log is not None and not simulation_log.closed:
                simulation_log.close()

            return {
                "message": "Simulation stopped.",
                "state": simulation_state,
            }

        except Exception as exc:
            simulation_state = "failed"
            raise HTTPException(
                status_code=500,
                detail=f"Could not stop simulation: {exc}",
            ) from exc


# ---------- IMAGE-BASED VEHICLE DETECTION ----------

IMAGE_MODEL = None

VEHICLE_CLASSES = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}


@app.post("/api/detect-image")
async def detect_image(file: UploadFile = File(...)):
    global IMAGE_MODEL

    allowed_types = {"image/jpeg", "image/png", "image/webp"}

    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Upload a JPG, PNG, or WEBP image."
        )

    image_bytes = await file.read()

    if not image_bytes:
        raise HTTPException(
            status_code=400,
            detail="The uploaded image is empty."
        )

    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail="Image size must be 10 MB or less."
        )

    image_array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

    if image is None:
        raise HTTPException(
            status_code=400,
            detail="Could not read the uploaded image."
        )

    try:
        if IMAGE_MODEL is None:
            IMAGE_MODEL = YOLO("yolo11n.pt")

        result = IMAGE_MODEL.predict(
            source=image,
            conf=0.10,
            imgsz=1280,
            iou=0.5,
            max_det=1000,
            verbose=False,
        )[0]

        counts = {
            name: 0 for name in VEHICLE_CLASSES.values()
        }

        for box in result.boxes:
            class_id = int(box.cls[0])

            if class_id in VEHICLE_CLASSES:
                counts[VEHICLE_CLASSES[class_id]] += 1

        annotated_image = result.plot()

        success, encoded_image = cv2.imencode(
            ".jpg", annotated_image
        )

        if not success:
            raise HTTPException(
                status_code=500,
                detail="Could not encode the detection image."
            )

        image_base64 = base64.b64encode(
            encoded_image.tobytes()
        ).decode("utf-8")


        total_vehicles = sum(counts.values())

        connection = get_db_connection()
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO vehicle_counts
                (image_name, cars, motorcycles, buses, trucks, total_vehicles)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    file.filename or "uploaded_image",
                    counts["car"],
                    counts["motorcycle"],
                    counts["bus"],
                    counts["truck"],
                    total_vehicles,
                ),
            )
            connection.commit()
            cursor.close()
        finally:
            connection.close()

        return {
            "filename": file.filename,
            "counts": counts,
            "total_vehicles": total_vehicles,
            "annotated_image": image_base64,
        }


    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Vehicle detection failed: {str(error)}"
        )
    finally:
        await file.close()
