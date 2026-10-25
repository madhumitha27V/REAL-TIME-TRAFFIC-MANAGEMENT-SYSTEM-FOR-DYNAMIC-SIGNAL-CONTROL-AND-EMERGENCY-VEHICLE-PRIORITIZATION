import csv
import json
import mimetypes
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent
IMAGE_DIR = ROOT / "images"
OUTPUT_CSV = ROOT / "data" / "results" / "yolo_vehicle_counts.csv"
API_URL = "http://127.0.0.1:8000/api/detect-image"

extensions = {".jpg", ".jpeg", ".png", ".webp"}
images = [
    p for p in sorted(IMAGE_DIR.iterdir())
    if p.is_file()
    and p.suffix.lower() in extensions
    and not p.stem.lower().endswith("_detected")
]

rows = []

for image_path in images:
    print(f"\nProcessing: {image_path.name}")

    content_type = mimetypes.guess_type(image_path.name)[0]
    if content_type not in {"image/jpeg", "image/png", "image/webp"}:
        print(f"Unsupported image type: {content_type}")
        continue

    boundary = "----SmartFlowBoundary8MA4YWxkTrZu0gW"
    image_bytes = image_path.read_bytes()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{image_path.name}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode("utf-8") + image_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

    request = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}"
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))

        print(json.dumps(result, indent=2)[:2000])

        counts = result.get("counts", result.get("vehicle_counts", {}))
        total = result.get("total_vehicles", result.get("total"))

        if not counts:
            # Some APIs return counts under a different structure.
            print("Response structure needs inspection; saved raw response.")
            rows.append({
                "image": image_path.name,
                "cars": "",
                "motorcycles": "",
                "buses": "",
                "trucks": "",
                "total_vehicles": total if total is not None else "",
                "status": "Inspect response JSON",
                "raw_response": json.dumps(result),
            })
            continue

        rows.append({
            "image": image_path.name,
            "cars": counts.get("car", counts.get("cars", 0)),
            "motorcycles": counts.get("motorcycle", counts.get("motorcycles", 0)),
            "buses": counts.get("bus", counts.get("buses", 0)),
            "trucks": counts.get("truck", counts.get("trucks", 0)),
            "total_vehicles": total if total is not None else sum(counts.values()),
            "status": "success",
            "raw_response": "",
        })

    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code}: {error_body}")
        rows.append({
            "image": image_path.name,
            "cars": "",
            "motorcycles": "",
            "buses": "",
            "trucks": "",
            "total_vehicles": "",
            "status": f"HTTP {exc.code}: {error_body}",
            "raw_response": "",
        })

    except Exception as exc:
        print(f"ERROR: {exc}")
        rows.append({
            "image": image_path.name,
            "cars": "",
            "motorcycles": "",
            "buses": "",
            "trucks": "",
            "total_vehicles": "",
            "status": str(exc),
            "raw_response": "",
        })

OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
fields = [
    "image", "cars", "motorcycles", "buses",
    "trucks", "total_vehicles", "status", "raw_response"
]

with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(file, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)

print(f"\nSaved results to: {OUTPUT_CSV}")
