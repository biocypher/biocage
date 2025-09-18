"""
Dependency analyzer for automatic library detection.

This module analyzes Python code to detect third-party dependencies
by parsing import statements and mapping them to package names.
"""

import ast
import logging
import os
from typing import Dict, List, Set, Tuple
import re

logger = logging.getLogger(__name__)


class DependencyAnalyzer:
    """
    Analyzes Python code to detect third-party dependencies.

    This class uses AST parsing to identify import statements and
    maps them to actual package names that can be installed via pip.

    Attributes:
        standard_lib_modules: Set of Python standard library modules
        import_to_package: Mapping of import names to package names
    """

    def __init__(self):
        """Initialize the dependency analyzer."""
        self.standard_lib_modules = self._get_standard_library_modules()
        self.import_to_package = self._get_import_to_package_mapping()

    def analyze_code_dependencies(self, code: str) -> Dict[str, str]:
        """
        Analyze Python code and return detected dependencies.

        Args:
            code: Python code to analyze

        Returns:
            Dictionary mapping package names to versions (or 'latest')

        Example:
            >>> analyzer = DependencyAnalyzer()
            >>> deps = analyzer.analyze_code_dependencies("import pandas as pd")
            >>> print(deps)
            {'pandas': 'latest'}
        """
        try:
            tree = ast.parse(code)
            imports = self._extract_imports(tree)
            third_party = self._filter_third_party(imports)
            return self._map_to_packages(third_party)
        except SyntaxError as e:
            logger.warning("Failed to parse code: %s", e)
            return {}

    def _extract_imports(self, tree: ast.AST) -> Set[str]:
        """Extract all import names from AST."""
        imports = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split(".")[0])

        return imports

    def _filter_third_party(self, imports: Set[str]) -> Set[str]:
        """Filter out standard library modules."""
        return imports - self.standard_lib_modules

    def _map_to_packages(self, imports: Set[str]) -> Dict[str, str]:
        """Map import names to package names."""
        packages = {}

        for imp in imports:
            package = self.import_to_package.get(imp, imp)
            packages[package] = "latest"  # Default to latest version

        return packages

    def _get_standard_library_modules(self) -> Set[str]:
        """Get set of Python standard library modules."""
        # Common standard library modules
        return {
            "argparse",
            "array",
            "ast",
            "asyncio",
            "atexit",
            "base64",
            "bdb",
            "binascii",
            "bisect",
            "builtins",
            "bz2",
            "cProfile",
            "calendar",
            "cgi",
            "cgitb",
            "chunk",
            "cmath",
            "cmd",
            "code",
            "codecs",
            "collections",
            "colorsys",
            "compileall",
            "concurrent",
            "configparser",
            "contextlib",
            "copy",
            "copyreg",
            "crypt",
            "csv",
            "ctypes",
            "curses",
            "dataclasses",
            "datetime",
            "dbm",
            "decimal",
            "difflib",
            "dis",
            "distutils",
            "doctest",
            "email",
            "encodings",
            "enum",
            "errno",
            "faulthandler",
            "fcntl",
            "filecmp",
            "fileinput",
            "fnmatch",
            "fractions",
            "ftplib",
            "functools",
            "gc",
            "getopt",
            "getpass",
            "gettext",
            "glob",
            "grp",
            "gzip",
            "hashlib",
            "heapq",
            "hmac",
            "html",
            "http",
            "imaplib",
            "imghdr",
            "imp",
            "importlib",
            "inspect",
            "io",
            "ipaddress",
            "itertools",
            "json",
            "keyword",
            "lib2to3",
            "linecache",
            "locale",
            "logging",
            "lzma",
            "mailbox",
            "mailcap",
            "marshal",
            "math",
            "mimetypes",
            "mmap",
            "modulefinder",
            "msilib",
            "msvcrt",
            "multiprocessing",
            "netrc",
            "nis",
            "nntplib",
            "numbers",
            "operator",
            "optparse",
            "os",
            "ossaudiodev",
            "parser",
            "pathlib",
            "pdb",
            "pickle",
            "pickletools",
            "pipes",
            "pkgutil",
            "platform",
            "plistlib",
            "poplib",
            "posix",
            "pprint",
            "profile",
            "pstats",
            "pty",
            "pwd",
            "py_compile",
            "pyclbr",
            "pydoc",
            "queue",
            "quopri",
            "random",
            "re",
            "readline",
            "reprlib",
            "resource",
            "rlcompleter",
            "runpy",
            "sched",
            "secrets",
            "select",
            "selectors",
            "shelve",
            "shlex",
            "shutil",
            "signal",
            "site",
            "smtpd",
            "smtplib",
            "sndhdr",
            "socket",
            "socketserver",
            "spwd",
            "sqlite3",
            "ssl",
            "stat",
            "statistics",
            "string",
            "stringprep",
            "struct",
            "subprocess",
            "sunau",
            "sys",
            "sysconfig",
            "syslog",
            "tabnanny",
            "tarfile",
            "telnetlib",
            "tempfile",
            "termios",
            "textwrap",
            "threading",
            "time",
            "timeit",
            "tkinter",
            "token",
            "tokenize",
            "trace",
            "traceback",
            "tracemalloc",
            "tty",
            "turtle",
            "turtledemo",
            "types",
            "typing",
            "unicodedata",
            "unittest",
            "urllib",
            "uu",
            "uuid",
            "venv",
            "warnings",
            "wave",
            "weakref",
            "webbrowser",
            "winreg",
            "winsound",
            "wsgiref",
            "xdrlib",
            "xml",
            "xmlrpc",
            "zipapp",
            "zipfile",
            "zipimport",
            "zlib",
            "zoneinfo",
        }

    def _get_import_to_package_mapping(self) -> Dict[str, str]:
        """Map import names to actual package names."""
        return {
            # Common mappings where import name differs from package name
            "bs4": "beautifulsoup4",
            "PIL": "Pillow",
            "cv2": "opencv-python",
            "yaml": "PyYAML",
            "dateutil": "python-dateutil",
            "sklearn": "scikit-learn",
            "tf": "tensorflow",
            "torch": "torch",
            "np": "numpy",
            "pd": "pandas",
            "plt": "matplotlib",
            "sns": "seaborn",
            "spacy": "spacy",
            "nltk": "nltk",
            "requests": "requests",
            "flask": "flask",
            "django": "django",
            "fastapi": "fastapi",
            "uvicorn": "uvicorn",
            "sqlalchemy": "sqlalchemy",
            "psycopg2": "psycopg2-binary",
            "redis": "redis",
            "boto3": "boto3",
            "botocore": "botocore",
            "pymongo": "pymongo",
            "scipy": "scipy",
            "sympy": "sympy",
            "plotly": "plotly",
            "bokeh": "bokeh",
            "dash": "dash",
            "streamlit": "streamlit",
            "jupyter": "jupyter",
            "ipython": "ipython",
            "pytest": "pytest",
            "black": "black",
            "flake8": "flake8",
            "mypy": "mypy",
            "pre_commit": "pre-commit",
            "gitpython": "GitPython",
            "click": "click",
            "typer": "typer",
            "rich": "rich",
            "tqdm": "tqdm",
            "joblib": "joblib",
            "dill": "dill",
            "cloudpickle": "cloudpickle",
            "xgboost": "xgboost",
            "lightgbm": "lightgbm",
            "catboost": "catboost",
            "transformers": "transformers",
            "datasets": "datasets",
            "accelerate": "accelerate",
            "diffusers": "diffusers",
            "sentence_transformers": "sentence-transformers",
            "langchain": "langchain",
            "openai": "openai",
            "anthropic": "anthropic",
            "huggingface_hub": "huggingface-hub",
            "wandb": "wandb",
            "mlflow": "mlflow",
            "optuna": "optuna",
            "ray": "ray",
            "dask": "dask",
            "polars": "polars",
            "pyarrow": "pyarrow",
            "delta": "delta-spark",
            "great_expectations": "great-expectations",
            "prefect": "prefect",
            "dagster": "dagster",
            "airflow": "apache-airflow",
            "kubernetes": "kubernetes",
            "docker": "docker",
            "blessed": "blessed",
            "curses": "windows-curses" if os.name == "nt" else "ncurses",
        }
