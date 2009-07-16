#!/usr/bin/env python
# -*- coding: utf-8 -*-

names = [
	"dispcal",
	"dispread",
	"colprof",
	"dispwin",
	"spyd2en",
	"targen"
]

prefixes_suffixes = ["argyll"]

altnames = {}
for name in names:
	if not name in altnames:
		altnames[name] = []
	for prefix_suffix in prefixes_suffixes:
		altnames[name] += ["%s-%s" % (prefix_suffix, name)]
		altnames[name] += ["%s-%s" % (name, prefix_suffix)]
	altnames[name] += [name]

viewconds = [
	"pp",
	"pe",
	"mt",
	"mb",
	"md",
	"jm",
	"jd",
	"pcd",
	"ob",
	"cx"
]
