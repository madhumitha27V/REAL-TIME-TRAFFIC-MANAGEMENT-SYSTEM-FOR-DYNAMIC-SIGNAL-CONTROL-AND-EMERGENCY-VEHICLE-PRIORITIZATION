
import { useEffect, useState } from "react";
import "./App.css";

const API = "http://127.0.0.1:8000";

const NAV_ITEMS = [
  { name: "Dashboard", icon: "▦", available: true },
  { name: "Live Monitoring", icon: "◉", available: false },
  { name: "Vehicle Detection", icon: "◇", available: true },
  { name: "Signal Control", icon: "⇄", available: true, page: "Traffic Optimization" },
  { name: "Simulation Results", icon: "▤", available: true, page: "Performance Reports" },
  { name: "Settings", icon: "⚙", available: false },
];

const VEHICLE_TYPES = [
  { key: "car", label: "Cars", icon: "🚗" },
  { key: "motorcycle", label: "Motorcycles", icon: "🏍️" },
  { key: "bus", label: "Buses", icon: "🚌" },
  { key: "truck", label: "Trucks", icon: "🚚" },
];

function MetricCard({ title, baseline, adaptive, unit, improvement, improvementLabel = "reduction" }) {
  return (
    <div className="metric-card">
      <p className="metric-title">{title}</p>

      <div className="metric-values">
        <div>
          <span className="metric-label">Baseline</span>
          <h2>
            {baseline ?? "—"} <small>{unit}</small>
          </h2>
        </div>

        <div>
          <span className="metric-label adaptive-label">Adaptive</span>
          <h2 className="green">
            {adaptive ?? "—"} <small>{unit}</small>
          </h2>
        </div>
      </div>

      <div className="improvement">
        {improvement == null ? "Recorded comparison" : `${improvement}% ${improvementLabel}`}
      </div>
    </div>
  );
}

function App() {
  const [activePage, setActivePage] = useState("Dashboard");
  const [metrics, setMetrics] = useState(null);
  const [emergencyEvents, setEmergencyEvents] = useState([]);
  const [eventsLoading, setEventsLoading] = useState(true);
  const [eventsError, setEventsError] = useState("");
  const [status, setStatus] = useState("Connecting...");

  const [simulation, setSimulation] = useState({
    state: "idle",
    running: false,
    elapsed_seconds: 0,
    exit_code: null,
  });

  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  // Vehicle detection state
  const [selectedImage, setSelectedImage] = useState(null);
  const [imagePreview, setImagePreview] = useState("");
  const [detectionResult, setDetectionResult] = useState(null);
  const [detecting, setDetecting] = useState(false);
  const [detectionError, setDetectionError] = useState("");

  async function loadMetrics() {
    try {
      const response = await fetch(`${API}/api/metrics`);

      if (!response.ok) {
        throw new Error("Could not load metrics");
      }

      const data = await response.json();
      setMetrics(data);
      setStatus("Backend connected");
      setError("");
    } catch {
      setStatus("Backend disconnected");
      setError("Cannot connect to the backend. Check that FastAPI is running.");
    }
  }

  async function loadEmergencyEvents() {
    try {
      const response = await fetch(`${API}/api/emergency-events`);

      if (!response.ok) {
        throw new Error("Could not load emergency events");
      }

      const data = await response.json();
      setEmergencyEvents(data.events || []);
      setEventsError("");
    } catch {
      setEventsError("Could not load emergency events.");
    } finally {
      setEventsLoading(false);
    }
  }

  async function loadSimulationStatus() {
    try {
      const response = await fetch(`${API}/api/simulation/status`);

      if (!response.ok) {
        throw new Error("Could not load simulation status");
      }

      const data = await response.json();

      setSimulation((previous) => {
        if (
          previous.state !== "completed" &&
          data.state === "completed"
        ) {
          setMessage("Simulation completed. Results have been refreshed.");
          loadMetrics();
        }

        if (data.state === "failed") {
          setMessage("Simulation failed. Check the controller log.");
        }

        return data;
      });

      setStatus("Backend connected");
    } catch {
      setStatus("Backend disconnected");
    }
  }

  async function startSimulation() {
    setBusy(true);
    setError("");
    setMessage("");

    try {
      const response = await fetch(`${API}/api/simulation/start`, {
        method: "POST",
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || data.message || "Could not start simulation"
        );
      }

      setMessage(data.message || "Simulation started.");
      await loadSimulationStatus();
    } catch (err) {
      setError(err.message || "Failed to start simulation.");
    } finally {
      setBusy(false);
    }
  }

  async function stopSimulation() {
    setBusy(true);
    setError("");
    setMessage("");

    try {
      const response = await fetch(`${API}/api/simulation/stop`, {
        method: "POST",
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || data.message || "Could not stop simulation"
        );
      }

      setMessage(data.message || "Stop request completed.");
      await loadSimulationStatus();
    } catch (err) {
      setError(err.message || "Failed to stop simulation.");
    } finally {
      setBusy(false);
    }
  }

  // Create and clean up the local image preview URL.
  useEffect(() => {
    if (!selectedImage) {
      setImagePreview("");
      return;
    }

    const previewUrl = URL.createObjectURL(selectedImage);
    setImagePreview(previewUrl);

    return () => URL.revokeObjectURL(previewUrl);
  }, [selectedImage]);

  // Upload the image to the FastAPI YOLO endpoint.
  async function detectVehicles() {
    if (!selectedImage) {
      setDetectionError("Please select a traffic image first.");
      return;
    }

    setDetecting(true);
    setDetectionError("");
    setDetectionResult(null);

    try {
      const formData = new FormData();
      formData.append("file", selectedImage);

      const response = await fetch(`${API}/api/detect-image`, {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Vehicle detection failed."
        );
      }

      setDetectionResult(data);
    } catch (err) {
      setDetectionError(
        err.message || "Could not connect to the detection API."
      );
    } finally {
      setDetecting(false);
    }
  }

  function handleImageSelection(event) {
    const file = event.target.files?.[0];

    setDetectionError("");
    setDetectionResult(null);

    if (!file) {
      return;
    }

    const allowedTypes = [
      "image/jpeg",
      "image/png",
      "image/webp",
    ];

    if (!allowedTypes.includes(file.type)) {
      setSelectedImage(null);
      setDetectionError("Please select a JPG, PNG, or WEBP image.");
      event.target.value = "";
      return;
    }

    if (file.size > 10 * 1024 * 1024) {
      setSelectedImage(null);
      setDetectionError("Image size must be 10 MB or less.");
      event.target.value = "";
      return;
    }

    setSelectedImage(file);
  }

  function clearDetection() {
    setSelectedImage(null);
    setDetectionResult(null);
    setDetectionError("");

    const fileInput = document.getElementById("traffic-image-input");

    if (fileInput) {
      fileInput.value = "";
    }
  }

  useEffect(() => {
    loadMetrics();
    loadSimulationStatus();
    loadEmergencyEvents();

    const timer = setInterval(() => {
      loadSimulationStatus();
      loadEmergencyEvents();
    }, 2000);

    return () => clearInterval(timer);
  }, []);

  const baseline = metrics?.baseline;
  const adaptive = metrics?.adaptive;
  const improvements = metrics?.improvements_percent;
  const running = simulation.running;
  const elapsed = Number(simulation.elapsed_seconds || 0).toFixed(1);

  function renderDashboard() {
    return (
      <>
        <header className="topbar">
          <div>
            <p className="eyebrow">TRAFFIC INTELLIGENCE PLATFORM</p>
            <h1>Traffic Management Dashboard</h1>
            <p className="subtitle">
              Adaptive signal optimization and emergency vehicle prioritization
            </p>
          </div>

          <button
            className="refresh-button"
            onClick={() => {
              loadMetrics();
              loadSimulationStatus();
            }}
          >
            ↻ Refresh data
          </button>
        </header>

        <section className="panel simulation-controls">
          <div className="panel-header">
            <div>
              <h3>Simulation Control</h3>
              <p>Run the adaptive traffic controller in SUMO.</p>
            </div>

            <strong>
              {running ? "RUNNING" : simulation.state.toUpperCase()}
            </strong>
          </div>

          <div className="simulation-actions">
            <button
              className="start-button"
              onClick={startSimulation}
              disabled={busy || running}
            >
              {busy && !running ? "Please wait..." : "▶ Start Simulation"}
            </button>

            <button
              className="stop-button"
              onClick={stopSimulation}
              disabled={busy || !running}
            >
              ■ Stop Simulation
            </button>
          </div>

          <p className="simulation-info">
            State: <strong>{simulation.state}</strong>
            {" · "}
            Elapsed: <strong>{elapsed} seconds</strong>
            {simulation.exit_code !== null && (
              <> · Exit code: <strong>{simulation.exit_code}</strong></>
            )}
          </p>

          {running && (
            <p className="simulation-info">
              Simulation is running. Recorded metrics will refresh after it finishes.
            </p>
          )}

          {message && <p className="success-message">{message}</p>}
          {error && <p className="error-banner">{error}</p>}
        </section>

        <section className="overview">
          <div>
            <span className="section-label">SYSTEM OVERVIEW</span>
            <h2>Simulation Performance</h2>
            <p>
              Compare fixed-time signals with demand-responsive adaptive control.
            </p>
          </div>
          <span className="result-tag">RECORDED RESULTS</span>
        </section>

        <section className="metric-grid">
          <MetricCard
            title="Average Waiting Time"
            baseline={baseline?.average_waiting_time_seconds}
            adaptive={adaptive?.average_waiting_time_seconds}
            unit="sec"
            improvement={improvements?.average_waiting_time_seconds}
          />

          <MetricCard
            title="Average Trip Duration"
            baseline={baseline?.average_trip_duration_seconds}
            adaptive={adaptive?.average_trip_duration_seconds}
            unit="sec"
            improvement={improvements?.average_trip_duration_seconds}
          />

          <MetricCard
            title="Average Time Loss"
            baseline={baseline?.average_time_loss_seconds}
            adaptive={adaptive?.average_time_loss_seconds}
            unit="sec"
            improvement={improvements?.average_time_loss_seconds}
          />
          <MetricCard
            title="Average Completed Trips"
            baseline={baseline?.completed_trips}
            adaptive={adaptive?.completed_trips}
            unit="trips"
            improvement={
              baseline?.completed_trips && adaptive?.completed_trips
                ? (((adaptive.completed_trips - baseline.completed_trips) /
                    baseline.completed_trips) *
                    100).toFixed(2)
                : null
            }
            improvementLabel="increase"
          />
        </section>

        <section className="content-grid">
          <div className="panel">
            <div className="panel-header">
              <div>
                <h3>Traffic Control Comparison</h3>
                <p>Average metrics · lower values are better</p>
              </div>

              <span className="legend">
                <i /> Fixed-time <i className="legend-green" /> Adaptive AI
              </span>
            </div>

            {metrics ? (
              <div className="chart">
                {[
                  {
                    label: "Waiting time",
                    base: baseline?.average_waiting_time_seconds,
                    ai: adaptive?.average_waiting_time_seconds,
                  },
                  {
                    label: "Trip duration",
                    base: baseline?.average_trip_duration_seconds,
                    ai: adaptive?.average_trip_duration_seconds,
                  },
                  {
                    label: "Time loss",
                    base: baseline?.average_time_loss_seconds,
                    ai: adaptive?.average_time_loss_seconds,
                  },
                ].map((item) => {
                  const max = Math.max(item.base || 0, item.ai || 0, 1);

                  return (
                    <div className="bar-group" key={item.label}>
                      <div className="bar-label">{item.label}</div>

                      <div className="bar-row">
                        <div className="bar-track">
                          <div
                            className="bar fixed"
                            style={{
                              width: `${((item.base || 0) / max) * 100}%`,
                            }}
                          />
                        </div>
                        <span>{item.base ?? "—"} s</span>
                      </div>

                      <div className="bar-row">
                        <div className="bar-track">
                          <div
                            className="bar adaptive"
                            style={{
                              width: `${((item.ai || 0) / max) * 100}%`,
                            }}
                          />
                        </div>
                        <span>{item.ai ?? "—"} s</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="empty-state">Waiting for backend metrics…</p>
            )}
          </div>

          {renderEmergencyPanel()}
        </section>

        <section className="monitoring-grid">
          {renderIntersectionPanel()}
          {renderSignalStatus()}
        </section>

        <section className="bottom-grid">
          <div className="panel">
            <h3>Simulation Summary</h3>
            <p className="panel-description">
              Completed trips in the recorded runs
            </p>

            <div className="trip-comparison">
              <div>
                <span className="muted">Fixed-time</span>
                <h2>{baseline?.completed_trips ?? "—"}</h2>
                <div className="mini-track">
                  <div
                    className="mini-bar fixed"
                    style={{
                      width: baseline
                        ? `${(baseline.completed_trips / Math.max(
                            baseline.completed_trips,
                            adaptive?.completed_trips || 1
                          )) * 100}%`
                        : "0%",
                    }}
                  />
                </div>
              </div>

              <div>
                <span className="muted">Adaptive AI</span>
                <h2 className="green">{adaptive?.completed_trips ?? "—"}</h2>
                <div className="mini-track">
                  <div
                    className="mini-bar adaptive"
                    style={{
                      width: adaptive
                        ? `${(adaptive.completed_trips / Math.max(
                            baseline?.completed_trips || 1,
                            adaptive.completed_trips
                          )) * 100}%`
                        : "0%",
                    }}
                  />
                </div>
              </div>
            </div>
          </div>

          <SystemComponents status={status} />
        </section>

        <footer>
          SmartFlow AI · Academic simulation prototype · Results may vary between runs
        </footer>
      </>
    );
  }

  function renderEmergencyPanel() {
    return (
      <div className="panel emergency-panel">
        <div className="panel-header">
          <div>
            <h3>Emergency Vehicle Priority</h3>
            <p>Recorded simulation event</p>
          </div>
          <span className="ambulance-icon">✚</span>
        </div>

        {eventsLoading && <p className="empty-state compact">Loading recorded events...</p>}
        {eventsError && <p className="error-banner">{eventsError}</p>}
        {!eventsLoading && !eventsError && emergencyEvents.length === 0 && (
          <p className="empty-state compact">
            No emergency events are recorded in the current controller log.
          </p>
        )}
        {!eventsLoading && emergencyEvents.length > 0 && (
          <>
            <div className="event-status alert">
              <span className="event-dot" />
              <div>
                <strong>{emergencyEvents.length} recorded controller event{emergencyEvents.length === 1 ? "" : "s"}</strong>
                <p>Loaded from the latest simulation log</p>
              </div>
            </div>
            <div className="event-detail">
              <span>Latest event</span>
              <strong>{emergencyEvents[emergencyEvents.length - 1].event}</strong>
            </div>
            <div className="event-detail">
              <span>Direction</span>
              <strong>{emergencyEvents[emergencyEvents.length - 1].direction || "Not specified"}</strong>
            </div>
          </>
        )}
        <p className="event-note">
          Recorded simulation events only. This dashboard does not claim a live ambulance feed.
        </p>
      </div>
    );
  }

  function renderIntersectionPanel() {
    return (
      <div className="panel intersection-panel">
        <div className="panel-header">
          <div>
            <h3>Live Traffic Monitor</h3>
            <p>SUMO junction topology and controller state</p>
          </div>
          <span className={`live-badge ${running ? "active" : ""}`}>
            <span className="status-dot" /> {running ? "SIMULATION LIVE" : "STANDBY"}
          </span>
        </div>
        <div className="intersection-map" aria-label="3 by 3 junction simulation view">
          <div className="road road-horizontal" />
          <div className="road road-vertical" />
          <div className="junction-core">
            <span className="signal-dot signal-green" />
            <span className="signal-dot signal-yellow" />
            <span className="signal-dot signal-red" />
          </div>
          <span className="map-label north">NORTH</span>
          <span className="map-label east">EAST</span>
          <span className="map-label south">SOUTH</span>
          <span className="map-label west">WEST</span>
        </div>
        <div className="monitor-footer">
          <span><i className="legend-dot blue-dot" /> Adaptive controller</span>
          <span><i className="legend-dot green-dot" /> Junction online</span>
        </div>
      </div>
    );
  }

  function renderSignalStatus() {
    return (
      <div className="panel signal-panel">
        <div className="panel-header">
          <div>
            <h3>Traffic Signal Status</h3>
            <p>Phase configuration available to the controller</p>
          </div>
          <span className="panel-icon">⇄</span>
        </div>
        <div className="signal-phase">
          <div className="signal-lights"><span className="signal-light on-green" /><span className="signal-light" /><span className="signal-light" /></div>
          <div><strong>North–South</strong><p>Green phase · controller managed</p></div>
          <span className="phase-pill green-pill">GREEN</span>
        </div>
        <div className="signal-phase">
          <div className="signal-lights"><span className="signal-light" /><span className="signal-light on-yellow" /><span className="signal-light" /></div>
          <div><strong>East–West</strong><p>Transition phase · safe clearance</p></div>
          <span className="phase-pill yellow-pill">YELLOW</span>
        </div>
        <p className="event-note">Phase indicators show the configured signal model. Live phase telemetry is unavailable until the simulation is running.</p>
      </div>
    );
  }

  function SystemComponents({ status: backendStatus }) {
    return (
      <div className="panel system-panel">
        <h3>System Components</h3>
        <div className="component-row">
          <span>Traffic simulator</span>
          <strong>SUMO 1.28</strong>
        </div>
        <div className="component-row">
          <span>Adaptive controller</span>
          <strong>Python + TraCI</strong>
        </div>
        <div className="component-row">
          <span>Backend API</span>
          <strong>{backendStatus}</strong>
        </div>
        <div className="component-row">
          <span>Network</span>
          <strong>3 × 3 junction grid</strong>
        </div>
      </div>
    );
  }

  function renderTrafficOptimization() {
    return (
      <>
        <PageHeader
          eyebrow="SIGNAL CONTROL"
          title="Traffic Optimization"
          subtitle="Review fixed-time and demand-responsive adaptive signal performance."
        />

        <section className="metric-grid">
          <MetricCard
            title="Average Waiting Time"
            baseline={baseline?.average_waiting_time_seconds}
            adaptive={adaptive?.average_waiting_time_seconds}
            unit="sec"
            improvement={improvements?.average_waiting_time_seconds}
          />
          <MetricCard
            title="Average Trip Duration"
            baseline={baseline?.average_trip_duration_seconds}
            adaptive={adaptive?.average_trip_duration_seconds}
            unit="sec"
            improvement={improvements?.average_trip_duration_seconds}
          />
          <MetricCard
            title="Average Time Loss"
            baseline={baseline?.average_time_loss_seconds}
            adaptive={adaptive?.average_time_loss_seconds}
            unit="sec"
            improvement={improvements?.average_time_loss_seconds}
          />
        </section>

        <section className="panel page-section">
          <h3>Adaptive Signal Control</h3>
          <p>
            The Python controller uses vehicle demand to choose green durations,
            within its configured minimum and maximum green times.
          </p>

          <div className="event-detail">
            <span>Minimum green time</span>
            <strong>10 seconds</strong>
          </div>
          <div className="event-detail">
            <span>Maximum green time</span>
            <strong>35 seconds</strong>
          </div>
          <div className="event-detail">
            <span>Yellow transition</span>
            <strong>3 seconds</strong>
          </div>
          <div className="event-detail">
            <span>Emergency detection distance</span>
            <strong>150 metres</strong>
          </div>
        </section>

        <section className="panel page-section">
          <h3>Run a New Adaptive Simulation</h3>
          <p>
            Start the controller to create a new adaptive result file and refresh
            the recorded performance metrics when the run finishes.
          </p>

          <div className="simulation-actions">
            <button
              className="start-button"
              onClick={startSimulation}
              disabled={busy || running}
            >
              {busy && !running ? "Please wait..." : "▶ Start Simulation"}
            </button>
            <button
              className="stop-button"
              onClick={stopSimulation}
              disabled={busy || !running}
            >
              ■ Stop Simulation
            </button>
          </div>

          <p className="simulation-info">
            Current state: <strong>{simulation.state}</strong>
            {" · "}Backend: <strong>{status}</strong>
          </p>
          {message && <p className="success-message">{message}</p>}
          {error && <p className="error-banner">{error}</p>}
        </section>
      </>
    );
  }

  function renderEmergencyPriority() {
    return (
      <>
        <PageHeader
          eyebrow="EMERGENCY RESPONSE"
          title="Emergency Priority"
          subtitle="Emergency events recorded by the SUMO adaptive controller."
        />

        <section className="panel page-section">
          <div className="panel-header">
            <div>
              <h3>Controller Emergency Events</h3>
              <p>Events loaded from the latest controller log</p>
            </div>
            <span className="ambulance-icon">✚</span>
          </div>

          {eventsLoading && (
            <p className="empty-state">Loading emergency events...</p>
          )}

          {eventsError && (
            <p className="error-banner">{eventsError}</p>
          )}

          {!eventsLoading && !eventsError && emergencyEvents.length === 0 && (
            <p className="empty-state">
              No emergency events found in the current log.
              Run a simulation to generate new events.
            </p>
          )}

          {!eventsLoading && emergencyEvents.length > 0 && (
            <>
              <div className="event-detail">
                <span>Total recorded events</span>
                <strong>{emergencyEvents.length}</strong>
              </div>

              {emergencyEvents.map((event, index) => (
                <div
                  className="event-status"
                  key={`${event.event_type}-${index}`}
                >
                  <span className="event-dot" />
                  <div>
                    <strong>{event.event}</strong>
                    <p>
                      {event.direction
                        ? `Direction: ${event.direction}`
                        : "Direction not specified"}
                      {" · "}
                      {event.simulation_time_seconds != null
                        ? `Simulation time: ${event.simulation_time_seconds}s`
                        : "Simulation time not specified"}
                    </p>
                  </div>
                </div>
              ))}
            </>
          )}

          <button
            className="refresh-button"
            onClick={loadEmergencyEvents}
            disabled={eventsLoading}
          >
            ↻ Refresh emergency events
          </button>
        </section>

        <section className="panel page-section">
          <h3>Emergency Handling Workflow</h3>
          <ol className="workflow-list">
            <li>Detect the simulated ambulance on an incoming road.</li>
            <li>Check its direction and distance from the junction.</li>
            <li>
              Request emergency signal priority while maintaining safe transitions.
            </li>
            <li>Record when the ambulance clears the junction.</li>
          </ol>

          <p className="event-note">
            These are recorded simulation events, not detections from a physical
            ambulance or live webcam.
          </p>
        </section>
      </>
    );
  }

  function renderVehicleDetection() {
    return (
      <>
        <PageHeader
          eyebrow="COMPUTER VISION"
          title="Vehicle Detection"
          subtitle="Upload a traffic image to detect and count vehicles using YOLO."
        />

        <section className="panel page-section">
          <h3>Upload Traffic Image</h3>
          <p className="panel-description">
            Supported formats: JPG, PNG and WEBP. Maximum file size: 10 MB.
          </p>

          <label className="upload-area" htmlFor="traffic-image-input">
            <span className="upload-icon">📷</span>
            <strong>
              {selectedImage
                ? selectedImage.name
                : "Choose a traffic image"}
            </strong>
            <span>Click here to browse your files</span>

            <input
              id="traffic-image-input"
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={handleImageSelection}
            />
          </label>

          {imagePreview && (
            <div className="image-preview">
              <p className="panel-description">Selected image preview</p>
              <img src={imagePreview} alt="Selected traffic preview" />
            </div>
          )}

          <div className="simulation-actions">
            <button
              className="start-button"
              onClick={detectVehicles}
              disabled={!selectedImage || detecting}
            >
              {detecting ? "Detecting vehicles..." : "🔍 Detect Vehicles"}
            </button>

            <button
              className="stop-button"
              onClick={clearDetection}
              disabled={detecting}
            >
              Clear
            </button>
          </div>

          {detecting && (
            <p className="simulation-info">
              YOLO is processing your image. The first request may take longer
              while the model loads.
            </p>
          )}

          {detectionError && (
            <p className="error-banner">{detectionError}</p>
          )}
        </section>

        {detectionResult && (
          <>
            <section className="overview">
              <div>
                <span className="section-label">DETECTION RESULTS</span>
                <h2>Vehicle Count</h2>
                <p>File: {detectionResult.filename}</p>
              </div>
              <span className="result-tag">YOLO DETECTION</span>
            </section>

            <section className="metric-grid vehicle-count-grid">
              <div className="metric-card">
                <p className="metric-title">Total Vehicles</p>
                <h2 className="green">
                  {detectionResult.total_vehicles}
                </h2>
                <p className="muted">Detected in this image</p>
              </div>

              {VEHICLE_TYPES.map((vehicle) => (
                <div className="metric-card" key={vehicle.key}>
                  <p className="metric-title">
                    {vehicle.icon} {vehicle.label}
                  </p>
                  <h2>{detectionResult.counts?.[vehicle.key] ?? 0}</h2>
                </div>
              ))}
            </section>

            <section className="panel page-section">
              <h3>Annotated Detection Image</h3>
              <p className="panel-description">
                Bounding boxes show the vehicles identified by the model.
              </p>

              <div className="detected-image">
                <img
                  src={`data:image/jpeg;base64,${detectionResult.annotated_image}`}
                  alt="Traffic image annotated with vehicle detections"
                />
              </div>
            </section>

            <p className="event-note">
              Counts are model predictions, not guaranteed ground-truth counts.
              Small or overlapping vehicles may be missed, particularly in
              crowded traffic scenes.
            </p>
          </>
        )}
      </>
    );
  }

  function renderPerformanceReports() {
    return (
      <>
        <PageHeader
          eyebrow="RESULT ANALYSIS"
          title="Performance Reports"
          subtitle="Compare the recorded fixed-time and adaptive simulation results."
        />

        <section className="panel page-section">
          <h3>Performance Comparison</h3>

          {metrics ? (
            <div className="table-wrapper">
              <table className="report-table">
                <thead>
                  <tr>
                    <th>Metric</th>
                    <th>Fixed-time</th>
                    <th>Adaptive AI</th>
                    <th>Improvement</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Completed trips</td>
                    <td>{baseline?.completed_trips ?? "—"}</td>
                    <td>{adaptive?.completed_trips ?? "—"}</td>
                    <td>—</td>
                  </tr>
                  <tr>
                    <td>Average waiting time</td>
                    <td>
                      {baseline?.average_waiting_time_seconds ?? "—"} s
                    </td>
                    <td>
                      {adaptive?.average_waiting_time_seconds ?? "—"} s
                    </td>
                    <td>
                      {improvements?.average_waiting_time_seconds ?? "—"}%
                    </td>
                  </tr>
                  <tr>
                    <td>Average trip duration</td>
                    <td>
                      {baseline?.average_trip_duration_seconds ?? "—"} s
                    </td>
                    <td>
                      {adaptive?.average_trip_duration_seconds ?? "—"} s
                    </td>
                    <td>
                      {improvements?.average_trip_duration_seconds ?? "—"}%
                    </td>
                  </tr>
                  <tr>
                    <td>Average time loss</td>
                    <td>
                      {baseline?.average_time_loss_seconds ?? "—"} s
                    </td>
                    <td>
                      {adaptive?.average_time_loss_seconds ?? "—"} s
                    </td>
                    <td>
                      {improvements?.average_time_loss_seconds ?? "—"}%
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          ) : (
            <p className="empty-state">Waiting for backend metrics…</p>
          )}

          <p className="event-note">
            These are recorded simulation results. A fair experimental comparison
            should use the same traffic demand, simulation duration, and random
            seeds across repeated runs.
          </p>
        </section>

        <section className="panel page-section">
          <h3>Simulation Status</h3>
          <div className="component-row">
            <span>Backend</span>
            <strong>{status}</strong>
          </div>
          <div className="component-row">
            <span>Simulation state</span>
            <strong>{simulation.state}</strong>
          </div>
          <div className="component-row">
            <span>Elapsed time</span>
            <strong>{elapsed} seconds</strong>
          </div>
          <div className="component-row">
            <span>Exit code</span>
            <strong>{simulation.exit_code ?? "—"}</strong>
          </div>

          <button
            className="refresh-button"
            onClick={() => {
              loadMetrics();
              loadSimulationStatus();
            }}
          >
            ↻ Refresh report data
          </button>
        </section>
      </>
    );
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">S</div>
          <div>
            <h2>SmartFlow AI</h2>
            <span>INTELLIGENT MOBILITY</span>
          </div>
        </div>

        <p className="nav-heading">WORKSPACE</p>

        <nav className="sidebar-nav" aria-label="Main navigation">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.name}
              type="button"
              className={`nav-item ${
                activePage === item.name ? "active" : ""
              }`}
              aria-current={activePage === item.name ? "page" : undefined}
              disabled={!item.available}
              onClick={() => {
                setActivePage(item.page || item.name);
                setError("");
                setMessage("");
              }}
            >
              <span className="nav-icon">{item.icon}</span>
              <span>{item.name}</span>
              {!item.available && <span className="nav-unavailable">Soon</span>}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div><span className={`status-dot ${status === "Backend connected" ? "online" : ""}`} /><span>{status}</span></div>
          <p>FastAPI · SUMO controller</p>
        </div>
      </aside>

      <main className="main">
        <div className="topbar-status">
          <span><i className={`status-dot ${status === "Backend connected" ? "online" : ""}`} /> {status}</span>
          <span><i className={`status-dot ${running ? "online" : "idle"}`} /> {running ? "Simulation running" : "Simulation idle"}</span>
          <span className="profile-icon" aria-label="SmartFlow operator">SF</span>
        </div>
        {activePage === "Dashboard" && renderDashboard()}
        {activePage === "Traffic Optimization" && renderTrafficOptimization()}
        {activePage === "Emergency Priority" && renderEmergencyPriority()}
        {activePage === "Vehicle Detection" && renderVehicleDetection()}
        {activePage === "Performance Reports" && renderPerformanceReports()}
      </main>
    </div>
  );
}

function PageHeader({ eyebrow, title, subtitle }) {
  return (
    <header className="topbar page-header">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="subtitle">{subtitle}</p>
      </div>
    </header>
  );
}

export default App;
