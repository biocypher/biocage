#!/usr/bin/env python3
"""
BioCage CLI - Command-line interface for BioCage sandbox management.

Usage:
    python -m biocage run "print('Hello World')"
    python -m biocage start --memory 1g --cpu 2.0
    python -m biocage stop
    python -m biocage expose /path/to/file.csv /app/data.csv
    python -m biocage info
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from .biocage_manager import BioCageManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


def setup_parser() -> argparse.ArgumentParser:
    """Set up command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog='biocage',
        description='BioCage - Secure Python sandbox for LLM-generated code execution'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Run command
    run_parser = subparsers.add_parser('run', help='Execute Python code in sandbox')
    run_parser.add_argument('code', help='Python code to execute')
    run_parser.add_argument('--timeout', '-t', type=int, default=30, help='Timeout in seconds')
    run_parser.add_argument('--persistent', '-p', action='store_true', help='Use persistent container')
    run_parser.add_argument('--output', '-o', choices=['json', 'text'], default='text', help='Output format')

    # Start command
    start_parser = subparsers.add_parser('start', help='Start a persistent container')
    start_parser.add_argument('--memory', '-m', default='512m', help='Memory limit (e.g., 512m, 1g)')
    start_parser.add_argument('--cpu', '-c', default='1.0', help='CPU limit (e.g., 1.0, 2.0)')
    start_parser.add_argument('--network', action='store_true', help='Allow network access')

    # Stop command
    subparsers.add_parser('stop', help='Stop the persistent container')

    # Expose command
    expose_parser = subparsers.add_parser('expose', help='Expose files/directories to container')
    expose_parser.add_argument('host_path', help='Path on host system')
    expose_parser.add_argument('container_path', nargs='?', help='Path inside container (auto-generated if not provided)')
    expose_parser.add_argument('--read-write', '-w', action='store_true', help='Mount as read-write (default: read-only)')

    # Info command
    subparsers.add_parser('info', help='Show container information')

    return parser


def cmd_run(args, sandbox: BioCageManager) -> int:
    """Execute code in sandbox."""
    if args.persistent and not sandbox.is_running:
        logger.info("Starting persistent container...")
        sandbox.start_container()

    try:
        result = sandbox.run(args.code, timeout=args.timeout)

        if args.output == 'json':
            print(json.dumps(result.to_dict(), indent=2))
        else:
            if result.success:
                print(result.stdout, end='')
                if result.stderr.strip():
                    print(f"\nSTDERR: {result.stderr}", file=sys.stderr)
            else:
                print(f"ERROR: {result.error or result.stderr}", file=sys.stderr)
                return 1

        return 0
    except Exception as e:
        logger.exception(f"Execution failed: {e}")
        return 1


def cmd_start(args, sandbox: BioCageManager) -> int:
    """Start persistent container."""
    if sandbox.is_running:
        logger.warning("Container is already running")
        return 0

    try:
        container_id = sandbox.start_container(
            memory_limit=args.memory,
            cpu_limit=args.cpu,
            network_access=args.network
        )
        print(f"Container started: {container_id[:12]}")
        return 0
    except Exception as e:
        logger.exception(f"Failed to start container: {e}")
        return 1


def cmd_stop(args, sandbox: BioCageManager) -> int:
    """Stop persistent container."""
    if not sandbox.is_running:
        logger.warning("No container is running")
        return 0

    try:
        sandbox.stop_container()
        print("Container stopped")
        return 0
    except Exception as e:
        logger.exception(f"Failed to stop container: {e}")
        return 1


def cmd_expose(args, sandbox: BioCageManager) -> int:
    """Expose file or directory to container."""
    host_path = Path(args.host_path)

    if not host_path.exists():
        logger.error(f"Path does not exist: {host_path}")
        return 1

    try:
        container_path = sandbox.expose_path(
            host_path,
            args.container_path,
            read_only=not args.read_write
        )
        access_type = "read-write" if args.read_write else "read-only"
        print(f"Exposed {host_path} -> {container_path} ({access_type})")
        return 0
    except Exception as e:
        logger.exception(f"Failed to expose path: {e}")
        return 1


def cmd_info(args, sandbox: BioCageManager) -> int:
    """Show container information."""
    info = sandbox.get_container_info()

    print(f"Container Status: {'Running' if info['is_running'] else 'Stopped'}")
    if info['container_id']:
        print(f"Container ID: {info['container_id'][:12]}")
    if info['container_name']:
        print(f"Container Name: {info['container_name']}")
    print(f"Image: {info['image_name']}")
    print(f"Exposed Paths: {len(info['exposed_paths'])}")
    print(f"Temporary Files: {info['temp_files_count']}")

    if info['exposed_paths']:
        print("\nExposed Paths:")
        for host_path, path_info in info['exposed_paths'].items():
            access = "rw" if ":rw" in path_info['mount_option'] else "ro"
            print(f"  {host_path} -> {path_info['container_path']} ({access})")

    return 0


def main() -> int:
    """Main CLI entry point."""
    parser = setup_parser()
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if not args.command:
        parser.print_help()
        return 1

    # Create sandbox manager
    sandbox = BioCageManager()

    try:
        if args.command == 'run':
            return cmd_run(args, sandbox)
        elif args.command == 'start':
            return cmd_start(args, sandbox)
        elif args.command == 'stop':
            return cmd_stop(args, sandbox)
        elif args.command == 'expose':
            return cmd_expose(args, sandbox)
        elif args.command == 'info':
            return cmd_info(args, sandbox)
        else:
            logger.error(f"Unknown command: {args.command}")
            return 1

    finally:
        # Cleanup if needed
        if not args.command == 'start' and sandbox.is_running:
            sandbox.cleanup()


if __name__ == '__main__':
    sys.exit(main())
