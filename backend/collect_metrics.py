
import csv
import os
import sys
import traci

SUMO_HOME = os.environ.get("SUMO_HOME")

if not SUMO_HOME:
    raise RuntimeError("SUMO_HOME is not set.")

SUMO_CONFIG = os.path.abspath(
    "sumo/config/junction_traffic.sumocfg"
)

OUTPUT_FILE = os.path.abspath(
    "data/results/adaptive_metrics.csv"
)

SIMULATION_END = 300


def main():
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    sumo_binary = os.path.join(SUMO_HOME, "bin", "sumo.exe")

    traci.start([
        sumo_binary,
        "-c", SUMO_CONFIG,
        "--end", str(SIMULATION_END),
        "--tripinfo-output", OUTPUT_FILE.replace(
            "adaptive_metrics.csv", "adaptive_tripinfo.xml"
        ),
        "--no-step-log",
    ])

    try:
        while traci.simulation.getTime() < SIMULATION_END:
            traci.simulationStep()

        print("Simulation finished.")
        print(f"Trip information saved beside the CSV: {OUTPUT_FILE}")

    finally:
        traci.close()

    tripinfo_file = OUTPUT_FILE.replace(
        "adaptive_metrics.csv", "adaptive_tripinfo.xml"
    )

    import xml.etree.ElementTree as ET

    root = ET.parse(tripinfo_file).getroot()
    trips = root.findall("tripinfo")

    fields = [
        "vehicle_id",
        "duration_seconds",
        "waiting_time_seconds",
        "time_loss_seconds",
    ]

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()

        for trip in trips:
            writer.writerow({
                "vehicle_id": trip.get("id"),
                "duration_seconds": trip.get("duration"),
                "waiting_time_seconds": trip.get("waitingTime"),
                "time_loss_seconds": trip.get("timeLoss"),
            })

    print(f"Completed trips: {len(trips)}")
    print(f"CSV saved to: {OUTPUT_FILE}")

    if trips:
        avg_wait = sum(
            float(t.get("waitingTime", 0)) for t in trips
        ) / len(trips)

        avg_duration = sum(
            float(t.get("duration", 0)) for t in trips
        ) / len(trips)

        avg_loss = sum(
            float(t.get("timeLoss", 0)) for t in trips
        ) / len(trips)

        print(f"Average waiting time: {avg_wait:.2f} seconds")
        print(f"Average trip duration: {avg_duration:.2f} seconds")
        print(f"Average time loss: {avg_loss:.2f} seconds")
    else:
        print("No completed trips were recorded.")


if __name__ == "__main__":
    main()
