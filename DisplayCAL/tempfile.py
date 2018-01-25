# WRAPPER FOR PYTHON 2.5
# This module exists only to make sure that other module's imports of tempfile
# end up with a version that has the SpooledTemporaryFile class (introduced in
# Python 2.6)

from tempfile26 import *
from tempfile26 import _bin_openflags, _set_cloexec
