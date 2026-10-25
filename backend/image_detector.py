
from pathlib import Path

import cv2
from ultralytics import YOLO

MODEL_NAME = "yolo11n.pt"

VEHICLE_CLASSES = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}


def main():
    image_path = input(
        "Enter the full path of your traffic image: "
    ).strip().strip('"')

    image_file = Path(image_path)

    if not image_file.is_file():
        print("ERROR: Image file not found.")
        return

    image = cv2.imread(str(image_file))

    if image is None:
        print("ERROR: Could not read this image.")
        return

    print("Loading YOLO model...")
    model = YOLO(MODEL_NAME)

    results = model.predict(
        source=image,
        conf=0.15,
        imgsz=960,
        verbose=False,
    )

    result = results[0]
    output_image = result.plot()

    counts = {
        name: 0 for name in VEHICLE_CLASSES.values()
    }

    for box in result.boxes:
        class_id = int(box.cls[0])

        if class_id in VEHICLE_CLASSES:
            counts[VEHICLE_CLASSES[class_id]] += 1

    print("\nVehicle Detection Results")
    print("-" * 30)

    for vehicle, count in counts.items():
        print(f"{vehicle.title()}: {count}")

    print(f"Total vehicles: {sum(counts.values())}")

    output_path = image_file.with_name(
        image_file.stem + "_detected.jpg"
    )

    if cv2.imwrite(str(output_path), output_image):
        print(f"\nDetection image saved to:\n{output_path}")
    else:
        print("\nERROR: Could not save the output image.")

    cv2.imshow("SmartFlow AI - Image Detection", output_image)
    print("\nPress any key in the image window to close.")

    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
