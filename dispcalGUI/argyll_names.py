#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Argyll CMS tools used by dispcalGUI
names = [
	"ccxxmake",
	"dispcal",
	"dispread",
	"colprof",
	"dispwin",
	"xicclu",
	"spotread",
	"spyd2en",
	"targen",
	"txt2ti3",
	"i1d3ccss"
]

# Argyll CMS tools optionally used by dispcalGUI
optional = ["ccxxmake", "i1d3ccss"]

prefixes_suffixes = ["argyll"]

# Alternative tool names (from older Argyll CMS versions or with filename 
# prefix/suffix like on some Linux distros)
altnames = {"txt2ti3": ["logo2cgats"], 
			"icclu": ["xicclu"],
			"ccxxmake": ["ccmxmake"]}

def add_prefixes_suffixes(name, altname):
	for prefix_suffix in prefixes_suffixes:
		altnames[name] += ["%s-%s" % (altname, prefix_suffix)]
		altnames[name] += ["%s-%s" % (prefix_suffix, altname)]

# Automatically populate the alternative tool names with prefixed/suffixed
# versions
for name in names:
	if not name in altnames:
		altnames[name] = []
	_altnames = list(altnames[name])
	for altname in _altnames:
		add_prefixes_suffixes(name, altname)
	altnames[name] += [name]
	add_prefixes_suffixes(name, name)
	altnames[name].reverse()

# Viewing conditions supported by colprof (only predefined choices)
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

# Intents supported by colprof
intents = ["a", "aa", "aw", "la", "ms", "p", "pa", "r", "s"]  # pa = Argyll >= 1.3.3
