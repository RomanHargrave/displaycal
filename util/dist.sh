#!/bin/sh

# Create a bunch of distributions: A standalone executable, RPMs for Python 2.5 and 2.6, and a source RPM and tarball

# Standalone executable
./setup.py bdist_pyi -F --use-distutils > pyi.log 2>&1

# Python 2.5 RPM
/usr/bin/python2.5 setup.py bdist_rpm --use-distutils > rpm-py2.5.log 2>&1

# Source tarball
/usr/bin/python2.5 setup.py sdist --use-setuptools > sdist.log 2>&1
