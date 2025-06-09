# CodeSandbox
## Specifying the requirements

As first thing, you need to define a pyproject.toml file in this directory. This file is used to describe the environment used by the sandbox.

Once the pyproject.toml file is defined, you can generate the requirements.txt file by running the following command:

```bash
uv pip compile pyproject.toml -o requirements.txt
```

This will generate a requirements.txt file that can be used to install the dependencies in the sandbox.

## Build the docker image

Once the requirements and the pyproject.toml file are defined, you can build the docker image by running the following command:

```bash
./build.sh
```

This will build the docker image and tag it with the current date.

## Test the container

After building the image, you can verify that the CodeSandbox container is working correctly by running the demo script:

```bash
./demo.sh
```

The demo script tests all key functionality:
- **Basic Python execution** via stdin
- **Dependencies** (NumPy and Pandas functionality)
- **Environment variable** code execution
- **Error handling** with proper JSON responses
- **Execution timing** and resource limits

Each test returns structured JSON output with execution results, including stdout, stderr, exit codes, and execution time. All tests should pass if the container is working correctly.