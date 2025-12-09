from flask import Flask, request, jsonify
import time
import numpy as np
import threading
import RPi.GPIO as GPIO

app = Flask(__name__)

# -------------------------------
# GPIO SETUP (ChatGPT)
# -------------------------------
LED_PIN = 17

GPIO.setmode(GPIO.BCM)
GPIO.setup(LED_PIN, GPIO.OUT)
GPIO.output(LED_PIN, GPIO.LOW)

def led_alert():
    GPIO.output(LED_PIN, GPIO.HIGH)
    time.sleep(5)
    GPIO.output(LED_PIN, GPIO.LOW)

# -------------------------------
# HEARTBEAT PROCESSING VARIABLES (ChatGPT)
# -------------------------------
timestamps = []

MAX_WINDOW_SECONDS = 20
MIN_PEAK_DISTANCE_MS = 250
IRREGULARITY_THRESHOLD_MS = 120


@app.route("/api/tap", methods=["POST"])
def receive_tap():
    global timestamps

    data = request.get_json()
    if "timestamp" not in data:
        return jsonify({"error": "timestamp missing"}), 400

    ts = float(data["timestamp"])
    timestamps.append(ts)

    now = time.time() * 1000
    timestamps = [t for t in timestamps if now - t <= MAX_WINDOW_SECONDS * 1000]

    result = process_peaks(timestamps)

    # ----------------------------------------------------------
    # If irregular heartbeat detected → trigger LED (ChatGPT)
    # ----------------------------------------------------------
    if result.get("irregularities"):
        threading.Thread(target=led_alert, daemon=True).start()

    return jsonify(result)


# used ChatGPT
def process_peaks(timestamps):
    if len(timestamps) < 3:
        return {"status": "waiting", "message": "Not enough data"}

    t = np.array(timestamps, dtype=float)

    # DIFFERENTIATION (kept for ECG compatibility)
    dt = np.diff(t)

    # PEAK FILTERING
    filtered = [t[0]]
    for i in range(1, len(t)):
        if t[i] - filtered[-1] > MIN_PEAK_DISTANCE_MS:
            filtered.append(t[i])

    filtered = np.array(filtered, dtype=float)

    if len(filtered) < 2:
        return {"status": "insufficient_peaks"}

    # RR intervals
    intervals = np.diff(filtered)

    avg_interval = np.mean(intervals)
    bpm = 60000.0 / avg_interval

    variability = float(np.std(intervals))

    # IRREGULARITY DETECTION
    irregularities = []
    for i in range(1, len(intervals)):
        diff = abs(intervals[i] - intervals[i - 1])
        if diff > IRREGULARITY_THRESHOLD_MS:
            if intervals[i] > intervals[i - 1]:
                irregularities.append("skipped beat")
            else:
                irregularities.append("premature beat")

    return {
        "status": "ok",
        "beats_detected": len(filtered),
        "intervals_ms": intervals.tolist(),
        "bpm": round(bpm),
        "variability_ms": round(variability, 2),
        "irregularities": list(set(irregularities)) if irregularities else []
    }


if __name__ == "__main__":
    try:
        app.run(host="0.0.0.0", port=5000)
    finally:
        GPIO.cleanup()
