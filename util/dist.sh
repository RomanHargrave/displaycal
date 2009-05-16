#!/bin/sh

# Create a bunch of distributions: A standalone executable, RPMs for Python 2.5 and 2.6, and a source RPM and tarball

# Standalone executable
./setup.py bdist_pyi -F --use-distutils 2>&1 | tee pyi.log

# Python 2.5 RPM
/usr/bin/python2.5 setup.py bdist_rpm --use-distutils 2>&1 | tee rpm-py2.5.log

# Source tarball
./setup.py sdist --use-setuptools 2>&1 | tee sdist.log
