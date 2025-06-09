#!/bin/bash
set -e

echo "🐍 Building CodeSandbox Container..."

# Build the image with optimizations
docker build \
    --no-cache \
    --pull \
    --tag codesandbox:latest \
    --tag codesandbox:$(date +%Y%m%d) \
    .

echo "✅ Build complete!"

# Show image size
echo "📦 Image size:"
docker images codesandbox:latest --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"