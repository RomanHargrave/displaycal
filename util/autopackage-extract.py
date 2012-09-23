#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys


def autopackage_extract(package):
	"""
	Extract the three parts that make up an autopackage:
	bootstrap script, metadata, and actual payload
	
	"""
	skiplines, compression, metasize, datasize, md5sum = (0, ) * 5
	with open(package, 'rb') as package_file:
		for line in package_file:
			line = line.strip()
			if line.startswith('# SkipLines'):
				skiplines = int(line.split()[2])
			elif line.startswith('# Compression'):
				compression = line.split()[2]
			elif line.startswith('# MetaSize'):
				metasize = int(line.split()[2])
			elif line.startswith('# DataSize'):
				datasize = int(line.split()[2])
			elif line.startswith('# MD5Sum'):
				md5sum = line.split()[2]
			if skiplines and compression and metasize and datasize and md5sum:
				break
		package_file.seek(0)
		linenum = 0
		scriptsize = 0
		for line in package_file:
			linenum += 1
			if linenum == skiplines:
				break
			scriptsize += len(line)
		package_file.seek(0)
		script = package_file.read(scriptsize)
		meta = package_file.read(metasize)
		data = package_file.read(datasize)
	with open('%s.sh' % package, 'wb') as script_file:
		script_file.write(script)
	with open('%s.meta.gz' % package, 'wb') as meta_file:
		meta_file.write(meta)
	with open('%s.payload.%s' % (package, compression), 'wb') as data_file:
		data_file.write(data)


if __name__ == '__main__':
	usage = "Usage: %s <package> [<package> ...] | --help" % os.path.basename(sys.argv[0])
	if not sys.argv[1:]:
		print usage
	else:
		if "--help" in sys.argv[1:]:
			print usage
			for line in autopackage_extract.__doc__.strip().splitlines():
				print line.strip()
		else:
			for arg in sys.argv[1:]:
				autopackage_extract(arg)
