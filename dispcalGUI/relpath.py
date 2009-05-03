#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

def relpath(path, start):
	path = os.path.abspath(path).split(os.path.sep)
	start = os.path.abspath(start).split(os.path.sep)
	if path == start:
		return "."
	elif path[:len(start)] == start:
		return os.path.sep.join(path[len(start):])
	elif start[:len(path)] == path:
		return os.path.sep.join([".."] * (len(start) - len(path)))

if __name__ == "__main__":
	abc = os.path.sep.join([os.path.sep, "a", "b", "c"])
	abcdef = os.path.sep.join([os.path.sep, "a", "b", "c", "d", "e", "f"])
	print relpath(abc, abcdef)
	print relpath(abcdef, abc)
	print relpath(abc, abc)