#!/usr/bin/env python3
"""
Example demonstrating file system operations in BioCage.

This script shows how to expose files and directories to the sandbox,
work with temporary files, and handle file permissions securely.
"""

import tempfile
import os
from pathlib import Path
from biocage import BioCageOrchestrator


def setup_sample_data():
    """Use existing sample data files for demonstration."""
    # Use the examples/data directory
    script_dir = Path(__file__).parent
    temp_dir = script_dir.parent / "data"

    if not temp_dir.exists():
        # Fallback: create temporary directory for examples
        temp_dir = Path(tempfile.gettempdir()) / "biocage_examples"
        temp_dir.mkdir(exist_ok=True)

    # Use existing sample files or create them if they don't exist
    csv_file = temp_dir / "sample_data.csv"
    json_file = temp_dir / "config.json"
    text_file = temp_dir / "notes.txt"

    # Create files if they don't exist (fallback)
    if not csv_file.exists():
        csv_content = """name,age,city,salary
Alice,25,New York,70000
Bob,30,London,65000
Charlie,35,Tokyo,75000
Diana,28,Paris,68000
Eve,32,Berlin,72000"""
        csv_file.write_text(csv_content)

    if not json_file.exists():
        json_content = """{
    "database": {
        "host": "localhost",
        "port": 5432,
        "name": "example_db"
    },
    "settings": {
        "debug": true,
        "max_connections": 100,
        "timeout": 30
    }
}"""
        json_file.write_text(json_content)

    if not text_file.exists():
        text_content = """BioCage Example Notes
====================

This is a sample text file for demonstrating
file operations in BioCage sandbox.

Key features:
- Secure file exposure
- Read-only by default
- Volume mounting
- Temporary file support

Last updated: 2024
"""
        text_file.write_text(text_content)

    return temp_dir, csv_file, json_file, text_file


def main():
    print("BioCage File Operations Example")
    print("=" * 35)

    # Setup sample data
    temp_dir, csv_file, json_file, text_file = setup_sample_data()
    print(f"Created sample data in: {temp_dir}")

    demonstrate_file_exposure(csv_file, json_file, text_file)
    demonstrate_directory_exposure(temp_dir)
    demonstrate_temporary_files()
    demonstrate_file_permissions(text_file)
    demonstrate_data_processing_workflow(csv_file)

    # Cleanup
    cleanup_sample_data(temp_dir)


def demonstrate_file_exposure(csv_file, json_file, text_file):
    """Demonstrate exposing individual files to the sandbox."""
    print("\n1. Exposing Individual Files")
    print("-" * 29)

    with BioCageOrchestrator() as sandbox:
        # Expose CSV file
        csv_container_path = sandbox.expose_file(
            str(csv_file),
            "/app/data.csv"
        )
        print(f"Exposed CSV: {csv_file} -> {csv_container_path}")

        # Expose JSON file
        json_container_path = sandbox.expose_file(
            str(json_file),
            "/app/config.json"
        )
        print(f"Exposed JSON: {json_file} -> {json_container_path}")

        # Use exposed files
        result = sandbox.run(f"""
import pandas as pd
import json

# Read CSV file
df = pd.read_csv('{csv_container_path}')
print(f"CSV data shape: {{df.shape}}")
print(f"Average age: {{df['age'].mean():.1f}}")
print(f"Cities: {{list(df['city'].unique())}}")

# Read JSON file
with open('{json_container_path}', 'r') as f:
    config = json.load(f)

print(f"Database host: {{config['database']['host']}}")
print(f"Debug mode: {{config['settings']['debug']}}")
""")

        print("Execution result:")
        print(result.stdout)


def demonstrate_directory_exposure(temp_dir):
    """Demonstrate exposing entire directories to the sandbox."""
    print("\n2. Exposing Directories")
    print("-" * 22)

    with BioCageOrchestrator() as sandbox:
        # Expose entire directory
        container_dir = sandbox.expose_directory(
            str(temp_dir),
            "/app/data_dir",
            readonly=True
        )
        print(f"Exposed directory: {temp_dir} -> {container_dir}")

        # List and process all files in directory
        result = sandbox.run(f"""
import os
import json

# List all files in exposed directory
files = os.listdir('{container_dir}')
print(f"Files in directory: {{files}}")

# Process each file
for filename in files:
    filepath = os.path.join('{container_dir}', filename)

    if filename.endswith('.csv'):
        import pandas as pd
        df = pd.read_csv(filepath)
        print(f"{{filename}}: CSV with {{len(df)}} rows")

    elif filename.endswith('.json'):
        with open(filepath, 'r') as f:
            data = json.load(f)
        print(f"{{filename}}: JSON with {{len(data)}} top-level keys")

    elif filename.endswith('.txt'):
        with open(filepath, 'r') as f:
            lines = f.readlines()
        print(f"{{filename}}: Text file with {{len(lines)}} lines")
""")

        print("Execution result:")
        print(result.stdout)


def demonstrate_temporary_files():
    """Demonstrate creating and working with temporary files in sandbox."""
    print("\n3. Working with Temporary Files")
    print("-" * 32)

    with BioCageOrchestrator(execution_mode="persistent") as sandbox:
        print("Creating temporary files in sandbox...")

        # Create temporary files through code execution
        result1 = sandbox.run("""
import tempfile
import json
import csv

# Create temporary JSON file
temp_json = '/tmp/temp_config.json'
config_data = {
    'app_name': 'BioCage Example',
    'version': '1.0.0',
    'features': ['security', 'isolation', 'flexibility']
}

with open(temp_json, 'w') as f:
    json.dump(config_data, f, indent=2)

print(f"Created temporary JSON: {temp_json}")

# Create temporary CSV file
temp_csv = '/tmp/temp_data.csv'
data = [
    ['Product', 'Price', 'Quantity'],
    ['Laptop', 999.99, 5],
    ['Mouse', 29.99, 20],
    ['Keyboard', 79.99, 15]
]

with open(temp_csv, 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerows(data)

print(f"Created temporary CSV: {temp_csv}")

# Create temporary text file
temp_txt = '/tmp/temp_notes.txt'
notes = '''Temporary Notes
===============

This file was created inside the BioCage sandbox.
It demonstrates temporary file operations.

Features tested:
1. JSON file creation
2. CSV file writing
3. Text file operations
'''

with open(temp_txt, 'w') as f:
    f.write(notes)

print(f"Created temporary text: {temp_txt}")
""")

        print("File creation result:")
        print(result1.stdout)

        # Use the temporary files
        print("\nUsing temporary files...")
        result2 = sandbox.run("""
import json
import pandas as pd

# Read and process temporary JSON
with open('/tmp/temp_config.json', 'r') as f:
    config = json.load(f)

print(f"App: {config['app_name']} v{config['version']}")
print(f"Features: {', '.join(config['features'])}")

# Read and process temporary CSV
df = pd.read_csv('/tmp/temp_data.csv')
print(f"\\nProduct inventory:")
print(f"Total products: {len(df)}")
print(f"Total value: ${(df['Price'] * df['Quantity']).sum():,.2f}")

# Read temporary text file
with open('/tmp/temp_notes.txt', 'r') as f:
    content = f.read()

print(f"\\nNotes file length: {len(content)} characters")
print("First line of notes:", content.split('\\n')[0])
""")

        print("Processing result:")
        print(result2.stdout)


def demonstrate_file_permissions(text_file):
    """Demonstrate file permission handling and security."""
    print("\n4. File Permissions and Security")
    print("-" * 34)

    with BioCageOrchestrator() as sandbox:
        # Expose file (files are read-only by default)
        container_path = sandbox.expose_file(
            str(text_file),
            "/app/readonly.txt"
        )

        print(f"Exposed file as read-only: {container_path}")

        # Try to read (should work)
        result1 = sandbox.run(f"""
# Reading should work
try:
    with open('{container_path}', 'r') as f:
        content = f.read()
    print("✓ Reading file successful")
    print(f"File length: {{len(content)}} characters")
    print(f"First line: {{content.split(chr(10))[0]}}")
except Exception as e:
    print(f"✗ Reading failed: {{e}}")
""")

        print("Read attempt result:")
        print(result1.stdout)

        # Try to write (should fail)
        result2 = sandbox.run(f"""
# Writing should fail (read-only mount)
try:
    with open('{container_path}', 'a') as f:
        f.write("\\nThis should not work!")
    print("✗ Writing succeeded (unexpected!)")
except Exception as e:
    print(f"✓ Writing failed as expected: {{type(e).__name__}}")
    print("File is properly protected")
""")

        print("Write attempt result:")
        print(result2.stdout)

        # Demonstrate internal file creation (always works)
        result3 = sandbox.run("""
# Creating files inside container always works
internal_file = '/tmp/internal_file.txt'
try:
    with open(internal_file, 'w') as f:
        f.write("This file is created inside the container\\n")
        f.write("It's not exposed to the host system\\n")

    with open(internal_file, 'r') as f:
        content = f.read()

    print("✓ Internal file operations work normally")
    print(f"Created: {internal_file}")
    print(f"Content: {content.strip()}")
except Exception as e:
    print(f"✗ Internal file operation failed: {e}")
""")

        print("Internal file result:")
        print(result3.stdout)


def demonstrate_data_processing_workflow(csv_file):
    """Demonstrate a complete data processing workflow with files."""
    print("\n5. Complete Data Processing Workflow")
    print("-" * 38)

    with BioCageOrchestrator(execution_mode="persistent") as sandbox:
        # Expose input file
        input_path = sandbox.expose_file(
            str(csv_file),
            "/app/input_data.csv"
        )

        print(f"Input file: {input_path}")

        # Step 1: Load and explore data
        print("\nStep 1: Data exploration")
        result1 = sandbox.run(f"""
import pandas as pd
import numpy as np

# Load data
df = pd.read_csv('{input_path}')

print("Dataset Overview:")
print(f"Shape: {{df.shape}}")
print(f"Columns: {{list(df.columns)}}")
print()
print("First few rows:")
print(df.head().to_string())
print()
print("Summary statistics:")
print(df.describe().to_string())
""")

        print(result1.stdout)

        # Step 2: Process and analyze data
        print("\nStep 2: Data processing")
        result2 = sandbox.run("""
# Data processing
df['salary_category'] = pd.cut(df['salary'],
                              bins=[0, 60000, 70000, float('inf')],
                              labels=['Low', 'Medium', 'High'])

# Calculate statistics by city
city_stats = df.groupby('city').agg({
    'age': ['mean', 'min', 'max'],
    'salary': ['mean', 'min', 'max'],
    'name': 'count'
}).round(2)

print("Statistics by City:")
print(city_stats.to_string())
print()

# Age distribution
age_distribution = df['age'].value_counts().sort_index()
print("Age Distribution:")
for age, count in age_distribution.items():
    print(f"Age {age}: {count} person(s)")
""")

        print(result2.stdout)

        # Step 3: Generate report and save results
        print("\nStep 3: Generate reports")
        result3 = sandbox.run("""
# Generate summary report
total_employees = len(df)
avg_age = df['age'].mean()
avg_salary = df['salary'].mean()
cities = df['city'].nunique()

report = f'''Employee Analysis Report
========================

Dataset Summary:
- Total employees: {total_employees}
- Average age: {avg_age:.1f} years
- Average salary: ${avg_salary:,.2f}
- Cities represented: {cities}

Salary Categories:
{df['salary_category'].value_counts().to_string()}

Highest paid employee: {df.loc[df['salary'].idxmax(), 'name']} (${df['salary'].max():,})
Youngest employee: {df.loc[df['age'].idxmin(), 'name']} ({df['age'].min()} years old)
Oldest employee: {df.loc[df['age'].idxmax(), 'name']} ({df['age'].max()} years old)
'''

print(report)

# Save processed data to temporary file
output_file = '/tmp/processed_data.csv'
df.to_csv(output_file, index=False)
print(f"\\nProcessed data saved to: {output_file}")

# Save report
report_file = '/tmp/analysis_report.txt'
with open(report_file, 'w') as f:
    f.write(report)
print(f"Report saved to: {report_file}")
""")

        print(result3.stdout)


def cleanup_sample_data(temp_dir):
    """Clean up the sample data files."""
    print(f"\nCleaning up sample data from: {temp_dir}")
    import shutil
    try:
        shutil.rmtree(temp_dir)
        print("✓ Sample data cleaned up successfully")
    except Exception as e:
        print(f"Warning: Could not clean up sample data: {e}")


if __name__ == "__main__":
    main()