🚀 HNG Internship Stage 3: Observability & Alerts for Blue/GreenThis repository extends the Stage 2 Blue/Green deployment by adding a full observability and alerting layer using Nginx custom logging and a lightweight Python log-watcher sidecar.The solution detects Failover Events and monitors the Upstream 5xx Error Rate, sending real-time, rate-limited alerts to Slack.🛠️ Architecture OverviewThe system consists of five services orchestrated by Docker Compose:app_blue / app_green: Node.js services (unchanged from Stage 2).nginx: Routes traffic, executes failover logic, and writes structured logs to a shared volume.alert_watcher: A Python service that tails the Nginx logs, processes a rolling window of requests, and sends formatted alerts to a Slack webhook.The configuration is entirely driven by environment variables (.env) for flexibility.⚙️ Repository ContentsFile/DirectoryPurposedocker-compose.ymlOrchestrates all 5 services, defines the nginx_logs shared volume, and passes all required environment variables..env.exampleTemplate for required Slack webhook, thresholds, and cooldown configuration.nginx/nginx.conf.templateCustom Nginx Log Format (json_log) defined to capture pool, release, upstream_status, and latency metrics.watcher/watcher.pyThe Python script containing the core logic for tailing logs, maintaining the rolling error window, and posting alerts.watcher/requirements.txtLists Python dependencies (requests).runbook.mdRequired deliverable detailing operator actions for each generated alert type.💻 Setup InstructionsPrerequisitesDocker & Docker Compose: Must be installed and running.Slack Webhook: You must obtain an Incoming Webhook URL from your Slack workspace.1. Configure the .env fileCopy the template and replace the placeholder values.Bashcp .env.example .env
Set the variables in your new .env file:Bash# --- Application Images (As provided in Stage 2/3) ---
BLUE_IMAGE="yimikaade/wonderful:devops-stage-two"
GREEN_IMAGE="yimikaade/wonderful:devops-stage-two"

# ... existing RELEASE_ID and PORT variables ...

# --- Stage 3 Alerting Configuration ---

SLACK_WEBHOOK_URL="<YOUR_SLACK_WEBHOOK_URL_HERE>"
ACTIVE_POOL="blue"
ERROR_RATE_THRESHOLD="2" # 2% error threshold for 5xx alerts
WINDOW_SIZE="200" # Sliding window size for error calculation
ALERT_COOLDOWN_SEC="60" # Cooldown in seconds (e.g., 60s for testing) 2. Build and Start ServicesThe Python watcher service must be built first.Bash# Build the watcher image and start all services in detached mode
docker-compose up --build -d
🧪 Verification and Chaos TestingUse the following steps to verify Nginx logging and trigger the required alerts.1. Verify Baseline & Nginx LoggingAccess the main endpoint and inspect the Nginx container logs to confirm structured output.Bash# 1. Access the endpoint (generates a log line)
curl -s http://localhost:8080/version

# 2. View the Nginx logs (should show structured JSON output)

docker logs nginx_proxy 2>&1 | grep json
You should see output similar to the required format: {"time": "...", "pool": "blue", "release": "...", "upstream_status": "200", ...}2. Verify Failover Alert (Blue → Green)This simulates the failure of the primary pool, which should trigger an immediate Slack alert and switch traffic to Green.StepAction (Command)Expected Alert in SlackA. Induce Chaos on Bluecurl -s -X POST http://localhost:8081/chaos/start?mode=errorNone yetB. Trigger Failovercurl -s http://localhost:8080/version:warning: POOL FAILOVER DETECTED: BLUE -> GREENC. Verify Trafficcurl -s http://localhost:8080/version | grep X-App-PoolOutput: X-App-Pool: green3. Verify High Error Rate AlertThis test is performed while Green is the active server pool (after the failover in Step 2). We simulate high errors in the current active pool.StepAction (Command)Expected Alert in SlackA. Induce Chaos on Greencurl -s -X POST http://localhost:8082/chaos/start?mode=errorNone yetB. Generate TrafficRun a loop to generate more than 200 requests (to exceed the WINDOW_SIZE). for i in {1..250}; do curl -s http://localhost:8080/version; done:fire: HIGH ERROR RATE DETECTED (Triggered after 5xx rate exceeds 2%)4. CleanupBashdocker-compose down
