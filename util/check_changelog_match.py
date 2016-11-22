#!/usr/bin/env python2
# -*- coding: utf-8 -*-

from __future__ import with_statement
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from DisplayCAL.meta import domain
from DisplayCAL.util_str import safe_unicode

tplpth = os.path.join(os.path.dirname(__file__), "..", "misc",
					  "README.template.html")
with open(tplpth, "r") as tpl:
	readme = safe_unicode(tpl.read(), "utf-8")

chglog = re.search('<div id="(?:changelog|history)">'
				   '.+?<h2>.+?</h2>'
				   '.+?<dl>.+?</dd>', readme, re.S)
if chglog:
	chglog = chglog.group()
	chglog = re.sub('<div id="(?:changelog|history)">', "", chglog)
	chglog = re.sub("<\/?d[l|d]>", "", chglog)
	chglog = re.sub("<(?:h2|dt)>.+?</(?:h2|dt)>", "", chglog)
	chglog = re.sub("<h3>.+?</h3>", "", chglog)
if chglog:
	chglog = re.sub(re.compile(r"<h\d>(.+?)</h\d>",
							   flags=re.I | re.S),
					r"<p><strong>\1</strong></p>", chglog)
	chglog = re.sub(re.compile('href="(#[^"]+)"', flags=re.I),
					r'href="https://%s/\1"' % domain, chglog)

	print chglog.encode(sys.stdout.encoding, "replace")
