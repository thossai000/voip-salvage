#!/bin/bash

# Exit on error
set -e

# Define script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Define directories
SRC_DIR="$SCRIPT_DIR/src"
DEPLOYMENT_DIR="$SCRIPT_DIR/deployment"

# Create deployment directory if it doesn't exist, or clean it if it does
if [ -d "$DEPLOYMENT_DIR" ]; then
    echo "Cleaning existing deployment directory..."
    rm -rf "$DEPLOYMENT_DIR"/*
else
    echo "Creating deployment directory..."
    mkdir -p "$DEPLOYMENT_DIR"
fi

# Copy necessary files and directories
echo "Copying files to deployment directory..."

# Find command to copy files excluding specific patterns
find "$SRC_DIR" -type f -not -path "*/\.*" \
  -not -path "*/\__pycache__*" \
  -not -path "*/*.pyc" \
  -not -path "*/*.pyo" \
  -not -path "*/*.pyd" \
  -not -path "*/*.so" \
  -not -path "*/*.egg-info*" \
  -not -path "*/\.*cache*" \
  | while read -r file; do
    # Get relative path
    rel_path="${file#$SRC_DIR/}"
    # Create target directory if needed
    target_dir="$DEPLOYMENT_DIR/$(dirname "$rel_path")"
    mkdir -p "$target_dir"
    # Copy the file
    cp "$file" "$target_dir/"
    echo "  → Copied: $rel_path"
done

# Make scripts executable
find "$DEPLOYMENT_DIR" -name "*.sh" -type f -exec chmod +x {} \;

# Clean up any Python cache files 
find "$DEPLOYMENT_DIR" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find "$DEPLOYMENT_DIR" -name "*.pyc" -type f -delete
find "$DEPLOYMENT_DIR" -name "*.pyo" -type f -delete
find "$DEPLOYMENT_DIR" -name "*.pyd" -type f -delete

# Validate deployment
echo "Validating deployment..."
essential_files=(
  "README.md"
  "setup.sh"
  "rtp_benchmark.sh"
)

for file in "${essential_files[@]}"; do
  file_path=$(find "$DEPLOYMENT_DIR" -name "$file" -type f)
  if [ -z "$file_path" ]; then
    echo "WARNING: Essential file '$file' not found in deployment."
  else
    echo "  ✓ Found: $file"
  fi
done

echo "Deployment preparation complete at $DEPLOYMENT_DIR"
echo "You can now distribute or deploy the contents of this directory."
