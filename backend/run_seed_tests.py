import csv
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "data" / "results"

SUMO_HOME = Path(
    os.environ.get("SUMO_HOME", r"C:\Program Files (x86)\SUMO")
)
SUMO = SUMO_HOME / "bin" / "sumo.exe"
SUMO_TOOLS = SUMO_HOME / "tools"

NETWORK = ROOT / "sumo" / "network" / "junction_3x3_signalized.net.xml"
ROUTES = ROOT / "sumo" / "routes" / "junction_traffic.rou.xml"
CONTROLLER = ROOT / "backend" / "adaptive_controller.py"

RESULTS.mkdir(parents=True, exist_ok=True)

if not SUMO.exists():
    raise FileNotFoundError(f"SUMO executable not found: {SUMO}")

if not (SUMO_TOOLS / "traci").exists():
    raise FileNotFoundError(
        f"TraCI module not found: {SUMO_TOOLS / 'traci'}"
    )

if not NETWORK.exists():
    raise FileNotFoundError(f"Network file not found: {NETWORK}")

if not ROUTES.exists():
    raise FileNotFoundError(f"Route file not found: {ROUTES}")


def metrics(xml_file):
    trips = []

    for _, item in ET.iterparse(xml_file, events=("end",)):
        if item.tag == "tripinfo":
            trips.append({
                "waiting": float(item.get("waitingTime", 0)),
                "duration": float(item.get("duration", 0)),
                "loss": float(item.get("timeLoss", 0)),
            })
            item.clear()

    if not trips:
        raise RuntimeError(
            f"No completed trips found in {xml_file}"
        )

    count = len(trips)

    return {
        "completed_trips": count,
        "average_waiting_time_seconds":
            sum(t["waiting"] for t in trips) / count,
        "average_trip_duration_seconds":
            sum(t["duration"] for t in trips) / count,
        "average_time_loss_seconds":
            sum(t["loss"] for t in trips) / count,
    }


all_results = []

for seed in range(1, 6):
    print(f"\n=== Seed {seed}: BASELINE ===", flush=True)

    baseline_xml = RESULTS / f"baseline_seed_{seed}.xml"

    subprocess.run(
        [
            str(SUMO),
            "--net-file", str(NETWORK),
            "--route-files", str(ROUTES),
            "--begin", "0",
            "--end", "300",
            "--step-length", "1",
            "--seed", str(seed),
            "--tripinfo-output", str(baseline_xml),
            "--no-step-log",
        ],
        cwd=ROOT,
        check=True,
    )

    baseline_result = metrics(baseline_xml)
    all_results.append({
        "seed": seed,
        "system": "Baseline",
        **baseline_result,
    })

    print(f"\n=== Seed {seed}: ADAPTIVE ===", flush=True)

    adaptive_xml = RESULTS / f"adaptive_seed_{seed}.xml"

    env = os.environ.copy()
    env["SMARTFLOW_SEED"] = str(seed)
    env["SMARTFLOW_TRIPINFO"] = str(adaptive_xml)

    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        str(SUMO_TOOLS)
        + (os.pathsep + existing_pythonpath if existing_pythonpath else "")
    )

    subprocess.run(
        [sys.executable, str(CONTROLLER)],
        cwd=ROOT,
        env=env,
        check=True,
    )

    adaptive_result = metrics(adaptive_xml)
    all_results.append({
        "seed": seed,
        "system": "Adaptive",
        **adaptive_result,
    })

    print(
        f"Seed {seed} completed | "
        f"Baseline waiting: "
        f"{baseline_result['average_waiting_time_seconds']:.2f}s | "
        f"Adaptive waiting: "
        f"{adaptive_result['average_waiting_time_seconds']:.2f}s",
        flush=True,
    )


csv_file = RESULTS / "five_seed_results.csv"

fields = [
    "seed",
    "system",
    "completed_trips",
    "average_waiting_time_seconds",
    "average_trip_duration_seconds",
    "average_time_loss_seconds",
]

with csv_file.open("w", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(file, fieldnames=fields)
    writer.writeheader()
    writer.writerows(all_results)


print("\n========== FIVE-SEED SUMMARY ==========")

for system in ("Baseline", "Adaptive"):
    rows = [
        result for result in all_results
        if result["system"] == system
    ]

    print(f"\n{system}")

    for key in (
        "completed_trips",
        "average_waiting_time_seconds",
        "average_trip_duration_seconds",
        "average_time_loss_seconds",
    ):
        average = sum(row[key] for row in rows) / len(rows)

        if key == "completed_trips":
            print(f"Average {key}: {average:.2f}")
        else:
            print(f"Average {key}: {average:.2f} seconds")


print(f"\nDetailed results saved to:\n{csv_file}")
print("\nAll five seeds completed successfully.")
