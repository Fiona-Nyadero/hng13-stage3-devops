import os
import time
import json
import requests
from collections import deque

# --- CONFIGURATION FROM ENVIRONMENT ---
LOG_FILE_PATH = "/app/logs/access.log"
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")
ERROR_RATE_THRESHOLD = float(os.environ.get("ERROR_RATE_THRESHOLD", 2)) / 100.0 # Convert % to decimal
WINDOW_SIZE = int(os.environ.get("WINDOW_SIZE", 200))
COOLDOWN_SEC = int(os.environ.get("ALERT_COOLDOWN_SEC", 300))
INITIAL_POOL = os.environ.get("ACTIVE_POOL", "blue")

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
        requests.post(SLACK_WEBHOOK_URL, json=payload)
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
            print(f"Error rate alert suppressed due to cooldown.")
            return

        pool_name = log_queue[-1].get('pool', 'unknown').upper()

        post_to_slack(
            title=":fire: HIGH ERROR RATE DETECTED",
            message=f"**Error Rate Threshold Breach**\n"
                    f"Pool: *{pool_name}* (Current)\n"
                    f"Rate: **{error_rate:.2%}** over last {WINDOW_SIZE} requests.\n"
                    f"Upstream errors detected. **Action Required: Inspect {pool_name} logs.**",
            color="#ff0000" # Red
        )
    # Optional: Alert on recovery, but the task focuses on breach
    # else: send recovery alert if error_rate was previously high

def check_failover(log_entry):
    """Detects a change in the current serving pool."""
    global current_pool, last_alert_time
    new_pool = log_entry.get('pool')

    if new_pool and new_pool != current_pool:
        # Check if the new pool is 'blue' or 'green' (and not 'none' or other states)
        if new_pool in ['blue', 'green']:
            # Alert only on the *first* failover event after the switch
            if (time.time() - last_alert_time) < 10: # A very short grace period for immediate switch, then skip cooldown
                return

            old_pool_upper = current_pool.upper()
            new_pool_upper = new_pool.upper()

            # Post Alert
            post_to_slack(
                title=f":warning: POOL FAILOVER DETECTED: {old_pool_upper} -> {new_pool_upper}",
                message=f"The active serving pool has switched from **{old_pool_upper}** to **{new_pool_upper}**.\n"
                        f"This suggests failure in the primary pool, or a manual toggle.",
                color="#FFA500" # Orange
            )

            # Update state and set cooldown for failover alerts
            current_pool = new_pool
            last_alert_time = time.time() # Start cooldown after failover alert

def tail_logs():
    """Tails the log file, robustly handling seek and file state."""
    print(f"Tailing log file: {LOG_FILE_PATH}")

    while True:
        try:
            # Open the file in read mode ('r')
            with open(LOG_FILE_PATH, 'r') as f:

                # Try to seek to the end for clean startup, but ignore failure (the fix!)
                try:
                    f.seek(0, io.SEEK_END)
                except io.UnsupportedOperation:
                    print("Note: Log stream is unseekable, starting read from current position.", file=sys.stderr)
                    # If unseekable, we just start reading from wherever the pointer is (usually the beginning)
                    pass

                # Continuous read loop
                while True:
                    line = f.readline()
                    if not line:
                        time.sleep(0.1) # Wait for new line
                        continue

                    process_log_line(line)

        except FileNotFoundError:
            # If Nginx hasn't created the file yet, wait and retry
            print(f"Log file not found at {LOG_FILE_PATH}. Retrying in 5 seconds.")
            time.sleep(5)
        except Exception as e:
            # Catch unexpected errors during file operation (like disk errors)
            print(f"Fatal file error: {e}. Retrying in 10 seconds.")
            time.sleep(10)

if __name__ == "__main__":
    tail_logs()