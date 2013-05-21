#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import glob
import os
import re
import shutil


def main():
	dist = glob.glob(os.path.join('dist', 'dispcalGUI-*'))
	for entry in dist:
		version = re.search('\d+(?:\.\d+){3}', entry)
		if version:
			version = version.group()
			version_dir = os.path.join('dist', version)
			if not os.path.isdir(version_dir):
				os.mkdir(version_dir)
			shutil.move(entry, version_dir)


if __name__ == '__main__':
	main()
