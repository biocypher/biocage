"""Test file and directory exposure functionality."""

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from codesandbox import PythonSandboxManager


@pytest.fixture
def test_data_dir():
    """Create a temporary directory with test data."""
    test_dir = Path(tempfile.mkdtemp(prefix="sandbox_test_"))

    # Create a test CSV file
    csv_file = test_dir / "sample_data.csv"
    csv_file.write_text("""name,age,city
Alice,30,New York
Bob,25,San Francisco
Charlie,35,Chicago
""")

    # Create a test Python module
    py_file = test_dir / "helper_module.py"
    py_file.write_text("""
def greet(name):
    return f"Hello, {name}!"

def calculate_sum(numbers):
    return sum(numbers)

PI = 3.14159
""")

    # Create a subdirectory with multiple files
    subdir = test_dir / "models"
    subdir.mkdir()

    (subdir / "model1.txt").write_text("Model 1 configuration")
    (subdir / "model2.txt").write_text("Model 2 configuration")
    (subdir / "config.json").write_text('{"version": "1.0", "type": "classifier"}')

    yield {"test_dir": test_dir, "csv_file": csv_file, "py_file": py_file, "subdir": subdir}

    # Cleanup
    shutil.rmtree(test_dir)


@pytest.fixture
def output_dir():
    """Create a temporary output directory."""
    output_dir = Path(tempfile.mkdtemp(prefix="sandbox_output_"))
    yield output_dir
    shutil.rmtree(output_dir)


class TestFileExposure:
    """Test individual file exposure functionality."""

    def test_single_file_exposure_with_custom_path(self, test_data_dir):
        """Test exposing a single file with custom container path."""
        csv_file = test_data_dir["csv_file"]

        sandbox = PythonSandboxManager()
        container_path = sandbox.expose_file(csv_file, "/app/shared/data.csv")

        with sandbox:
            result = sandbox.run(f"""
import pandas as pd
import os

print(f"File exists: {{os.path.exists('{container_path}')}}")
data = pd.read_csv('{container_path}')
print(f"Shape: {{data.shape}}")
print(f"Names: {{list(data['name'])}}")
""")
            assert result.success
            assert "File exists: True" in result.stdout
            assert "Shape: (3, 3)" in result.stdout
            assert "Alice" in result.stdout

    def test_single_file_exposure_auto_path(self, test_data_dir):
        """Test exposing a file with auto-generated container path."""
        csv_file = test_data_dir["csv_file"]

        sandbox = PythonSandboxManager()
        container_path = sandbox.expose_file(csv_file)  # Auto-generated path

        with sandbox:
            result = sandbox.run(f"""
import os
print(f"Auto path: {container_path}")
print(f"File exists: {{os.path.exists('{container_path}')}}")
with open('{container_path}', 'r') as f:
    lines = f.readlines()
print(f"Lines: {{len(lines)}}")
""")
            assert result.success
            assert "File exists: True" in result.stdout
            assert "Lines: 4" in result.stdout  # Header + 3 data rows

    def test_file_exposure_context_manager(self, test_data_dir):
        """Test file exposure using context manager configuration."""
        csv_file = test_data_dir["csv_file"]

        with PythonSandboxManager().configure_context_manager(
            expose_files={str(csv_file): "/app/shared/data.csv"}
        ) as sandbox:
            result = sandbox.run("""
import pandas as pd
df = pd.read_csv('/app/shared/data.csv')
print(f"Average age: {df['age'].mean():.1f}")
print(f"Cities: {', '.join(df['city'])}")
""")
            assert result.success
            assert "Average age: 30.0" in result.stdout
            assert "New York" in result.stdout

    def test_python_module_exposure(self, test_data_dir):
        """Test exposing and importing a Python module."""
        py_file = test_data_dir["py_file"]

        with PythonSandboxManager().configure_context_manager(
            expose_files={str(py_file): "/app/shared/helper.py"}
        ) as sandbox:
            result = sandbox.run("""
import sys
sys.path.append('/app/shared')
import helper

print(f"Greeting: {helper.greet('Test')}")
print(f"Sum: {helper.calculate_sum([1, 2, 3, 4, 5])}")
print(f"PI: {helper.PI}")
""")
            assert result.success
            assert "Greeting: Hello, Test!" in result.stdout
            assert "Sum: 15" in result.stdout
            assert "PI: 3.14159" in result.stdout


class TestDirectoryExposure:
    """Test directory exposure functionality."""

    def test_directory_exposure_readonly(self, test_data_dir):
        """Test exposing a directory as read-only."""
        subdir = test_data_dir["subdir"]

        sandbox = PythonSandboxManager()
        container_path = sandbox.expose_directory(subdir, "/app/models", read_only=True)

        with sandbox:
            result = sandbox.run(f"""
import os
import json

print(f"Directory exists: {{os.path.exists('{container_path}')}}")
files = os.listdir('{container_path}')
print(f"Files: {{sorted(files)}}")

# Read JSON file
with open('{container_path}/config.json', 'r') as f:
    config = json.load(f)
print(f"Config: {{config}}")
""")
            assert result.success
            assert "Directory exists: True" in result.stdout
            assert "config.json" in result.stdout
            assert "model1.txt" in result.stdout
            assert "version" in result.stdout and "1.0" in result.stdout

    def test_directory_exposure_context_manager(self, test_data_dir):
        """Test directory exposure using context manager."""
        subdir = test_data_dir["subdir"]

        with PythonSandboxManager().configure_context_manager(
            expose_directories={str(subdir): "/app/models"}
        ) as sandbox:
            result = sandbox.run("""
import os

files = []
for filename in os.listdir('/app/models'):
    filepath = os.path.join('/app/models', filename)
    with open(filepath, 'r') as f:
        content = f.read().strip()
    files.append(f"{filename}: {len(content)} chars")

print("Files and sizes:")
for file_info in sorted(files):
    print(f"  {file_info}")
""")
            assert result.success
            assert "config.json:" in result.stdout
            assert "model1.txt:" in result.stdout

    def test_multiple_directory_exposure(self, test_data_dir):
        """Test exposing multiple directories."""
        test_dir = test_data_dir["test_dir"]
        subdir = test_data_dir["subdir"]

        with PythonSandboxManager().configure_context_manager(
            expose_directories={str(test_dir): "/app/data", str(subdir): "/app/models"}
        ) as sandbox:
            result = sandbox.run("""
import os

data_files = os.listdir('/app/data')
model_files = os.listdir('/app/models')

print(f"Data directory: {len(data_files)} items")
print(f"Models directory: {len(model_files)} items")
print(f"CSV exists: {'sample_data.csv' in data_files}")
print(f"Config exists: {'config.json' in model_files}")
""")
            assert result.success
            assert "Data directory:" in result.stdout
            assert "Models directory:" in result.stdout
            assert "CSV exists: True" in result.stdout
            assert "Config exists: True" in result.stdout


class TestWritableDirectories:
    """Test writable directory functionality."""

    def test_writable_directory_basic(self, output_dir):
        """Test basic writable directory functionality."""
        sandbox = PythonSandboxManager()
        container_path = sandbox.expose_directory(output_dir, "/app/output", read_only=False)

        with sandbox:
            result = sandbox.run(f"""
import os

# Write a test file
with open('{container_path}/test.txt', 'w') as f:
    f.write('Hello from container!')

print(f"File written to: {container_path}/test.txt")
print(f"File exists: {{os.path.exists('{container_path}/test.txt')}}")

# Read it back
with open('{container_path}/test.txt', 'r') as f:
    content = f.read()
print(f"Content: {{content}}")
""")
            assert result.success
            assert "File written to:" in result.stdout
            assert "File exists: True" in result.stdout
            assert "Content: Hello from container!" in result.stdout

            # Verify file exists on host
            host_file = output_dir / "test.txt"
            assert host_file.exists()
            assert host_file.read_text() == "Hello from container!"

    def test_writable_directory_context_manager(self, output_dir):
        """Test writable directory with context manager."""
        with PythonSandboxManager().configure_context_manager(
            expose_directories_rw={str(output_dir): "/app/output"}
        ) as sandbox:
            result = sandbox.run("""
import json
import os

# Write multiple files
data = {'status': 'success', 'value': 42}
with open('/app/output/result.json', 'w') as f:
    json.dump(data, f, indent=2)

with open('/app/output/log.txt', 'w') as f:
    f.write('Processing complete\\n')
    f.write('Files generated successfully\\n')

files = os.listdir('/app/output')
print(f"Created files: {sorted(files)}")
""")
            assert result.success
            assert "result.json" in result.stdout
            assert "log.txt" in result.stdout

            # Verify files on host
            result_file = output_dir / "result.json"
            log_file = output_dir / "log.txt"

            assert result_file.exists()
            assert log_file.exists()

            result_data = json.loads(result_file.read_text())
            assert result_data["status"] == "success"
            assert result_data["value"] == 42

    def test_combined_readonly_writable(self, test_data_dir, output_dir):
        """Test combining read-only input and writable output directories."""
        input_dir = test_data_dir["test_dir"]

        with PythonSandboxManager().configure_context_manager(
            expose_directories={str(input_dir): "/app/input"},  # Read-only
            expose_directories_rw={str(output_dir): "/app/output"},  # Writable
        ) as sandbox:
            result = sandbox.run("""
import os
import pandas as pd

# Read from input directory
df = pd.read_csv('/app/input/sample_data.csv')
print(f"Loaded {len(df)} records")

# Process and write to output
summary = {
    'total_records': len(df),
    'average_age': df['age'].mean(),
    'cities': list(df['city'].unique())
}

# Write summary
with open('/app/output/summary.txt', 'w') as f:
    f.write(f"Total records: {summary['total_records']}\\n")
    f.write(f"Average age: {summary['average_age']:.1f}\\n")
    f.write(f"Cities: {', '.join(summary['cities'])}\\n")

# Write processed data
processed_df = df.copy()
processed_df['age_group'] = processed_df['age'].apply(
    lambda x: 'young' if x < 30 else 'senior'
)
processed_df.to_csv('/app/output/processed_data.csv', index=False)

print("Processing complete")

# Test read-only protection
try:
    with open('/app/input/test_write.txt', 'w') as f:
        f.write('This should fail')
    print("ERROR: Should not be able to write to read-only directory")
except Exception as e:
    print(f"Read-only protection working: {type(e).__name__}")
""")
            assert result.success
            assert "Loaded 3 records" in result.stdout
            assert "Processing complete" in result.stdout
            assert "protection working" in result.stdout

            # Verify output files
            summary_file = output_dir / "summary.txt"
            processed_file = output_dir / "processed_data.csv"

            assert summary_file.exists()
            assert processed_file.exists()

            summary_content = summary_file.read_text()
            assert "Total records: 3" in summary_content
            assert "Average age: 30.0" in summary_content


class TestTemporaryFiles:
    """Test temporary file creation."""

    def test_create_temp_file_csv(self):
        """Test creating a temporary CSV file."""
        with PythonSandboxManager() as sandbox:
            csv_content = "name,value\ntest1,10\ntest2,20"
            temp_path = sandbox.create_temp_file(csv_content, ".csv")

            result = sandbox.run(f"""
import pandas as pd
import os

print(f"Temp file exists: {{os.path.exists('{temp_path}')}}")
df = pd.read_csv('{temp_path}')
print(f"Loaded {{len(df)}} rows")
print(f"Values: {{list(df['value'])}}")
print(f"Sum: {{df['value'].sum()}}")
""")
            assert result.success
            assert "Temp file exists: True" in result.stdout
            assert "Loaded 2 rows" in result.stdout
            assert "Values: [10, 20]" in result.stdout
            assert "Sum: 30" in result.stdout

    def test_create_temp_file_python(self):
        """Test creating a temporary Python file."""
        with PythonSandboxManager() as sandbox:
            python_content = """
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)

def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)
"""
            temp_path = sandbox.create_temp_file(python_content, ".py")

            result = sandbox.run(f"""
import sys
import os

# Add temp file directory to path
temp_dir = os.path.dirname('{temp_path}')
sys.path.append(temp_dir)

# Import the module (remove .py extension)
module_name = os.path.basename('{temp_path}')[:-3]
module = __import__(module_name)

print(f"Factorial 5: {{module.factorial(5)}}")
print(f"Fibonacci 7: {{module.fibonacci(7)}}")
""")
            assert result.success
            assert "Factorial 5: 120" in result.stdout
            assert "Fibonacci 7: 13" in result.stdout

    def test_multiple_temp_files(self):
        """Test creating multiple temporary files."""
        with PythonSandboxManager() as sandbox:
            # Create multiple temp files
            csv_path = sandbox.create_temp_file("id,name\n1,Alice\n2,Bob", ".csv")
            json_path = sandbox.create_temp_file('{"config": "test", "value": 123}', ".json")
            txt_path = sandbox.create_temp_file("This is a text file\nWith multiple lines", ".txt")

            result = sandbox.run(f"""
import pandas as pd
import json
import os

# Read CSV
df = pd.read_csv('{csv_path}')
print(f"CSV records: {{len(df)}}")

# Read JSON
with open('{json_path}', 'r') as f:
    data = json.load(f)
print(f"JSON value: {{data['value']}}")

# Read text
with open('{txt_path}', 'r') as f:
    lines = f.readlines()
print(f"Text lines: {{len(lines)}}")

# Check that all files exist
files = ['{csv_path}', '{json_path}', '{txt_path}']
existing = [f for f in files if os.path.exists(f)]
print(f"Existing files: {{len(existing)}}/{{len(files)}}")
""")
            assert result.success
            assert "CSV records: 2" in result.stdout
            assert "JSON value: 123" in result.stdout
            assert "Text lines: 2" in result.stdout
            assert "Existing files: 3/3" in result.stdout
