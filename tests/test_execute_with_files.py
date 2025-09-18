"""Test execute_with_files method functionality."""

import json
import tempfile
import pytest

from biocage import BioCageOrchestrator


class TestExecuteWithFiles:
    """Test execute_with_files method with various file types and scenarios."""

    def test_execute_with_single_file(self):
        """Test execute_with_files with a single temporary file."""
        with BioCageOrchestrator() as sandbox:
            files = {
                '/tmp/test_data.txt': 'Hello, World!\nThis is a test file.\nEnd of file.'
            }

            result = sandbox.execute_with_files("""
import os

# Check if file exists
file_path = '/tmp/test_data.txt'
print(f"File exists: {os.path.exists(file_path)}")

# Read and process file
with open(file_path, 'r') as f:
    content = f.read()

lines = content.strip().split('\\n')
print(f"Number of lines: {len(lines)}")
print(f"First line: {lines[0]}")
print(f"File size: {len(content)} characters")
""", files)

            assert result.success
            assert "File exists: True" in result.stdout
            assert "Number of lines: 3" in result.stdout
            assert "First line: Hello, World!" in result.stdout
            assert "File size: 47 characters" in result.stdout

    def test_execute_with_multiple_files(self):
        """Test execute_with_files with multiple temporary files."""
        with BioCageOrchestrator() as sandbox:
            files = {
                '/tmp/data.csv': 'name,age,city\nAlice,30,NYC\nBob,25,LA\nCharlie,35,Chicago',
                '/tmp/config.json': '{"debug": true, "max_records": 100, "version": "1.0"}',
                '/tmp/readme.txt': 'This is a README file\nWith instructions\nFor data processing'
            }

            result = sandbox.execute_with_files("""
import json
import csv
import os
from io import StringIO

# Check all files exist
files_to_check = ['/tmp/data.csv', '/tmp/config.json', '/tmp/readme.txt']
existing_files = [f for f in files_to_check if os.path.exists(f)]
print(f"Existing files: {len(existing_files)}/{len(files_to_check)}")

# Process CSV file
with open('/tmp/data.csv', 'r') as f:
    csv_reader = csv.DictReader(f)
    records = list(csv_reader)

print(f"CSV records: {len(records)}")
print(f"Average age: {sum(int(r['age']) for r in records) / len(records):.1f}")

# Process JSON config
with open('/tmp/config.json', 'r') as f:
    config = json.load(f)

print(f"Config version: {config['version']}")
print(f"Debug mode: {config['debug']}")
print(f"Max records: {config['max_records']}")

# Count lines in README
with open('/tmp/readme.txt', 'r') as f:
    readme_lines = f.readlines()

print(f"README lines: {len(readme_lines)}")
""", files)

            assert result.success
            assert "Existing files: 3/3" in result.stdout
            assert "CSV records: 3" in result.stdout
            assert "Average age: 30.0" in result.stdout
            assert "Config version: 1.0" in result.stdout
            assert "Debug mode: True" in result.stdout
            assert "README lines: 3" in result.stdout

    def test_execute_with_python_module(self):
        """Test execute_with_files with Python module that can be imported."""
        with BioCageOrchestrator() as sandbox:
            files = {
                '/tmp/math_utils.py': '''
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)

def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)

def prime_factors(n):
    factors = []
    d = 2
    while d * d <= n:
        while n % d == 0:
            factors.append(d)
            n //= d
        d += 1
    if n > 1:
        factors.append(n)
    return factors

PI = 3.14159265359
E = 2.71828182846
''',
                '/tmp/test_data.txt': '12\n15\n8\n7\n100'
            }

            result = sandbox.execute_with_files("""
import sys
sys.path.append('/tmp')

# Import the custom module
import math_utils

# Read test numbers
with open('/tmp/test_data.txt', 'r') as f:
    numbers = [int(line.strip()) for line in f.readlines()]

print(f"Test numbers: {numbers}")

# Test mathematical functions
for num in numbers:
    if num <= 10:  # Keep factorial reasonable
        fact = math_utils.factorial(num)
        print(f"Factorial of {num}: {fact}")

    if num <= 15:  # Keep fibonacci reasonable
        fib = math_utils.fibonacci(num)
        print(f"Fibonacci of {num}: {fib}")

    factors = math_utils.prime_factors(num)
    print(f"Prime factors of {num}: {factors}")

# Use constants
print(f"PI constant: {math_utils.PI}")
print(f"E constant: {math_utils.E}")
""", files)

            assert result.success
            assert "Test numbers: [12, 15, 8, 7, 100]" in result.stdout
            assert "Factorial of 8: 40320" in result.stdout
            assert "Factorial of 7: 5040" in result.stdout
            assert "Fibonacci of 8: 21" in result.stdout
            assert "Prime factors of 12: [2, 2, 3]" in result.stdout
            assert "Prime factors of 100: [2, 2, 5, 5]" in result.stdout
            assert "PI constant: 3.14159" in result.stdout

    def test_execute_with_config_files(self):
        """Test execute_with_files with various configuration file formats."""
        with BioCageOrchestrator() as sandbox:
            files = {
                '/tmp/config.ini': '''[database]
host = localhost
port = 5432
username = admin
password = secret123

[logging]
level = INFO
file = /var/log/app.log
max_size = 100MB

[features]
debug = true
cache_enabled = false
max_connections = 50
''',
                '/tmp/settings.yaml': '''server:
  host: 0.0.0.0
  port: 8080
  workers: 4

database:
  url: postgresql://user:pass@localhost/db
  pool_size: 10
  timeout: 30

cache:
  type: redis
  host: localhost
  port: 6379
  ttl: 3600
''',
                '/tmp/environment.env': '''DATABASE_URL=postgresql://localhost:5432/mydb
REDIS_URL=redis://localhost:6379
DEBUG=true
SECRET_KEY=super-secret-key-123
API_VERSION=v1
MAX_WORKERS=4
TIMEOUT=30
'''
            }

            result = sandbox.execute_with_files("""
import configparser
import os

# Parse INI file
config = configparser.ConfigParser()
config.read('/tmp/config.ini')

print("=== INI Configuration ===")
print(f"Database host: {config.get('database', 'host')}")
print(f"Database port: {config.get('database', 'port')}")
print(f"Log level: {config.get('logging', 'level')}")
print(f"Debug enabled: {config.getboolean('features', 'debug')}")
print(f"Max connections: {config.getint('features', 'max_connections')}")

# Parse environment file manually (simple key=value format)
env_vars = {}
with open('/tmp/environment.env', 'r') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#'):
            key, value = line.split('=', 1)
            env_vars[key] = value

print("\\n=== Environment Variables ===")
print(f"Database URL: {env_vars.get('DATABASE_URL')}")
print(f"Debug mode: {env_vars.get('DEBUG')}")
print(f"API version: {env_vars.get('API_VERSION')}")
print(f"Max workers: {env_vars.get('MAX_WORKERS')}")

# Check YAML file exists (we won't parse it without PyYAML)
print(f"\\n=== File Checks ===")
print(f"YAML config exists: {os.path.exists('/tmp/settings.yaml')}")
print(f"INI config exists: {os.path.exists('/tmp/config.ini')}")
print(f"ENV config exists: {os.path.exists('/tmp/environment.env')}")

# Read YAML content manually for basic validation
with open('/tmp/settings.yaml', 'r') as f:
    yaml_content = f.read()

print(f"YAML content length: {len(yaml_content)} characters")
print(f"Contains 'server:': {'server:' in yaml_content}")
print(f"Contains 'database:': {'database:' in yaml_content}")
""", files)

            assert result.success
            assert "Database host: localhost" in result.stdout
            assert "Database port: 5432" in result.stdout
            assert "Log level: INFO" in result.stdout
            assert "Debug enabled: True" in result.stdout
            assert "Max connections: 50" in result.stdout
            assert "Database URL: postgresql://localhost:5432/mydb" in result.stdout
            assert "Debug mode: true" in result.stdout
            assert "API version: v1" in result.stdout
            assert "YAML config exists: True" in result.stdout
            assert "Contains 'server:': True" in result.stdout

    def test_execute_with_files_error_handling(self):
        """Test execute_with_files error handling when code fails."""
        with BioCageOrchestrator() as sandbox:
            files = {
                '/tmp/data.txt': 'Some test data',
                '/tmp/numbers.txt': '1\n2\ninvalid\n4\n5'
            }

            result = sandbox.execute_with_files("""
# This will succeed
with open('/tmp/data.txt', 'r') as f:
    data = f.read()
print(f"Read data: {data.strip()}")

# This will fail when trying to convert 'invalid' to int
with open('/tmp/numbers.txt', 'r') as f:
    for line_num, line in enumerate(f, 1):
        number = int(line.strip())  # This will fail on 'invalid'
        print(f"Line {line_num}: {number}")
""", files)

            assert not result.success
            assert "Read data: Some test data" in result.stdout  # Partial success
            assert "ValueError" in result.stderr  # Error captured

    def test_execute_with_files_unicode_content(self):
        """Test execute_with_files with Unicode content."""
        with BioCageOrchestrator() as sandbox:
            files = {
                '/tmp/unicode_text.txt': 'Hello 世界! 🌍\nЗдравствуй мир!\nBonjour le monde! 🇫🇷\nこんにちは世界！🇯🇵',
                '/tmp/emoji_data.txt': '😀😃😄😁😆😅😂🤣😊😇🙂🙃😉😌😍🥰😘😗😙😚😋😛😝😜🤪🤨🧐🤓',
                '/tmp/math_symbols.txt': '∑∏∫∂∞∇∆√∛∜∝∠∟∡∢⊥⊙⊘⊗⊕⊖⊗⊘⊙⊚⊛⊜⊝⊞⊟⊠⊡⊢⊣⊤⊥⊦⊧⊨⊩⊪⊫⊬⊭⊮⊯'
            }

            result = sandbox.execute_with_files("""
import os

# Read Unicode text file
with open('/tmp/unicode_text.txt', 'r', encoding='utf-8') as f:
    unicode_lines = f.readlines()

print(f"Unicode lines: {len(unicode_lines)}")
for i, line in enumerate(unicode_lines, 1):
    print(f"Line {i}: {line.strip()}")

# Process emoji file
with open('/tmp/emoji_data.txt', 'r', encoding='utf-8') as f:
    emoji_content = f.read().strip()

print(f"\\nEmoji count: {len(emoji_content)}")
print(f"First 10 emojis: {emoji_content[:10]}")

# Process math symbols
with open('/tmp/math_symbols.txt', 'r', encoding='utf-8') as f:
    math_symbols = f.read().strip()

print(f"\\nMath symbols count: {len(math_symbols)}")
print(f"Contains sum symbol: {'∑' in math_symbols}")
print(f"Contains integral: {'∫' in math_symbols}")
print(f"Contains infinity: {'∞' in math_symbols}")

# Check file sizes
for filename in ['/tmp/unicode_text.txt', '/tmp/emoji_data.txt', '/tmp/math_symbols.txt']:
    size = os.path.getsize(filename)
    print(f"File {filename}: {size} bytes")
""", files)

            assert result.success
            assert "Unicode lines: 4" in result.stdout
            assert "Hello 世界! 🌍" in result.stdout
            assert "Здравствуй мир!" in result.stdout
            assert "Emoji count:" in result.stdout
            assert "Contains sum symbol: True" in result.stdout
            assert "Contains integral: True" in result.stdout
            assert "Contains infinity: True" in result.stdout

    def test_execute_with_files_large_content(self):
        """Test execute_with_files with larger file content."""
        with BioCageOrchestrator() as sandbox:
            # Create large CSV content
            large_csv = "id,name,value,description\n"
            for i in range(1000):
                large_csv += f"{i},User{i},{i*10},Description for user {i}\n"

            # Create large text content
            large_text = "\n".join([f"Line {i}: " + "x" * 100 for i in range(500)])

            files = {
                '/tmp/large_data.csv': large_csv,
                '/tmp/large_text.txt': large_text,
                '/tmp/metadata.json': json.dumps({
                    "csv_records": 1000,
                    "text_lines": 500,
                    "generated_by": "BioCage test",
                    "processing_instructions": [
                        "Read CSV and calculate statistics",
                        "Process text file line by line",
                        "Generate summary report"
                    ]
                }, indent=2)
            }

            result = sandbox.execute_with_files("""
import json
import csv
from io import StringIO
import os

# Read metadata
with open('/tmp/metadata.json', 'r') as f:
    metadata = json.load(f)

print(f"Processing {metadata['csv_records']} CSV records...")
print(f"Processing {metadata['text_lines']} text lines...")

# Process large CSV
with open('/tmp/large_data.csv', 'r') as f:
    csv_reader = csv.DictReader(f)
    records = list(csv_reader)

print(f"Actual CSV records loaded: {len(records)}")

# Calculate statistics
if records:
    values = [int(r['value']) for r in records]
    print(f"Sum of values: {sum(values)}")
    print(f"Average value: {sum(values) / len(values):.1f}")
    print(f"Min value: {min(values)}")
    print(f"Max value: {max(values)}")

# Process large text file
with open('/tmp/large_text.txt', 'r') as f:
    text_lines = f.readlines()

print(f"Actual text lines loaded: {len(text_lines)}")

# Calculate text statistics
total_chars = sum(len(line) for line in text_lines)
print(f"Total characters: {total_chars}")
print(f"Average line length: {total_chars / len(text_lines):.1f}")

# File size information
for filename in ['/tmp/large_data.csv', '/tmp/large_text.txt', '/tmp/metadata.json']:
    size = os.path.getsize(filename)
    print(f"{filename}: {size} bytes ({size/1024:.1f} KB)")
""", files)

            assert result.success
            assert "Actual CSV records loaded: 1000" in result.stdout
            assert "Actual text lines loaded: 500" in result.stdout
            assert "Sum of values: 4995000" in result.stdout  # Sum of 0*10 + 1*10 + ... + 999*10
            assert "Average value: 4995.0" in result.stdout
            assert "Min value: 0" in result.stdout
            assert "Max value: 9990" in result.stdout
            assert "Total characters:" in result.stdout

    def test_execute_with_files_timeout(self):
        """Test execute_with_files with timeout handling."""
        with BioCageOrchestrator() as sandbox:
            files = {
                '/tmp/test_data.txt': 'Test data for timeout scenario'
            }

            # This should timeout
            result = sandbox.execute_with_files("""
import time

# Read the file first
with open('/tmp/test_data.txt', 'r') as f:
    data = f.read()
print(f"Read data: {data.strip()}")

# Then sleep for too long
print("Starting long operation...")
time.sleep(10)  # This should cause timeout
print("This should not appear")
""", files, timeout=3)

            assert not result.success
            assert result.exit_code == 124  # Timeout exit code
            assert "Read data: Test data for timeout scenario" in result.stdout
            assert "Starting long operation..." in result.stdout
            assert "This should not appear" not in result.stdout

    def test_execute_with_files_persistence_check(self):
        """Test that files created by execute_with_files don't persist between calls."""
        with BioCageOrchestrator(execution_mode="persistent") as sandbox:
            # First execution with files
            files1 = {
                '/tmp/temp_file1.txt': 'This is temporary file 1'
            }

            result1 = sandbox.execute_with_files("""
import os

# Check and use the temporary file
print(f"File exists: {os.path.exists('/tmp/temp_file1.txt')}")

with open('/tmp/temp_file1.txt', 'r') as f:
    content = f.read()
print(f"Content: {content.strip()}")

# Set a variable for next test
persistent_var = "This should persist"
""", files1)

            assert result1.success
            assert "File exists: True" in result1.stdout
            assert "Content: This is temporary file 1" in result1.stdout

            # Second execution without files - check if temp file persists
            result2 = sandbox.run("""
import os

# Check if temporary file from previous execution still exists
print(f"Previous temp file exists: {os.path.exists('/tmp/temp_file1.txt')}")

# Check if variable persists (it should)
try:
    print(f"Persistent variable: {persistent_var}")
except NameError:
    print("Persistent variable not found")
""")

            assert result2.success
            # The temporary file should NOT persist (it's cleaned up)
            # But the variable should persist in persistent mode
            assert "Persistent variable: This should persist" in result2.stdout

            # Third execution with different files
            files3 = {
                '/tmp/temp_file3.txt': 'This is temporary file 3',
                '/tmp/another_temp.txt': 'Another temporary file'
            }

            result3 = sandbox.execute_with_files("""
import os

# Check new files exist
print(f"File 3 exists: {os.path.exists('/tmp/temp_file3.txt')}")
print(f"Another temp exists: {os.path.exists('/tmp/another_temp.txt')}")

# Check old file doesn't exist
print(f"Old file exists: {os.path.exists('/tmp/temp_file1.txt')}")

# Variable should still persist
print(f"Still persistent: {persistent_var}")
""", files3)

            assert result3.success
            assert "File 3 exists: True" in result3.stdout
            assert "Another temp exists: True" in result3.stdout
            assert "Still persistent: This should persist" in result3.stdout