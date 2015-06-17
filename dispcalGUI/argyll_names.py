# -*- coding: utf-8 -*-

# Argyll CMS tools used by dispcalGUI
names = [
	"applycal",
	"average",
	"cctiff",
	"ccxxmake",
	"dispcal",
	"dispread",
	"collink",
	"colprof",
	"dispwin",
	"fakeread",
	"iccgamut",
	"icclu",
	"xicclu",
	"spotread",
	"spyd2en",
	"spyd4en",
	"targen",
	"tiffgamut",
	"txt2ti3",
	"i1d3ccss",
	"viewgam",
	"oeminst",
	"profcheck"
]

# Argyll CMS tools optionally used by dispcalGUI
optional = ["applycal", "average", "cctiff", "ccxxmake", "i1d3ccss", "oeminst",
			"spyd2en", "spyd4en", "tiffgamut"]

prefixes_suffixes = ["argyll"]

# Alternative tool names (from older Argyll CMS versions or with filename 
# prefix/suffix like on some Linux distros)
altnames = {"txt2ti3": ["logo2cgats"], 
			"icclu": ["xicclu"],
			"ccxxmake": ["ccmxmake"],
			"i1d3ccss": ["oeminst"],
			"spyd2en": ["oeminst"],
			"spyd4en": ["oeminst"]}

def add_prefixes_suffixes(name, altname):
	for prefix_suffix in prefixes_suffixes:
		altnames[name].append("%s-%s" % (altname, prefix_suffix))
		altnames[name].append("%s-%s" % (prefix_suffix, altname))

# Automatically populate the alternative tool names with prefixed/suffixed
# versions
for name in names:
	if not name in altnames:
		altnames[name] = []
	_altnames = list(altnames[name])
	for altname in _altnames:
		add_prefixes_suffixes(name, altname)
	altnames[name].append(name)
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

# Video input/output encodings supported by collink (Argyll >= 1.6)
video_encodings = ["n", "t", "6", "7", "5", "2", "C", "x", "X"]

# Observers
observers = ["1931_2", "1955_2", "1964_10", "1964_10c", "1978_2", "shaw"]
