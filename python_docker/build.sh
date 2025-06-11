#!/bin/bash
set -e

echo "🐍 Building BioCage Container..."

# Build the image with optimizations
docker build \
    --no-cache \
    --pull \
    --tag biocage:latest \
    --tag biocage:$(date +%Y%m%d) \
    .

echo "✅ Build complete!"

# Show image size
echo "📦 Image size:"
docker images biocage:latest --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"