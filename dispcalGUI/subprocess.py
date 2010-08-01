# WRAPPER FOR PYTHON 2.5
# This module exists only to make sure that other module's imports of subprocess
# end up with a version that supports the terminate() method (introduced in
# Python 2.6)

import sys

from subprocess26 import *

if sys.platform == "win32":
	from subprocess26 import (CREATE_NEW_CONSOLE, DUPLICATE_SAME_ACCESS, 
							  INFINITE,  STARTF_USESHOWWINDOW, 
							  STARTF_USESTDHANDLES, STARTUPINFO, 
							  STD_ERROR_HANDLE, STD_INPUT_HANDLE, 
							  STD_OUTPUT_HANDLE, SW_HIDE, WAIT_OBJECT_0)
