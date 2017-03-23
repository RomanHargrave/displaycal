import os
import sys

import subprocess26
from subprocess26 import Popen as _Popen, list2cmdline
from subprocess26 import _args_from_interpreter_flags


class Popen(_Popen):

	""" In case of an EnvironmentError when executing the child, set its
		filename to the first item of args """

	def __init__(self, *args, **kwargs):
		try:
			_Popen.__init__(self, *args, **kwargs)
		except EnvironmentError, exception:
			if not exception.filename:
				if isinstance(args[0], basestring):
					cmd = args[0].split()[0]
				else:
					cmd = args[0][0]
				if not os.path.isfile(cmd) or not os.access(cmd, os.X_OK):
					exception.filename = cmd
			raise

subprocess26.Popen = Popen


from subprocess26 import *
