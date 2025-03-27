#!/bin/bash

# Exit on any error
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$SCRIPT_DIR/src"
DEPLOYMENT_DIR="$SCRIPT_DIR/deployment"

echo "Creating deployment package at $DEPLOYMENT_DIR"

# Make sure the deployment directory exists and is clean
rm -rf "$DEPLOYMENT_DIR"
mkdir -p "$DEPLOYMENT_DIR"

# Copy directories using find to avoid recursive copy issues
echo "Copying directories..."
for dir in voip_benchmark audio config docker docs results scripts tests; do
    if [ -d "$SRC_DIR/$dir" ]; then
        mkdir -p "$DEPLOYMENT_DIR/$dir"
        find "$SRC_DIR/$dir" -type f -not -path "*/\.*" -not -path "*/__pycache__*" | while read file; do
            rel_path=${file#$SRC_DIR/}
            dest_dir=$(dirname "$DEPLOYMENT_DIR/$rel_path")
            mkdir -p "$dest_dir"
            cp "$file" "$dest_dir/"
        done
    fi
done

# Copy other needed files
echo "Copying additional files..."
cp "$SRC_DIR/setup-env.sh" "$DEPLOYMENT_DIR/" 2>/dev/null || true
cp "$SRC_DIR/README.md" "$DEPLOYMENT_DIR/" 2>/dev/null || true
cp "$SRC_DIR/.gitignore" "$DEPLOYMENT_DIR/" 2>/dev/null || true

# Remove Python cache files
echo "Cleaning up Python cache files..."
find "$DEPLOYMENT_DIR" -name "__pycache__" -type d -exec rm -rf {} +  2>/dev/null || true
find "$DEPLOYMENT_DIR" -name "*.pyc" -delete  2>/dev/null || true
find "$DEPLOYMENT_DIR" -name "*.pyo" -delete  2>/dev/null || true

# Make scripts executable
echo "Making scripts executable..."
find "$DEPLOYMENT_DIR" -name "*.sh" -type f -exec chmod +x {} \;
find "$DEPLOYMENT_DIR" -name "*.py" -type f -exec chmod +x {} \;

# Validate that all necessary files are present
echo "Validating deployment package..."
needed_files=(
    "README.md"
    "docs/USER_GUIDE.md"
    "docs/TECHNICAL_REFERENCE.md"
)

for file in "${needed_files[@]}"; do
    if [ ! -f "$DEPLOYMENT_DIR/$file" ]; then
        echo "Warning: $file is missing from deployment package."
    else
        echo "Found $file"
    fi
done

echo "Deployment package created successfully."
echo "You can now run the setup-env.sh script in the deployment directory to create a virtual environment and install dependencies."
