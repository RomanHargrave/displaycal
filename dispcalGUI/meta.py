#!/usr/bin/env python
# -*- coding: utf-8 -*-

author = u"Florian Höch"
author_ascii = "Florian Hoech"
description = u"A graphical user interface for the Argyll CMS display calibration utilities"
domain = "dispcalGUI.hoech.net"
name = "dispcalGUI"

"""
	Play nice with distutils (from distutils.version's StrictVersion):

    The following are valid version numbers (shown in the order that
    would be obtained by sorting according to the supplied cmp function):

        0.4       0.4.0  (these two are equivalent)
        0.4.1
        0.5a1
        0.5b3
        0.5
        0.9.6
        1.0
        1.0.4a3
        1.0.4b1
        1.0.4

    The following are examples of invalid version numbers:

        1
        2.7.2.2
        1.3.a4
        1.3pl1
        1.3c4
"""

version = "0.2.5b4"
version_lin = "0.2.5b4" # Linux
version_mac = "0.2.5b4" # Mac OS X
version_win = "0.2.5b4" # Windows
version_src = "0.2.5b4-2"

version_tuple = (0, 2, 5, 0) # only ints allowed and must be exactly 4 values