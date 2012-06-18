# -*- coding: utf-8 -*-

from jsondict import JSONDict

instruments = JSONDict("argyll_instruments.json")

vendors = [
	"ColorVision",
	"Datacolor",
	"GretagMacbeth",
	"Hughski",
	"X-Rite",
	"Xrite"
]

def remove_vendor_names(txt):
	for vendor in vendors:
		txt = txt.replace(vendor, "")
	txt = txt.strip()
	return txt
