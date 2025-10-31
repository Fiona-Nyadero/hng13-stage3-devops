import os
import sys
import time
import json
import requests
from collections import deque
import io

# --- CONFIGURATION FROM ENVIRONMENT ---
LOG_FILE_PATH = os.environ.get("LOG_FILE_PATH", "/app/logs/access.log")
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")
ERROR_RATE_THRESHOLD = float(os.environ.get("ERROR_RATE_THRESHOLD", 2)) / 100.0
WINDOW_SIZE = int(os.environ.get("WINDOW_SIZE", 200))
COOLDOWN_SEC = int(os.environ.get("ALERT_COOLDOWN_SEC", 300))
INITIAL_POOL = os.environ.get("ACTIVE_POOL", "blue").lower()

# --- GLOBAL STATE ---
log_queue = deque(maxlen=WINDOW_SIZE)
current_pool = INITIAL_POOL
last_alert_time = 0.0

def post_to_slack(title, message, color="#36a64f"):
    """Posts a rich message to the configured Slack webhook."""
    if not SLACK_WEBHOOK_URL:
        print(f"[SLACK-ALERT] {title}: {message}")
        return

    payload = {
        "attachments": [{
            "color": color,
            "title": title,
            "text": message,
            "ts": int(time.time())
        }]
    }
    try:
        requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=5)
    except Exception as e:
        print(f"Error posting to Slack: {e}")

def check_cooldown():
    """Returns True if cooldown is active, False otherwise."""
    global last_alert_time
    if (time.time() - last_alert_time) < COOLDOWN_SEC:
        return True
    last_alert_time = time.time()
    return False

def analyze_error_rate():
    """Calculates 5xx error rate and alerts if threshold is breached."""
    if len(log_queue) < WINDOW_SIZE:
        return

    error_count = sum(1 for entry in log_queue if 500 <= int(entry.get('upstream_status', '0')) < 600)
    error_rate = error_count / WINDOW_SIZE

    if error_rate > ERROR_RATE_THRESHOLD:
        if check_cooldown():
            print("Error rate alert suppressed due to cooldown.")
            return

        pool_name = log_queue[-1].get('pool', 'unknown').upper()

        post_to_slack(
            title=":fire: HIGH ERROR RATE DETECTED",
            message=f"**Error Rate Threshold Breach**\n"
                    f"Pool: *{pool_name}* (Current)\n"
                    f"Rate: **{error_rate:.2%}** over last {WINDOW_SIZE} requests.\n"
                    f"Upstream errors detected. **Action Required: Inspect {pool_name} logs.**",
            color="#ff0000"
        )

def check_failover(log_entry):
    """Detects a change in the current serving pool."""
    global current_pool, last_alert_time
    new_pool = log_entry.get('pool')

    if new_pool and new_pool != current_pool:
        if new_pool in ['blue', 'green']:
            if (time.time() - last_alert_time) < 10:
                return

            old_pool_upper = current_pool.upper()
            new_pool_upper = new_pool.upper()

            post_to_slack(
                title=f":warning: POOL FAILOVER DETECTED: {old_pool_upper} -> {new_pool_upper}",
                message=f"The active serving pool has switched from **{old_pool_upper}** to **{new_pool_upper}**.\n"
                        f"This suggests failure in the primary pool, or a manual toggle.",
                color="#FFA500"
            )

            current_pool = new_pool
            last_alert_time = time.time()

def process_log_line(line):
    """Parses each log line and updates monitoring state."""
    try:
        log_entry = json.loads(line.strip())
    except json.JSONDecodeError:
        return
    log_queue.append(log_entry)
    analyze_error_rate()
    check_failover(log_entry)

def tail_logs():
    """Tails the log file, robustly handling seek and file state."""
    print(f"Tailing log file: {LOG_FILE_PATH}")

    while True:
        try:
            with open(LOG_FILE_PATH, 'r') as f:
                try:
                    f.seek(0, io.SEEK_END)
                except io.UnsupportedOperation:
                    print("Note: Log stream is unseekable, starting read from current position.", file=sys.stderr)
                    pass

                while True:
                    line = f.readline()
                    if not line:
                        time.sleep(0.1)
                        continue

                    process_log_line(line)

        except FileNotFoundError:
            print(f"Log file not found at {LOG_FILE_PATH}. Retrying in 5 seconds.")
            time.sleep(5)
        except Exception as e:
            print(f"Fatal file error: {e}. Retrying in 10 seconds.")
            time.sleep(10)

if __name__ == "__main__":
    tail_logs()
