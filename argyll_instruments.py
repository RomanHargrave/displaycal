#!/usr/bin/env python
# -*- coding: utf-8 -*-

instruments = {
	# instrument names from Argyll source spectro/insttypes.c
	
	# A value of True for autocal_on_display means the instrument can be left
	# on the display for automatic sensor calibration
	
	# A value of False for autocal_on_display means the instrument must be
	# removed from the display for sensor calibration (i1 Display 1, 
	# Spectrolino/Spectroscan and i1 Monitor/Pro)
	
	# A value of None for any of the keys means unknown/not tested
	
	"Xrite DTP92": {
		"autocal_on_display": None,
		"high_res_supported": False,
		"skip_autocal_supported": None
	},
	"Xrite DTP94": {
		"autocal_on_display": None,
		"high_res_supported": False,
		"skip_autocal_supported": None
	},
	"GretagMacbeth Spectrolino": {
		"autocal_on_display": False,
		"high_res_supported": False,
		"skip_autocal_supported": True
	},
	"GretagMacbeth SpectroScan": {
		"autocal_on_display": False,
		"high_res_supported": False,
		"skip_autocal_supported": True
	},
	"GretagMacbeth SpectroScanT": {
		"autocal_on_display": False,
		"high_res_supported": False,
		"skip_autocal_supported": True
	},
	"Spectrocam": {
		"autocal_on_display": None,
		"high_res_supported": False,
		"skip_autocal_supported": None
	},
	"GretagMacbeth i1 Display": {
		"autocal_on_display": True, # FIXME: Only i1 Display 2
		"high_res_supported": False,
		"skip_autocal_supported": False # i1 Display 2 instrument access fails 
				# when using -N option to skip automatic sensor calibration
				# (dispread -D9 output: "Setting no-autocalibrate failed failed
				# with 'Unsupported function'")
	},
	"GretagMacbeth i1 Monitor": {
		"autocal_on_display": False,
		"high_res_supported": True,
		"skip_autocal_supported": True
	},
	"GretagMacbeth i1 Pro": {
		"autocal_on_display": False,
		"high_res_supported": True,
		"skip_autocal_supported": True
	},
	"X-Rite ColorMunki": {
		"autocal_on_display": None,
		"high_res_supported": False,
		"skip_autocal_supported": None
	},
	"Colorimtre HCFR": {
		"autocal_on_display": None,
		"high_res_supported": False,
		"skip_autocal_supported": None
	},
	"ColorVision Spyder2": {
		"autocal_on_display": None,
		"high_res_supported": False,
		"skip_autocal_supported": None
	},
	"Datacolor Spyder3": {
		"autocal_on_display": None,
		"high_res_supported": False,
		"skip_autocal_supported": None
	},
	"GretagMacbeth Huey": {
		"autocal_on_display": None,
		"high_res_supported": False,
		"skip_autocal_supported": None
	}
}