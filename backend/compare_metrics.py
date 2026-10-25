
import csv
import os
import xml.etree.ElementTree as ET

RESULTS_DIR = os.path.abspath("data/results")

BASELINE_FILE = os.path.join(
    RESULTS_DIR, "baseline_tripinfo.xml"
)
ADAPTIVE_FILE = os.path.join(
    RESULTS_DIR, "adaptive_tripinfo.xml"
)
OUTPUT_FILE = os.path.join(
    RESULTS_DIR, "performance_comparison.csv"
)


def calculate_metrics(xml_file):
    if not os.path.exists(xml_file):
        raise FileNotFoundError(
            f"Tripinfo file not found: {xml_file}"
        )

    completed_trips = 0
    total_waiting = 0.0
    total_duration = 0.0
    total_time_loss = 0.0

    for _, trip in ET.iterparse(xml_file, events=("end",)):
        if trip.tag == "tripinfo":
            completed_trips += 1
            total_waiting += float(
                trip.get("waitingTime", 0)
            )
            total_duration += float(
                trip.get("duration", 0)
            )
            total_time_loss += float(
                trip.get("timeLoss", 0)
            )
            trip.clear()

    if completed_trips == 0:
        raise ValueError(
            f"No completed trips found in {xml_file}"
        )

    return {
        "completed_trips": completed_trips,
        "average_waiting_time_seconds": (
            total_waiting / completed_trips
        ),
        "average_trip_duration_seconds": (
            total_duration / completed_trips
        ),
        "average_time_loss_seconds": (
            total_time_loss / completed_trips
        ),
    }


def main():
    systems = {
        "Baseline": calculate_metrics(BASELINE_FILE),
        "Adaptive": calculate_metrics(ADAPTIVE_FILE),
    }

    baseline = systems["Baseline"]
    adaptive = systems["Adaptive"]

    metrics = [
        "average_waiting_time_seconds",
        "average_trip_duration_seconds",
        "average_time_loss_seconds",
    ]

    for metric in metrics:
        before = baseline[metric]
        after = adaptive[metric]

        improvement = (
            (before - after) / before * 100
            if before != 0
            else 0.0
        )

        adaptive[
            metric.replace(
                "_seconds", "_improvement_percent"
            )
        ] = round(improvement, 2)

    os.makedirs(RESULTS_DIR, exist_ok=True)

    fields = [
        "system",
        "completed_trips",
        "average_waiting_time_seconds",
        "average_trip_duration_seconds",
        "average_time_loss_seconds",
        "average_waiting_time_improvement_percent",
        "average_trip_duration_improvement_percent",
        "average_time_loss_improvement_percent",
    ]

    with open(
        OUTPUT_FILE, "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()

        for name, metrics_data in systems.items():
            row = {"system": name, **metrics_data}
            writer.writerow(row)

    print("\nSMARTFLOW AI PERFORMANCE COMPARISON")
    print("-" * 48)

    for name, values in systems.items():
        print(f"\n{name}")
        print(f"Completed trips: {values['completed_trips']}")
        print(
            "Average waiting time: "
            f"{values['average_waiting_time_seconds']:.2f} s"
        )
        print(
            "Average trip duration: "
            f"{values['average_trip_duration_seconds']:.2f} s"
        )
        print(
            "Average time loss: "
            f"{values['average_time_loss_seconds']:.2f} s"
        )

    print("\nADAPTIVE IMPROVEMENT")
    for metric in metrics:
        improvement_key = metric.replace(
            "_seconds", "_improvement_percent"
        )
        print(
            f"{metric}: "
            f"{adaptive[improvement_key]:.2f}%"
        )

    print(f"\nCSV saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
