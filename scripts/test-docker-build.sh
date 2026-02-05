#!/bin/bash
set -e

echo "🧪 Testing Docker package installation..."

# Build test image
docker build -f Dockerfile.test -t profit-sharing-test:latest .

if [ $? -eq 0 ]; then
    echo "✅ All packages can be installed successfully!"
    echo "🚀 Proceeding with full build..."

    # Clean up test image
    docker rmi profit-sharing-test:latest

    # Build production image
    docker build -t profit-sharing-api:latest .

    echo "✅ Production image built successfully!"
    docker images profit-sharing-api:latest
else
    echo "❌ Package installation test failed!"
    echo "💡 Try using Dockerfile.alpine for minimal dependencies"
    exit 1
fi
