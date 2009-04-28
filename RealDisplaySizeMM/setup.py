#!/usr/bin/env python
# -*- coding: utf-8 -*-

import _setup, os, subprocess as sp, sys

if sys.platform == 'darwin' and not 'clean' in sys.argv and not '--help' in sys.argv and not '--help-commands' in sys.argv:
	p = sp.Popen([sys.executable, '_setup.py'] + sys.argv[1:], stdout = sp.PIPE, stderr = sp.STDOUT)
	lines = []
	while True:
		o = p.stdout.readline()
		if o == '' and p.poll() != None:
			break
		if o[0:4] == 'gcc ':
			lines += [o]
		print o.rstrip()
	if len(lines):
		os.environ['MACOSX_DEPLOYMENT_TARGET'] = '10.3'
		sp.call(lines[-1], shell = True) # fix the library
		if 'install' in sys.argv:
			_setup._setup() # install the fixed library
else:
	_setup._setup()