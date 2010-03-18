#!/usr/bin/env python
# -*- coding: utf-8 -*-

names = [
	"dispcal",
	"dispread",
	"colprof",
	"dispwin",
	"icclu",
	"spotread",
	"spyd2en",
	"targen",
	"txt2ti3"
]

prefixes_suffixes = ["argyll"]

altnames = {"txt2ti3": ["logo2cgats"], 
			"icclu": ["xicclu"]}

def add_prefixes_suffixes(name, altname):
	for prefix_suffix in prefixes_suffixes:
		altnames[name] += ["%s-%s" % (altname, prefix_suffix)]
		altnames[name] += ["%s-%s" % (prefix_suffix, altname)]

for name in names:
	if not name in altnames:
		altnames[name] = []
	_altnames = list(altnames[name])
	for altname in _altnames:
		add_prefixes_suffixes(name, altname)
	altnames[name] += [name]
	add_prefixes_suffixes(name, name)
	altnames[name].reverse()

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
