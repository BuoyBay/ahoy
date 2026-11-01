#!/usr/bin/env python3
"""Internal recipe planner/actions for the native ahoy build executor."""
import sys
sys.dont_write_bytecode = True
if sys.version_info < (3, 10):
    print('ahoy build requires Python 3.10+', file=sys.stderr)
    raise SystemExit(2)
from buoydev.build import main

if __name__ == '__main__':
    raise SystemExit(main())
