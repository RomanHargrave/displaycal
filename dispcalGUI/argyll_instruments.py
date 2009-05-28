#!/usr/bin/env python
# -*- coding: utf-8 -*-

instruments = {
	# instrument names from Argyll source spectro/insttypes.c
	
	# spectral: Does the instrument support spectral readings?
	
	# high_res: Does the instrument support high-res spectral readings?
	
	# sensor_cal: Does the instrument need to calibrate its sensor by putting it
	# on a reference tile or black surface?
	# A value of False for sensor_cal means the instrument can be left
	# on the display
	# A value of True for sensor_cal means the instrument must be
	# removed from the display for sensor calibration if it cannot be skipped
	
	# skip_sensor_cal: Can the sensor calibration be skipped?
	
	# A value of None for any of the keys means unknown/not tested
	
	"DTP92": {
		"spectral": False,
		"high_res": False,
		"projector_mode": False,
		"sensor_cal": None,
		"skip_sensor_cal": None
	},
	"DTP94": {
		"spectral": False,
		"high_res": False,
		"projector_mode": False,
		"sensor_cal": False,
		"skip_sensor_cal": False # DTP94 instrument access fails 
				# when using -N option to skip automatic sensor calibration
				# (dispread -D9 output: "Setting no-sensor_calibrate failed failed
				# with 'Unsupported function'")
	},
	"Spectrolino": {
		"spectral": True,
		"high_res": False,
		"projector_mode": False,
		"sensor_cal": True,
		"skip_sensor_cal": True
	},
	"SpectroScan": {
		"spectral": True,
		"high_res": False,
		"projector_mode": False,
		"sensor_cal": True,
		"skip_sensor_cal": True
	},
	"SpectroScanT": {
		"spectral": True,
		"high_res": False,
		"projector_mode": False,
		"sensor_cal": True,
		"skip_sensor_cal": True
	},
	"Spectrocam": {
		"spectral": True,
		"high_res": False,
		"projector_mode": False,
		"sensor_cal": True,
		"skip_sensor_cal": None
	},
	"i1 Display": {
		"spectral": False,
		"high_res": False,
		"projector_mode": False,
		"sensor_cal": False, # FIXME: Only i1 Display 2
		"skip_sensor_cal": False # i1 Display 2 instrument access fails 
				# when using -N option to skip automatic sensor calibration
				# (dispread -D9 output: "Setting no-sensor_calibrate failed failed
				# with 'Unsupported function'")
	},
	"i1 Monitor": {
		"spectral": True,
		"high_res": True,
		"projector_mode": False,
		"sensor_cal": True,
		"skip_sensor_cal": True
	},
	"i1 Pro": {
		"spectral": True,
		"high_res": True,
		"projector_mode": False,
		"sensor_cal": True,
		"skip_sensor_cal": True
	},
	"ColorMunki": {
		"spectral": True,
		"high_res": None,
		"projector_mode": True,
		"sensor_cal": True,
		"skip_sensor_cal": True
	},
	"Colorimtre HCFR": {
		"spectral": False,
		"high_res": False,
		"projector_mode": False,
		"sensor_cal": None,
		"skip_sensor_cal": None
	},
	"Spyder2": {
		"spectral": False,
		"high_res": False,
		"projector_mode": False,
		"sensor_cal": None,
		"skip_sensor_cal": None
	},
	"Spyder3": {
		"spectral": False,
		"high_res": False,
		"projector_mode": False,
		"sensor_cal": None,
		"skip_sensor_cal": None
	},
	"Huey": {
		"spectral": False,
		"high_res": False,
		"projector_mode": False,
		"sensor_cal": None,
		"skip_sensor_cal": None
	},
	"Dummy Meter with Hires & Projector Mode": { # dummy instrument, just for testing
		"spectral": False,
		"high_res": True,
		"projector_mode": True,
		"sensor_cal": False,
		"skip_sensor_cal": False
	},
	"Dummy Spectro with Hires & Projector Mode": { # dummy instrument, just for testing
		"spectral": True,
		"high_res": True,
		"projector_mode": True,
		"sensor_cal": True,
		"skip_sensor_cal": True
	}
}

vendors = [
	"ColorVision",
	"Datacolor",
	"GretagMacbeth",
	"X-Rite",
	"Xrite"
]

def remove_vendor_names(txt):
	for vendor in vendors:
		txt = txt.replace(vendor, "")
	txt = txt.strip()
	return txt
