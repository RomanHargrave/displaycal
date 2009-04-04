#!/usr/bin/env python
# -*- coding: utf-8 -*-

instruments = {
	# instrument names from Argyll source spectro/insttypes.c
	
	# sensor_cal: Does the instrument need to calibrate its sensor?
	# high_res_supported: Does the instrument support a high-res spectral mode?
	# skip_sensor_cal_supported: Can the sensor calibration be skipped?
	
	# A value of False for sensor_cal means the instrument can be left
	# on the display
	
	# A value of True for sensor_cal means the instrument must be
	# removed from the display for sensor calibration if it cannot be skipped
	
	# A value of None for any of the keys means unknown/not tested
	
	"Xrite DTP92": {
		"sensor_cal": None,
		"high_res_supported": False,
		"skip_sensor_cal_supported": None
	},
	"Xrite DTP94": {
		"sensor_cal": False,
		"high_res_supported": False,
		"skip_sensor_cal_supported": False # DTP94 instrument access fails 
				# when using -N option to skip automatic sensor calibration
				# (dispread -D9 output: "Setting no-sensor_calibrate failed failed
				# with 'Unsupported function'")
	},
	"GretagMacbeth Spectrolino": {
		"sensor_cal": True,
		"high_res_supported": False,
		"skip_sensor_cal_supported": True
	},
	"GretagMacbeth SpectroScan": {
		"sensor_cal": True,
		"high_res_supported": False,
		"skip_sensor_cal_supported": True
	},
	"GretagMacbeth SpectroScanT": {
		"sensor_cal": True,
		"high_res_supported": False,
		"skip_sensor_cal_supported": True
	},
	"Spectrocam": {
		"sensor_cal": None,
		"high_res_supported": False,
		"skip_sensor_cal_supported": None
	},
	"GretagMacbeth i1 Display": {
		"sensor_cal": False, # FIXME: Only i1 Display 2
		"high_res_supported": False,
		"skip_sensor_cal_supported": False # i1 Display 2 instrument access fails 
				# when using -N option to skip automatic sensor calibration
				# (dispread -D9 output: "Setting no-sensor_calibrate failed failed
				# with 'Unsupported function'")
	},
	"GretagMacbeth i1 Monitor": {
		"sensor_cal": True,
		"high_res_supported": True,
		"skip_sensor_cal_supported": True
	},
	"GretagMacbeth i1 Pro": {
		"sensor_cal": True,
		"high_res_supported": True,
		"skip_sensor_cal_supported": True
	},
	"X-Rite ColorMunki": {
		"sensor_cal": True,
		"high_res_supported": None,
		"skip_sensor_cal_supported": True
	},
	"Colorimtre HCFR": {
		"sensor_cal": None,
		"high_res_supported": False,
		"skip_sensor_cal_supported": None
	},
	"ColorVision Spyder2": {
		"sensor_cal": None,
		"high_res_supported": False,
		"skip_sensor_cal_supported": None
	},
	"Datacolor Spyder3": {
		"sensor_cal": None,
		"high_res_supported": False,
		"skip_sensor_cal_supported": None
	},
	"GretagMacbeth Huey": {
		"sensor_cal": None,
		"high_res_supported": False,
		"skip_sensor_cal_supported": None
	}
}