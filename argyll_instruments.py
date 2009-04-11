#!/usr/bin/env python
# -*- coding: utf-8 -*-

instruments = {
	# instrument names from Argyll source spectro/insttypes.c
	
	# spectral_supported: Does the instrument support spectral readings?
	
	# high_res_supported: Does the instrument support high-res spectral readings?
	
	# sensor_cal: Does the instrument need to calibrate its sensor by putting it
	# on a reference tile or black surface?
	# A value of False for sensor_cal means the instrument can be left
	# on the display
	# A value of True for sensor_cal means the instrument must be
	# removed from the display for sensor calibration if it cannot be skipped
	
	# skip_sensor_cal_supported: Can the sensor calibration be skipped?
	
	# A value of None for any of the keys means unknown/not tested
	
	"Xrite DTP92": {
		"spectral_supported": False,
		"high_res_supported": False,
		"sensor_cal": None,
		"skip_sensor_cal_supported": None
	},
	"Xrite DTP94": {
		"spectral_supported": False,
		"high_res_supported": False,
		"sensor_cal": False,
		"skip_sensor_cal_supported": False # DTP94 instrument access fails 
				# when using -N option to skip automatic sensor calibration
				# (dispread -D9 output: "Setting no-sensor_calibrate failed failed
				# with 'Unsupported function'")
	},
	"GretagMacbeth Spectrolino": {
		"spectral_supported": True,
		"high_res_supported": False,
		"sensor_cal": True,
		"skip_sensor_cal_supported": True
	},
	"GretagMacbeth SpectroScan": {
		"spectral_supported": True,
		"high_res_supported": False,
		"sensor_cal": True,
		"skip_sensor_cal_supported": True
	},
	"GretagMacbeth SpectroScanT": {
		"spectral_supported": True,
		"high_res_supported": False,
		"sensor_cal": True,
		"skip_sensor_cal_supported": True
	},
	"Spectrocam": {
		"spectral_supported": True,
		"high_res_supported": False,
		"sensor_cal": True,
		"skip_sensor_cal_supported": None
	},
	"GretagMacbeth i1 Display": {
		"spectral_supported": False,
		"high_res_supported": False,
		"sensor_cal": False, # FIXME: Only i1 Display 2
		"skip_sensor_cal_supported": False # i1 Display 2 instrument access fails 
				# when using -N option to skip automatic sensor calibration
				# (dispread -D9 output: "Setting no-sensor_calibrate failed failed
				# with 'Unsupported function'")
	},
	"GretagMacbeth i1 Monitor": {
		"spectral_supported": True,
		"high_res_supported": True,
		"sensor_cal": True,
		"skip_sensor_cal_supported": True
	},
	"GretagMacbeth i1 Pro": {
		"spectral_supported": True,
		"high_res_supported": True,
		"sensor_cal": True,
		"skip_sensor_cal_supported": True
	},
	"X-Rite ColorMunki": {
		"spectral_supported": True,
		"high_res_supported": None,
		"sensor_cal": True,
		"skip_sensor_cal_supported": True
	},
	"Colorimtre HCFR": {
		"spectral_supported": False,
		"high_res_supported": False,
		"sensor_cal": None,
		"skip_sensor_cal_supported": None
	},
	"ColorVision Spyder2": {
		"spectral_supported": False,
		"high_res_supported": False,
		"sensor_cal": None,
		"skip_sensor_cal_supported": None
	},
	"Datacolor Spyder3": {
		"spectral_supported": False,
		"high_res_supported": False,
		"sensor_cal": None,
		"skip_sensor_cal_supported": None
	},
	"GretagMacbeth Huey": {
		"spectral_supported": False,
		"high_res_supported": False,
		"sensor_cal": None,
		"skip_sensor_cal_supported": None
	},
	"COM2": { # dummy instrument, just for testing
		"spectral_supported": True,
		"high_res_supported": True,
		"sensor_cal": True,
		"skip_sensor_cal_supported": True
	}
}