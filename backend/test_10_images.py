
from pathlib import Path
import csv
import cv2
from ultralytics import YOLO

PROJECT_DIR = Path(__file__).resolve().parent.parent
IMAGE_DIR = PROJECT_DIR / "images"
OUTPUT_DIR = PROJECT_DIR / "data" / "image_test_results"

MODEL_NAME = "yolo11n.pt"
CONFIDENCE = 0.15

VEHICLE_CLASSES = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not IMAGE_DIR.exists():
        print(f"Image folder not found: {IMAGE_DIR}")
        return

    image_files = sorted(
        p for p in IMAGE_DIR.iterdir()
        if p.is_file()
        and p.suffix.lower() in {".jpg", ".jpeg", ".png"}
        and not p.stem.endswith("_detected")
    )[:10]

    if len(image_files) != 10:
        print(f"Warning: Found {len(image_files)} images, not 10.")

    if not image_files:
        print("Add images to the images folder first.")
        return

    print("Loading YOLO model...")
    model = YOLO(MODEL_NAME)

    csv_path = OUTPUT_DIR / "results.csv"
    rows = []

    for index, image_path in enumerate(image_files, start=1):
        print(f"\nTesting {index}/{len(image_files)}: {image_path.name}")

        image = cv2.imread(str(image_path))

        if image is None:
            print("Could not read this image. Skipping.")
            continue

        result = model.predict(
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

        output_image = result.plot()
        output_path = OUTPUT_DIR / f"{image_path.stem}_detected.jpg"

        if not cv2.imwrite(str(output_path), output_image):
            print("Could not save annotated image.")

        total = sum(counts.values())

        print(f"Cars: {counts['car']}")
        print(f"Motorcycles: {counts['motorcycle']}")
        print(f"Buses: {counts['bus']}")
        print(f"Trucks: {counts['truck']}")
        print(f"Total vehicles: {total}")

        rows.append({
            "image": image_path.name,
            **counts,
            "total_vehicles": total,
            "annotated_image": output_path.name,
        })

    if rows:
        with csv_path.open(
            "w", newline="", encoding="utf-8"
        ) as file:
            writer = csv.DictWriter(
                file, fieldnames=rows[0].keys()
            )
            writer.writeheader()
            writer.writerows(rows)

    print("\n========== TESTING COMPLETED ==========")
    print(f"Images processed: {len(rows)}")
    print(f"Annotated images: {OUTPUT_DIR}")
    print(f"Results CSV: {csv_path}")


if __name__ == "__main__":
    main()
