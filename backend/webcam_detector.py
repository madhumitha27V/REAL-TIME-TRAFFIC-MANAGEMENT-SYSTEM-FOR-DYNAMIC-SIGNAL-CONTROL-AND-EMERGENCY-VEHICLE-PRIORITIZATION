
import cv2
from ultralytics import YOLO

MODEL_NAME = "yolo11n.pt"
CONFIDENCE = 0.15

VEHICLE_CLASSES = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}


def main():
    print("Loading YOLO model...")
    model = YOLO(MODEL_NAME)
    print("Model loaded successfully.")

    camera = cv2.VideoCapture(0)

    if not camera.isOpened():
        print("ERROR: Could not open webcam.")
        return

    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    print("Webcam started.")
    print("Show vehicles clearly in front of the camera.")
    print("Press Q to quit.")

    try:
        while True:
            success, frame = camera.read()

            if not success:
                print("ERROR: Failed to read camera frame.")
                break

            results = model.predict(
                source=frame,
                conf=CONFIDENCE,
                imgsz=960,
                verbose=False,
            )

            counts = {
                name: 0 for name in VEHICLE_CLASSES.values()
            }

            # Draw every detection returned by YOLO.
            annotated_frame = results[0].plot()

            for box in results[0].boxes:
                class_id = int(box.cls[0])

                if class_id in VEHICLE_CLASSES:
                    vehicle_name = VEHICLE_CLASSES[class_id]
                    counts[vehicle_name] += 1

            # Display vehicle counts.
            y = 35
            total = sum(counts.values())

            cv2.putText(
                annotated_frame,
                f"Total vehicles: {total}",
                (15, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 255),
                2,
            )

            for name, count in counts.items():
                y += 30
                cv2.putText(
                    annotated_frame,
                    f"{name.title()}: {count}",
                    (15, y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 255),
                    2,
                )

            cv2.imshow(
                "SmartFlow AI - Vehicle Detection",
                annotated_frame,
            )

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:
        camera.release()
        cv2.destroyAllWindows()
        print("Detector stopped.")


if __name__ == "__main__":
    main()
