#!/bin/bash
# Script to run the VoIP benchmark locally

set -e

# Default values
INPUT=""
OUTPUT="results/output.wav"
CODEC="opus"
BITRATE=64000
PACKET_LOSS=0.0
JITTER=0.0
LATENCY=0.0
ADAPTIVE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
  key="$1"
  case $key in
    --input)
      INPUT="$2"
      shift
      shift
      ;;
    --output)
      OUTPUT="$2"
      shift
      shift
      ;;
    --codec)
      CODEC="$2"
      shift
      shift
      ;;
    --bitrate)
      BITRATE="$2"
      shift
      shift
      ;;
    --packet-loss)
      PACKET_LOSS="$2"
      shift
      shift
      ;;
    --jitter)
      JITTER="$2"
      shift
      shift
      ;;
    --latency)
      LATENCY="$2"
      shift
      shift
      ;;
    --adaptive)
      ADAPTIVE=true
      shift
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# Ensure output directory exists
mkdir -p $(dirname "$OUTPUT")

# Build command
CMD="python -m voip_benchmark.examples.simple_benchmark"

if [ ! -z "$INPUT" ]; then
  CMD="$CMD --input $INPUT"
fi

CMD="$CMD --output $OUTPUT"
CMD="$CMD --codec $CODEC"
CMD="$CMD --bitrate $BITRATE"
CMD="$CMD --packet-loss $PACKET_LOSS"
CMD="$CMD --jitter $JITTER"
CMD="$CMD --latency $LATENCY"

if [ "$ADAPTIVE" = true ]; then
  CMD="$CMD --adaptive"
fi

# Print command
echo "Running: $CMD"

# Execute command
eval $CMD

echo "Benchmark completed. Output saved to $OUTPUT" 