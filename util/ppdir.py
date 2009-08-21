#!/usr/bin/env python
# -*- coding: utf-8 -*-

brackets = {
	dict: "{}",
	list: "[]",
	tuple: "()"
}

def ppdir(obj, types=None, level=1):
	""" Pretty-print object attributes """
	if isinstance(obj, (dict, list, tuple)):
		print brackets[obj.__class__][0]
		bag = obj
	else:
		bag = dir(obj)
	for stuff in bag:
		if isinstance(obj, dict):
			item = obj[stuff]
		elif isinstance(obj, (list, tuple)):
			item = stuff
		else:
			item = getattr(obj, stuff)
		if types:
			match = False
			for type_ in types:
				if isinstance(item, type_):
					match = True
					break
			if not match:
				continue
		print ("    " * level) + (
			((repr(stuff) if level else unicode(stuff)) + ":")
			if item != stuff else ""
		),
		if isinstance(item, (str, unicode, int, float)):
			if isinstance(item, (str, unicode)) and "\n" in item:
				print '"""' + item + '"""' + ("," if level else "")
			else:
				print repr(item) + ("," if level else "")
		elif isinstance(item, (dict, list, tuple)):
			if len(("    " * level) + repr(item)) < 80:
				print repr(item) + ("," if level else "")
			else:
				#print brackets[item.__class__][0]
				ppdir(item, types, level=level+1)
				#print ("    " * level) + brackets[item.__class__][1] + ("," if level else "")
		else:
			print repr(item) + ("," if level else "")
	if isinstance(obj, (dict, list, tuple)):
		print ("    " * (level - 1)) + brackets[obj.__class__][1] + ("," if level - 1 else "")
		bag = obj