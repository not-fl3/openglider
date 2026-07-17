#!/bin/env python

from optparse import OptionParser
from pathlib import Path
import sys
import unittest


SCRIPT_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_ROOT.parent

import openglider

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test() -> None:
    parser = OptionParser()
    parser.add_option("-n", "--num", default=1, help="Number of loops")
    parser.add_option("-a", "--run_all", action='store_true', help="Run all tests (including visual)")
    parser.add_option("-p", "--pattern", help="Run a custom Pattern to find")
    parser.add_option("-f", "--folder", default=".")
    parser.add_option("-v", "--verbose", default=0)

    args = parser.parse_args()[0]

    if args.pattern:
        pattern = args.pattern
    elif args.run_all:
        pattern = "*test*.py"
    else:
        pattern = "test*.py"

    start_dir = SCRIPT_ROOT / args.folder
    loader = unittest.TestLoader().discover(str(start_dir), pattern)

    for i in range(int(args.num)):
        print("\n\n>>> Running ("+str(i+1)+"/"+str(args.num)+")")
        test_results = unittest.TextTestRunner(verbosity=int(args.verbose)).run(loader)
        #print(">>> Errors: " + str(test_results.errors))
        #print(">>> Failures: " + str(test_results.failures))

    print("return: "+str(not test_results.wasSuccessful()))
    sys.exit(not test_results.wasSuccessful())

def test_typings() -> int:
    import mypy.api
    stdout, _, return_value = mypy.api.run([
        "--config-file",
        str(PROJECT_ROOT / "mypy.ini"),
        str(PROJECT_ROOT / "openglider"),
    ])
    print(stdout)
    return return_value
    
if __name__ == "__main__":
    typing_result = test_typings()
    test_result = test()

    if typing_result != 0 or test_result != 0:
        sys.exit(1)
