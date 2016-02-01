# -*- coding: utf-8 -*-

"""
Parse commandline options.
"""

import sys

# use only ascii?
ascii = "--ascii" in sys.argv[1:]

# debug level (default: 0 = off)
if "-d2" in sys.argv[1:] or "--debug=2" in sys.argv[1:]:
	debug = 2
elif "-d1" in sys.argv[1:] or "--debug=1" in sys.argv[1:] or \
	 "-d" in sys.argv[1:] or "--debug" in sys.argv[1:]:
	debug = 1
else:
	debug = 0 # >= 1 prints debug messages

# use alternate patch preview in the testchart editor?
tc_use_alternate_preview = "-ap" in sys.argv[1:] or "--alternate-preview" in \
						   sys.argv[1:]

# test some features even if they are not available
test = "-t" in sys.argv[1:] or "--test" in sys.argv[1:]

test_require_sensor_cal = "-s" in sys.argv[1:] or "--test_require_sensor_cal" in sys.argv[1:]

# verbosity level (default: 1)
if "-v4" in sys.argv[1:] or "--verbose=4" in sys.argv[1:]:
	verbose = 4
elif "-v3" in sys.argv[1:] or "--verbose=3" in sys.argv[1:]:
	verbose = 3
elif "-v2" in sys.argv[1:] or "--verbose=2" in sys.argv[1:]:
	verbose = 2
elif "-v0" in sys.argv[1:] or "--verbose=0" in sys.argv[1:]:
	verbose = 0 # off
else:
	verbose = 1 # >= 1 prints some status information
