import os
import shutil
import traci
from backend.database import get_db_connection

SUMO_HOME = os.environ.get("SUMO_HOME")



SUMO_CONFIG = os.path.abspath(
    "sumo/config/junction_traffic.sumocfg"
)

TLS_ID = "B1"

MIN_GREEN = 10
MAX_GREEN = 35
YELLOW_TIME = 3
SIMULATION_END = 300
EMERGENCY_DETECTION_DISTANCE = 150

NORTH_SOUTH_EDGES = ["B2B1", "B0B1"]
EAST_WEST_EDGES = ["C1B1", "A1B1"]


def save_signal_event(previous_phase, new_phase, reason):
    """Save a signal phase change to MySQL."""
    connection = get_db_connection()

    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO signal_events
            (
                junction_id,
                previous_phase,
                new_phase,
                reason
            )
            VALUES (%s, %s, %s, %s)
            """,
            (
                TLS_ID,
                previous_phase,
                new_phase,
                reason,
            ),
        )
        connection.commit()
        cursor.close()
    finally:
        connection.close()


def count_vehicles(edge_ids):
    """Count vehicles on incoming lanes."""
    total = 0

    for edge_id in edge_ids:
        lane_count = traci.edge.getLaneNumber(edge_id)

        for lane_index in range(lane_count):
            lane_id = f"{edge_id}_{lane_index}"
            total += traci.lane.getLastStepVehicleNumber(lane_id)

    return total


def detect_ambulance():
    """Detect the ambulance approaching the central junction."""
    ambulance_id = "ambulance_1"

    if ambulance_id not in traci.vehicle.getIDList():
        return None

    edge_id = traci.vehicle.getRoadID(ambulance_id)

    if edge_id not in NORTH_SOUTH_EDGES + EAST_WEST_EDGES:
        return None

    lane_id = traci.vehicle.getLaneID(ambulance_id)
    lane_position = traci.vehicle.getLanePosition(ambulance_id)
    lane_length = traci.lane.getLength(lane_id)

    distance_to_junction = lane_length - lane_position

    if distance_to_junction > EMERGENCY_DETECTION_DISTANCE:
        return None

    if edge_id in NORTH_SOUTH_EDGES:
        return "N/S"

    return "E/W"


def main():
    if not os.path.isfile(SUMO_CONFIG):
        raise FileNotFoundError(
            f"SUMO configuration not found: {SUMO_CONFIG}"
        )

    sumo_binary = shutil.which("sumo")

    if not sumo_binary and SUMO_HOME:
        executable_name = "sumo.exe" if os.name == "nt" else "sumo"
        candidate = os.path.join(SUMO_HOME, "bin", executable_name)

        if os.path.isfile(candidate):
            sumo_binary = candidate

    if not sumo_binary:
        raise FileNotFoundError(
            "SUMO executable not found. Install SUMO and configure "
            "SUMO_HOME or add the SUMO executable to PATH."
        )
    os.makedirs("data/results", exist_ok=True)

    seed = int(os.environ.get("SMARTFLOW_SEED", "1"))
    tripinfo_file = os.environ.get(
        "SMARTFLOW_TRIPINFO",
        os.path.abspath("data/results/adaptive_tripinfo.xml"),
    )

    traci.start([
        sumo_binary,
        "-c", SUMO_CONFIG,
        "--end", str(SIMULATION_END),
        "--seed", str(seed),
        "--tripinfo-output", tripinfo_file,
        "--no-step-log",
    ])

    try:
        last_phase = -1
        emergency_priority = None
        ambulance_was_detected = False
        emergency_transition_requested = False

        while traci.simulation.getTime() < SIMULATION_END:
            traci.simulationStep()

            current_time = traci.simulation.getTime()
            phase = traci.trafficlight.getPhase(TLS_ID)

            if phase != last_phase:
                print(
                    f"SIGNAL PHASE | Time={current_time:.0f}s | "
                    f"Phase={phase} | "
                    f"State={traci.trafficlight.getRedYellowGreenState(TLS_ID)}"
                )

                try:
                    save_signal_event(
                        previous_phase=(
                            last_phase if last_phase >= 0 else None
                        ),
                        new_phase=phase,
                        reason=(
                            "emergency_priority"
                            if emergency_priority is not None
                            else "adaptive_cycle"
                        ),
                    )
                except Exception as error:
                    print(f"MYSQL SIGNAL LOG ERROR | {error}")

            emergency_direction = detect_ambulance()

            # Detect and remember the emergency request.
            if emergency_direction is not None:
                if not ambulance_was_detected:
                    print(
                        f"EMERGENCY DETECTED | "
                        f"Direction={emergency_direction} | "
                        f"Time={current_time:.0f}s"
                    )

                emergency_priority = emergency_direction

                if not emergency_transition_requested:
                    if phase == 0:
                        current_direction = "N/S"
                    elif phase == 2:
                        current_direction = "E/W"
                    else:
                        current_direction = None

                    if current_direction == emergency_direction:
                        traci.trafficlight.setPhaseDuration(
                            TLS_ID, MAX_GREEN
                        )

                        print(
                            f"EMERGENCY PRIORITY ACTIVE | "
                            f"Direction={emergency_direction} | "
                            f"Time={current_time:.0f}s"
                        )

                    elif current_direction is not None:
                        traci.trafficlight.setPhaseDuration(
                            TLS_ID, 1
                        )

                        print(
                            f"EMERGENCY TRANSITION REQUESTED | "
                            f"Direction={emergency_direction} | "
                            f"Time={current_time:.0f}s"
                        )

                    emergency_transition_requested = True

                ambulance_was_detected = True

            # Clear the request after the ambulance reaches
            # the next edge beyond the central junction.
            ambulance_id = "ambulance_1"

            if (
                ambulance_was_detected
                and ambulance_id in traci.vehicle.getIDList()
            ):
                ambulance_edge = traci.vehicle.getRoadID(
                    ambulance_id
                )

                if ambulance_edge == "B1C1":
                    emergency_priority = None
                    ambulance_was_detected = False
                    emergency_transition_requested = False

                    print(
                        f"AMBULANCE CLEARED | "
                        f"Time={current_time:.0f}s"
                    )

            # Adjust timing only when a new phase begins.
            if phase != last_phase:
                if phase == 0:
                    direction = "N/S"
                    edges = NORTH_SOUTH_EDGES

                elif phase == 2:
                    direction = "E/W"
                    edges = EAST_WEST_EDGES

                else:
                    # Do not modify yellow phases.
                    last_phase = phase
                    continue

                demand = count_vehicles(edges)

                green_time = min(
                    MAX_GREEN,
                    max(
                        MIN_GREEN,
                        MIN_GREEN + demand // 2
                    )
                )

                if emergency_priority == direction:
                    green_time = MAX_GREEN

                    print(
                        f"EMERGENCY PRIORITY | "
                        f"Direction={direction} | "
                        f"Green={green_time}s"
                    )

                print(
                    f"Time={current_time:.0f}s | "
                    f"Direction={direction} | "
                    f"Vehicles={demand} | "
                    f"Green={green_time}s | "
                    f"Emergency={emergency_priority == direction}"
                )

                traci.trafficlight.setPhaseDuration(
                    TLS_ID, green_time
                )

            last_phase = phase

        print(
            f"\nSimulation stopped at "
            f"{traci.simulation.getTime():.0f} seconds."
        )

    finally:
        traci.close()


if __name__ == "__main__":
    main()
