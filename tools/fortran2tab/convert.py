#!/usr/bin/env python3
"""Wrapper to apply fortran2tab on a range of wf101 types."""

import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    if len(sys.argv) > 1:
        fortran2tab = sys.argv[1]
        if Path(fortran2tab).exists():
            for wt_type in range(1, 100000):
                process = subprocess.Popen(
                    [Path(fortran2tab).absolute(), str(wt_type)], text=True
                )
        else:
            print(
                f"Error: cannot find fortran2tab binary. "
                f"Expected it as first argument but first argument is '{fortran2tab}'"
            )
    else:
        print("Error: please provide fortran2tab binary as first argument.")
