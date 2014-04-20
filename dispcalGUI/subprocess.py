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


_Popen = Popen
_call = call
_check_call = check_call


class Popen(_Popen):

	""" In case of an EnvironmentError when executing the child, set its
		filename to the first item of args """

	def __init__(self, *args, **kwargs):
		try:
			_Popen.__init__(self, *args, **kwargs)
		except EnvironmentError, exception:
			if not exception.filename:
				if isinstance(args[0], basestring):
					exception.filename = args[0].split()[0]
				else:
					exception.filename = args[0][0]
			raise


def call(*popenargs, **kwargs):
    return Popen(*popenargs, **kwargs).wait()


call.__doc__ = _call.__doc__


def check_call(*popenargs, **kwargs):
    retcode = call(*popenargs, **kwargs)
    cmd = kwargs.get("args")
    if cmd is None:
        cmd = popenargs[0]
    if retcode:
        raise CalledProcessError(retcode, cmd)
    return retcode


check_call.__doc__ = _check_call.__doc__
