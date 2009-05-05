#!/bin/sh

# Create a bunch of distributions: A standalone executable, RPMs for Python 2.5 and 2.6, and a source RPM and tarball

# Standalone executable
./setup.py bdist_pyi -F --use-distutils > pyi.log 2>&1

# Python 2.5 RPM
/usr/bin/python2.5 setup.py bdist_rpm --binary-only --use-distutils > rpm-py2.5.log 2>&1
mkdir -p dist/python2.5
mv dist/dispcalGUI-*.rpm dist/python2.5

# Python 2.6 RPM
/usr/local/bin/python2.6 setup.py bdist_rpm --binary-only --use-distutils > rpm-py2.6.log 2>&1
mkdir -p dist/python2.6
mv dist/dispcalGUI-*.rpm dist/python2.6

# Source RPM and tarball
./setup.py bdist_rpm --source-only --use-setuptools > rpm-src.log 2>&1
