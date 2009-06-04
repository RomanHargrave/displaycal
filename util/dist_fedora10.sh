#!/bin/sh

dist=fedora10

# Python 2.5 RPM
/usr/bin/python2.5 setup.py bdist_rpm --cfg=$dist --use-distutils 2>&1 | tee rpm-py2.5-$dist.log
