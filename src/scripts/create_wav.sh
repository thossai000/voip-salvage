#!/bin/bash
# create_wav.sh - Generate a deterministic WAV file with configurable parameters

# Default values
DURATION=30
FREQUENCY=440
CHANNELS=1
OUTPUT_FILE="test_audio.wav"
SAMPLE_RATE=48000

# Function to display help
show_help() {
    echo "Usage: $0 [options]"
    echo "Generate a deterministic WAV file with configurable parameters."
    echo ""
    echo "Options:"
    echo "  -d, --duration SEC       Duration in seconds (default: $DURATION)"
    echo "  -f, --frequency HZ       Frequency in Hz (default: $FREQUENCY)"
    echo "  -c, --channels NUM       Number of channels (default: $CHANNELS)"
    echo "  -r, --rate RATE          Sample rate in Hz (default: $SAMPLE_RATE)"
    echo "  -o, --output FILE        Output file (default: $OUTPUT_FILE)"
    echo "  -h, --help               Show this help"
    echo ""
    echo "Example:"
    echo "  $0 --duration 10 --frequency 1000 --channels 2 --output test.wav"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        -d|--duration)
            DURATION="$2"
            shift
            shift
            ;;
        -f|--frequency)
            FREQUENCY="$2"
            shift
            shift
            ;;
        -c|--channels)
            CHANNELS="$2"
            shift
            shift
            ;;
        -r|--rate)
            SAMPLE_RATE="$2"
            shift
            shift
            ;;
        -o|--output)
            OUTPUT_FILE="$2"
            shift
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Create output directory if it doesn't exist
OUTPUT_DIR=$(dirname "$OUTPUT_FILE")
if [ "$OUTPUT_DIR" != "." ] && [ ! -d "$OUTPUT_DIR" ]; then
    mkdir -p "$OUTPUT_DIR"
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to create output directory: $OUTPUT_DIR"
        exit 1
    fi
fi

# Check if ffmpeg is installed
if ! command -v ffmpeg &> /dev/null; then
    echo "ERROR: ffmpeg is not installed. Please install it to generate WAV files."
    exit 1
fi

# Generate WAV file
echo "Generating WAV file with the following parameters:"
echo "  * Duration: $DURATION seconds"
echo "  * Frequency: $FREQUENCY Hz"
echo "  * Channels: $CHANNELS"
echo "  * Sample rate: $SAMPLE_RATE Hz"
echo "  * Output file: $OUTPUT_FILE"

# Create a single-channel or multi-channel WAV file
if [ "$CHANNELS" -eq 1 ]; then
    # Single channel (mono)
    ffmpeg -y -f lavfi -i "sine=frequency=$FREQUENCY:duration=$DURATION" \
        -c:a pcm_s16le -ar $SAMPLE_RATE -ac 1 "$OUTPUT_FILE" 2>&1 | grep -v "^ffmpeg version"
else
    # Multi-channel
    FILTER_COMPLEX=""
    for i in $(seq 0 $((CHANNELS - 1))); do
        FILTER_COMPLEX="${FILTER_COMPLEX}[0:a]aformat=channel_layouts=mono,asplit=2[a$i][tmp$i]; "
    done
    
    # Create the final mix of all channels
    FILTER_COMPLEX="${FILTER_COMPLEX}"
    for i in $(seq 0 $((CHANNELS - 1))); do
        if [ $i -eq 0 ]; then
            FILTER_COMPLEX="${FILTER_COMPLEX}[a$i]"
        else
            FILTER_COMPLEX="${FILTER_COMPLEX}[a$i]"
        fi
    done
    FILTER_COMPLEX="${FILTER_COMPLEX}amerge=inputs=$CHANNELS[aout]"
    
    ffmpeg -y -f lavfi -i "sine=frequency=$FREQUENCY:duration=$DURATION" \
        -filter_complex "$FILTER_COMPLEX" -map "[aout]" \
        -c:a pcm_s16le -ar $SAMPLE_RATE "$OUTPUT_FILE" 2>&1 | grep -v "^ffmpeg version"
fi

# Check if the file was created successfully
if [ $? -ne 0 ] || [ ! -f "$OUTPUT_FILE" ]; then
    echo "ERROR: Failed to generate WAV file."
    exit 1
fi

# Get file information
file_size=$(du -h "$OUTPUT_FILE" | cut -f1)
file_duration=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$OUTPUT_FILE")
file_duration=$(printf "%.2f" "$file_duration")

echo "WAV file generated successfully:"
echo "  * Size: $file_size"
echo "  * Actual duration: $file_duration seconds"
echo "  * Path: $(realpath "$OUTPUT_FILE")"
exit 0