import math, os, sys
from time import strftime

if __name__ == '__main__':
	if len(sys.argv) == 3:
		curve = []
		start = float(sys.argv[1]) / 100
		end = float(sys.argv[2]) / 100
		if start == end:
			print "ERROR: start == end"
		else:
			step = (end - start) / 255.0
			i = start
			for x in range(256):
				curve += [i]
				i += step
			if curve[-1] != end:
				curve += [end]
			print 'CAL'
			print ''
			print 'DESCRIPTOR "Argyll Device Calibration State"'
			print 'ORIGINATOR "Argyll dispcal"'
			print 'CREATED "%s"' % strftime("%a %b %d %H:%I:%S %Y")
			print 'KEYWORD "DEVICE_CLASS"'
			print 'DEVICE_CLASS "DISPLAY"'
			print ''
			print 'KEYWORD "RGB_I"'
			print 'NUMBER_OF_FIELDS 4'
			print 'BEGIN_DATA_FORMAT'
			print 'RGB_I RGB_R RGB_G RGB_B'
			print 'END_DATA_FORMAT'
			print ''
			print 'NUMBER_OF_SETS 256'
			print 'BEGIN_DATA'
			for i in range(256):
				print " ".join([str(round(col, 5)).ljust(7, '0') for col in [(1.0 / 255) * i] + [curve[i]] * 3])
			print 'END_DATA'
	else:
		print "Usage: %s start end" % os.path.basename(__file__)
		print " start, end = integer between 0 and 100"