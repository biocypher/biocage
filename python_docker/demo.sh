#!/bin/bash
set -e

echo "🧪 CodeSandbox Demo - Testing Container Functionality"
echo "=================================================="

# Test 1: Basic Python execution via stdin
echo "📝 Test 1: Basic Python execution"
echo 'print("Hello from CodeSandbox!")' | docker run --rm -i codesandbox:latest
echo

# Test 2: NumPy/Pandas functionality (testing dependencies)
echo "📊 Test 2: NumPy and Pandas functionality"
cat << 'EOF' | docker run --rm -i codesandbox:latest
import numpy as np
import pandas as pd

# Test NumPy
arr = np.array([1, 2, 3, 4, 5])
print(f"NumPy array: {arr}")
print(f"Mean: {np.mean(arr)}")

# Test Pandas
df = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]})
print(f"Pandas DataFrame:\n{df}")
EOF
echo

# Test 3: Environment variable execution
echo "🔧 Test 3: Environment variable execution"
docker run --rm -e PYTHON_CODE="print('Environment variable test works!')" codesandbox:latest
echo

# Test 4: Error handling
echo "❌ Test 4: Error handling"
echo 'print(undefined_variable)' | docker run --rm -i codesandbox:latest
echo

# Test 5: Resource limits (timeout simulation)
echo "⏱️  Test 5: Execution timeout (quick test)"
cat << 'EOF' | docker run --rm -i codesandbox:latest
import time
print("Starting quick computation...")
time.sleep(1)
print("Computation completed!")
EOF
echo

echo "✅ Demo complete! All tests executed."
echo "The container is working as expected if you see JSON output for each test." 