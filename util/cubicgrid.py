#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys

def create_cubic_grid(res=4, skip_grayscale=False):
	step = 100.0 / res
	for i in range(0, res + 1):
		for j in range(0, res + 1):
			for k in range(0, res + 1):
				outer = []
				inner = []
				for n in (i, j, k):
					outer.append(str(n * step))
					n = n * step + step / 2.0
					if n < 100:
						inner.append(str(n))
				if len(outer) == 3 and (not skip_grayscale or 
										outer != [outer[0]] * 3):
					print " ".join(outer)
				if len(inner) == 3 and (not skip_grayscale or 
										inner != [inner[0]] * 3):
					print " ".join(inner)

if __name__ == "__main__":
	if len(sys.argv) > 1:
		create_cubic_grid(int(sys.argv[1]), bool(sys.argv[2:]))
	else:
		print "Usage: cubicgrid.py <res>"
		create_cubic_grid()