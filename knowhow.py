"""Run with Python and this file's path, from any project directory."""
import sys
sys.dont_write_bytecode = True
from access.cli import main

if __name__ == '__main__':
    raise SystemExit(main())
