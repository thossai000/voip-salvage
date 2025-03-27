#!/bin/bash
# rtp_benchmark.sh - benchmarking script for RTP audio transmission
# This script automates the process of sending RTP packets between containers and measuring network traffic

# Exit on any error
set -e

# Get script locations
SCRIPT_DIR="$(dirname "$(realpath "$0")")"
REPO_ROOT="$(realpath "$SCRIPT_DIR/../..")"

# Configuration
RESULTS_DIR="/tmp/jitsi-results-$(date +%Y%m%d%H%M%S)"
WAV_INPUT_FILE="${REPO_ROOT}/audio/voip_ready.wav"
WAV_OUTPUT_FILE="${RESULTS_DIR}/received_audio.wav"
CAPTURE_FILE="${RESULTS_DIR}/rtp_capture.pcapng"
TEST_DURATION=30  # in seconds - should match roughly the duration of WAV file
RTP_SEND_PORT=12345  # UDP port for RTP transmission

# Print banner
echo "===================================================="
echo "RTP Audio Benchmark Test"
echo "===================================================="

# Create results directory
mkdir -p ${RESULTS_DIR}
echo "[+] Created results directory: ${RESULTS_DIR}"
# Make sure results directory has proper permissions
chmod 777 ${RESULTS_DIR}
echo "[+] Set permissions on results directory: ${RESULTS_DIR}"

# Step 1: Check dependencies
echo -e "\n[1/6] Checking dependencies..."
command -v python3 >/dev/null 2>&1 || { echo "Error: python3 is required but not installed. Aborting."; exit 1; }
command -v tshark >/dev/null 2>&1 || { echo "Error: tshark is required but not installed. Aborting."; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "Error: docker is required but not installed. Aborting."; exit 1; }

# Check if our RTP scripts are executable
RTP_SEND_SCRIPT="${SCRIPT_DIR}/rtp_send.py"
RTP_RECEIVE_SCRIPT="${SCRIPT_DIR}/rtp_receive.py"
if [ ! -f "$RTP_SEND_SCRIPT" ] || [ ! -f "$RTP_RECEIVE_SCRIPT" ]; then
    echo "Error: RTP scripts not found at ${SCRIPT_DIR}. Aborting."
    exit 1
fi

# Make scripts executable
chmod +x "$RTP_SEND_SCRIPT"
chmod +x "$RTP_RECEIVE_SCRIPT"

echo "✓ All dependencies are installed"

# Step 2: Check WAV file
echo -e "\n[2/6] Checking WAV file..."
if [ ! -f "$WAV_INPUT_FILE" ]; then
    echo "Error: Input WAV file not found: $WAV_INPUT_FILE"
    echo "Please create it first with: ffmpeg -i ${REPO_ROOT}/audio/test_audio_30s.wav -ar 8000 -ac 1 -acodec pcm_s16le $WAV_INPUT_FILE"
    exit 1
fi

# Get WAV file info
echo "✓ Using WAV file: $WAV_INPUT_FILE"
WAV_SIZE=$(stat -c%s "$WAV_INPUT_FILE")
echo "✓ WAV file size: $WAV_SIZE bytes"

# Step 3: Verify Docker environment
echo -e "\n[3/6] Verifying Docker environment..."
RUNNING_CONTAINERS=$(docker ps --format '{{.Names}}' | grep -E 'jvb|web' | wc -l)
if [ "$RUNNING_CONTAINERS" -lt 2 ]; then
    echo "Warning: Not all Jitsi Meet containers appear to be running."
    echo "Expected at least containers with 'web' and 'jvb' in their names"
    echo "Running containers:"
    docker ps --format 'table {{.Names}}\t{{.Status}}' | grep -E 'jvb|web'
    
    read -p "Do you want to continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborting test."
        exit 1
    fi
else
    echo "✓ Jitsi Meet containers are running"
fi

# Find JVB container for testing - updated with better pattern matching
JVB_CONTAINER=$(docker ps --format '{{.Names}}' | grep -E 'jvb|jvb-1|jitsi.*jvb' | head -1)
if [ -z "$JVB_CONTAINER" ]; then
    echo "❌ Error: Could not find JVB container"
    echo "Available containers:"
    docker ps --format 'table {{.Names}}\t{{.Image}}'
    exit 1
fi

# Get container IP
JVB_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$JVB_CONTAINER")
echo "✓ Using JVB container: $JVB_CONTAINER (IP: $JVB_IP)"

# Get host IP visible to containers (for receiver to listen on)
HOST_IP=$(ip route get 1 | awk '{print $(NF-2);exit}')
echo "✓ Host IP address for container communication: $HOST_IP"

# Step 4: Start packet capture
echo -e "\n[4/6] Starting packet capture..."
echo "Capturing RTP traffic to: $CAPTURE_FILE"
# Expanded capture filter to ensure we catch the right traffic
tshark -i any -f "udp port $RTP_SEND_PORT or udp portrange 10000-20000" -w "$CAPTURE_FILE" -a duration:$((TEST_DURATION+10)) &
TSHARK_PID=$!
echo "✓ Packet capture started (PID: $TSHARK_PID)"

# Give tshark time to initialize
sleep 2

# Step 5: Run the RTP benchmark test
echo -e "\n[5/6] Running RTP benchmark test..."

# Verify output directory exists with proper permissions
echo "Verifying output directory permissions..."
ls -la $(dirname "$WAV_OUTPUT_FILE")

# Start RTP receiver in the background with debug mode enabled
echo "Starting RTP receiver..."
echo "Command: python3 ${RTP_RECEIVE_SCRIPT} --port $RTP_SEND_PORT --output $WAV_OUTPUT_FILE --duration $((TEST_DURATION+5)) --debug"
python3 "${RTP_RECEIVE_SCRIPT}" --port $RTP_SEND_PORT --output $WAV_OUTPUT_FILE --duration $((TEST_DURATION+5)) --debug &
RECEIVER_PID=$!
echo "✓ RTP receiver started (PID: $RECEIVER_PID)"

# Give receiver time to initialize
sleep 2

# Start RTP sender with explicit debugging
echo "Starting RTP sender..."
echo "Command: python3 ${RTP_SEND_SCRIPT} $WAV_INPUT_FILE --dest-ip $HOST_IP --dest-port $RTP_SEND_PORT --debug"
python3 "${RTP_SEND_SCRIPT}" $WAV_INPUT_FILE --dest-ip $HOST_IP --dest-port $RTP_SEND_PORT --debug

# Wait for receiver to complete
echo "Waiting for RTP receiver to complete..."
wait $RECEIVER_PID || true
echo "RTP receiver process completed."

# Check if the output file was created
if [ -f "$WAV_OUTPUT_FILE" ]; then
    WAV_OUTPUT_SIZE=$(stat -c%s "$WAV_OUTPUT_FILE" 2>/dev/null || echo "0")
    echo "Received WAV file info:"
    echo "  Path: $WAV_OUTPUT_FILE"
    echo "  Size: $WAV_OUTPUT_SIZE bytes"
    echo "  File exists: Yes"
    ls -la "$WAV_OUTPUT_FILE"
else
    echo "❌ Output WAV file not found at: $WAV_OUTPUT_FILE"
fi

# Wait for packet capture to complete
echo "Waiting for packet capture to complete..."
wait $TSHARK_PID || true
echo "✓ Packet capture completed"

# Step 6: Analyze results
echo -e "\n[6/6] Analyzing results..."

# Check if the capture file exists and has content
if [ ! -s "$CAPTURE_FILE" ]; then
  echo "❌ Error: No packet capture data found"
  echo "Please check your network configuration and try again"
  exit 1
fi

# Get basic statistics from the capture file
echo "Generating traffic summary..."
capinfos -c -e -i -M -T "$CAPTURE_FILE" > "${RESULTS_DIR}/traffic_summary.txt"

# Extract   RTP traffic statistics
echo "Extracting RTP traffic statistics..."
tshark -r "$CAPTURE_FILE" -q -z io,stat,1,"frame.time_relative and udp" > "${RESULTS_DIR}/rtp_stats.txt"
tshark -r "$CAPTURE_FILE" -qz rtp,streams > "${RESULTS_DIR}/rtp_streams.txt"

# Generate a full packet analysis
echo "Performing   packet analysis..."
tshark -r "$CAPTURE_FILE" -T fields -e frame.number -e frame.time_relative -e ip.src -e ip.dst -e udp.srcport -e udp.dstport -e frame.len -Y "udp" > "${RESULTS_DIR}/rtp_packets.csv"

# Calculate total RTP bytes transferred
echo "Calculating total bytes transmitted..."
TOTAL_BYTES=$(tshark -r "$CAPTURE_FILE" -T fields -e frame.len -Y "udp port $RTP_SEND_PORT" | awk '{sum+=$1} END {print sum}')
if [ -z "$TOTAL_BYTES" ] || [ "$TOTAL_BYTES" = "0" ]; then
    # Try alternate calculation method
    TOTAL_BYTES=$(cat "${RESULTS_DIR}/rtp_packets.csv" | awk '{sum+=$7} END {print sum}')
    if [ -z "$TOTAL_BYTES" ] || [ "$TOTAL_BYTES" = "0" ]; then
        TOTAL_BYTES=0
        echo "⚠️ Failed to calculate total bytes transmitted"
    else
        echo "Calculated total bytes using packet sizes: $TOTAL_BYTES"
    fi
else
    echo "Calculated total bytes using tshark: $TOTAL_BYTES"
fi

# Count RTP packets
RTP_PACKETS=$(tshark -r "$CAPTURE_FILE" -Y "udp" | wc -l)

# Check received WAV file
if [ -f "$WAV_OUTPUT_FILE" ]; then
    RECEIVED_WAV_SIZE=$(stat -c%s "$WAV_OUTPUT_FILE")
    echo "Received WAV file size: $RECEIVED_WAV_SIZE bytes"
else
    RECEIVED_WAV_SIZE=0
    echo "⚠️ No received WAV file found"
fi

# Calculate transmission ratio
if [ "$WAV_SIZE" -gt 0 ] && [ "$TOTAL_BYTES" -gt 0 ]; then
    RATIO_PERCENT=$(echo "scale=2; ($TOTAL_BYTES/$WAV_SIZE)*100" | bc)
    echo "Transmission ratio: ${RATIO_PERCENT}% of WAV file size"
else
    RATIO_PERCENT="0.00"
    echo "⚠️ No meaningful transmission ratio calculated"
fi

# Calculate audio quality if we have both files
if [ -f "$WAV_OUTPUT_FILE" ] && [ "$RECEIVED_WAV_SIZE" -gt 0 ]; then
    echo "Audio transfer success: Yes"
    AUDIO_QUALITY="Not measured"  # Could implement PESQ or similar in the future
else
    echo "Audio transfer success: No"
    AUDIO_QUALITY="N/A"
fi

# Save results to file
echo "Total RTP bytes transmitted: $TOTAL_BYTES" > "${RESULTS_DIR}/benchmark_results.txt"
echo "Total RTP packets: $RTP_PACKETS" >> "${RESULTS_DIR}/benchmark_results.txt"
echo "WAV file size: $WAV_SIZE bytes" >> "${RESULTS_DIR}/benchmark_results.txt"
echo "Received WAV file size: $RECEIVED_WAV_SIZE bytes" >> "${RESULTS_DIR}/benchmark_results.txt"
echo "Transmission ratio: ${RATIO_PERCENT}%" >> "${RESULTS_DIR}/benchmark_results.txt"
echo "Audio transfer success: $([ -f "$WAV_OUTPUT_FILE" ] && echo "Yes" || echo "No")" >> "${RESULTS_DIR}/benchmark_results.txt"
echo "Audio quality: $AUDIO_QUALITY" >> "${RESULTS_DIR}/benchmark_results.txt"

# Print summary
echo -e "\n===== Benchmark Results ====="
echo "RTP packets captured: $RTP_PACKETS"
echo "Total RTP bytes transmitted: $TOTAL_BYTES bytes"
echo "Original WAV file size: $WAV_SIZE bytes"
echo "Received WAV file size: $RECEIVED_WAV_SIZE bytes"
echo "Transmission ratio: ${RATIO_PERCENT}% of WAV file size"
echo "Audio transfer success: $([ -f "$WAV_OUTPUT_FILE" ] && echo "Yes" || echo "No")"
echo "============================"

# Create report
echo -e "\n===================================================="
echo "RTP Benchmark Test Report"
echo "===================================================="
echo "Test completed at: $(date)"
echo "WAV input file: $WAV_INPUT_FILE ($WAV_SIZE bytes)"
echo "WAV output file: $WAV_OUTPUT_FILE ($([ -f "$WAV_OUTPUT_FILE" ] && echo "$RECEIVED_WAV_SIZE" || echo "0") bytes)"
echo "Capture file: $CAPTURE_FILE"
echo "RTP packets captured: $RTP_PACKETS"
echo "Total RTP bytes transmitted: $TOTAL_BYTES bytes"
echo "Transmission ratio: ${RATIO_PERCENT}% of WAV file size"
echo "Audio transfer success: $([ -f "$WAV_OUTPUT_FILE" ] && echo "Yes" || echo "No")"
echo "  results available in: $RESULTS_DIR"
echo "===================================================="

# List the generated report files
echo ""
echo "Generated report files:"
ls -la "${RESULTS_DIR}" 