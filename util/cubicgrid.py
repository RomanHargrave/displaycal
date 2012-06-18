#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys

def create_cubic_grid(res=4, skip_grayscale=False, hires_outergamut=False):
	grid = []
	step = 100.0 / res
	for i in range(0, res + 1):
		for j in range(0, res + 1):
			for k in range(0, res + 1):
				outer = []
				inner = []
				for n in (i, j, k):
					outer.append(n * step)
					n = n * step + step / 2.0
					if n > 100:
						if not hires_outergamut:
							continue
						n = 100
					inner.append(n)
				for v in (outer, inner):
					if len(v) == 3 and (not skip_grayscale or 
											v != [v[0]] * 3):
						grid.append(v)
	if hires_outergamut:
		for i in range(0, res * 2 + 1):
			for j in range(0, res * 2 + 1):
				for k in range(0, res * 2 + 1):
					outer = []
					for n in (i, j, k):
						if 0 in (i, j, k) and \
						   (((i % 2 == 1 or j % 2 == 1 or k % 2 == 1) and 
						     ((i == j == 0 or i == k == 0 or j == k == 0) or 
						      (i == res * 2 or j == res * 2 or k == res * 2))) or 
							((i % 2 == 1 and j % 2 == 1) or 
							 (i % 2 == 1 and k % 2 == 1) or 
							 (j % 2 == 1 and k % 2 == 1))):
							outer.append(n * (step / 2.0))
					if len(outer) == 3 and (not skip_grayscale or 
											outer != [outer[0]] * 3):
						grid.append(outer)
		grid.sort()
	return grid

if __name__ == "__main__":
	if len(sys.argv) > 1:
		skip_grayscale = bool(sys.argv[2]) if len(sys.argv) > 2 else False
		hires_outergamut = bool(sys.argv[3]) if len(sys.argv) > 3 else False
		grid = create_cubic_grid(int(sys.argv[1]), skip_grayscale, hires_outergamut)
		for v in grid:
			print " ".join(str(n) for n in v)
	else:
		print "Usage: cubicgrid.py <res>"
