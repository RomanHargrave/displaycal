#!/usr/bin/env python
# -*- coding: utf-8 -*-

from time import strftime
import codecs
import os
import re
import shutil
import sys

from config import get_data_path, initcfg
from meta import version
from safe_print import safe_print
import jspacker
import localization as lang


def create(report_path, placeholders2data):
	""" Create a report with all placeholders substituted by data. """
	# read report template
	report_html_template_path = get_data_path(os.path.join("report", 
														   "report.html"))
	if not report_html_template_path:
		raise IOError(lang.getstr("file.missing", 
								  report_html_template_path))
	try:
		report_html_template = codecs.open(report_html_template_path, "r", 
										   "UTF-8")
	except (IOError, OSError), exception:
		raise exception.__class__(lang.getstr("error.file.open", 
											  report_html_template_path))
	report_html = report_html_template.read()
	report_html_template.close()
	
	# create report
	for placeholder, data in placeholders2data.iteritems():
		report_html = report_html.replace(placeholder, data)
	
	for include in ("base.css", "compare.css", "compare-dark-light.css", 
					"compare-dark.css", "compare-light.css", 
					"compare-light-dark.css", "print.css", 
					"jsapi-packages.js", "jsapi-patches.js", 
					"compare.constants.js", "compare.variables.js", 
					"compare.functions.js", "compare.init.js"):
		path = get_data_path(os.path.join("report", include))
		if not path:
			raise IOError(lang.getstr("file.missing", include))
		try:
			f = codecs.open(path, "r", "UTF-8")
		except (IOError, OSError), exception:
			raise exception.__class__(lang.getstr("error.file.open", path))
		if include.endswith(".js"):
			packer = jspacker.JavaScriptPacker()
			report_html = report_html.replace('src="%s">' % include, 
											  ">/*<![CDATA[*/\n" + 
											  packer.pack(f.read(), 
														  62, 
														  True).strip() + 
											  "\n/*]]>*/")
		else:
			report_html = report_html.replace('@import "%s";' % include, 
											  f.read().strip())
		f.close()
	
	# write report
	try:
		report_html_file = codecs.open(report_path, "w", "UTF-8")
	except (IOError, OSError), exception:
		raise exception.__class__(lang.getstr("error.file.create", save_path))
	report_html_file.write(report_html)
	report_html_file.close()


def update(report_path):
	""" Update existing report with current template files. 
	
	Also creates a backup copy of the old report.
	
	"""
	# read original report
	try:
		orig_report = codecs.open(report_path, "r", "UTF-8")
	except (IOError, OSError), exception:
		raise exception.__class__(lang.getstr("error.file.open", report_path))
	orig_report_html = orig_report.read()
	orig_report.close()
	
	data = (("${PLANCKIAN}", 
			 'id="FF_planckian"\s*(.*?)\s*disabled="disabled"', 0),
			("${DISPLAY}", '"FF_display"\s*value="(.+?)"\s\/>', 0),
			("${INSTRUMENT}", '"FF_instrument"\s*value="(.+?)"\s\/>', 0),
			("${CORRECTION_MATRIX}", 
			 '"FF_correction_matrix"\s*value="(.+?)"\s\/>', 0),
			("${WHITEPOINT}", '"FF_whitepoint"\s*value="(.+?)"\s\/>', 0),
			("${WHITEPOINT_NORMALIZED}", 
			 '"FF_whitepoint_normalized"\s*value="(.+?)"\s\/>', 0),
			("${PROFILE}", '"FF_profile"\s*value="(.+?)"\s\/>', 0),
			("${PROFILE_WHITEPOINT}", 
			 '"FF_profile_whitepoint"\s*value="(.+?)"\s\/>', 0),
			("${PROFILE_WHITEPOINT_NORMALIZED}", 
			 '"FF_profile_whitepoint_normalized"\s*value="(.+?)"\s\/>', 0),
			("${TESTCHART}", '"FF_testchart"\s*value="(.+?)"\s\/>', 0),
			("${ADAPTION}", '"FF_adaption"\s*value="(.+?)"\s\/>', 0),
			("${DATETIME}", '"FF_datetime"\s*value="(.+?)"\s\/>', 0),
			("${REF}", '"FF_data_ref"\s*value="(.+?)"\s\/>', re.DOTALL),
			("${MEASURED}", '"FF_data_in"\s*value="(.+?)"\s\/>', re.DOTALL),
			("${CAL_ENTRYCOUNT}", "CAL_ENTRYCOUNT\s*=\s*(.+?);", 0),
			("${CAL_RGBLEVELS}", "CAL_RGBLEVELS\s*=\s*(.+?);", 0),
			("${GRAYSCALE}", "CRITERIA_GRAYSCALE\s*=\s*(.+?);", 0))
	
	placeholders2data = {"${REPORT_VERSION}": version}
	
	for placeholder, pattern, flags in data:
		result = re.search(pattern, orig_report_html, flags)
		placeholders2data[placeholder] = result.groups()[0] if result else ""
	
	# backup original report
	shutil.copy2(report_path, "%s.%s" % (report_path, 
										 strftime("%Y-%m-%d_%H-%M-%S")))
	
	create(report_path, placeholders2data)


if __name__ == "__main__":
	initcfg()
	lang.init()
	if not sys.argv[1:]:
		safe_print("Update existing report(s) with current template files.")
		safe_print("Usage: %s report1.html [report2.html...]" % 
				   os.path.basename(sys.argv[0]))
	else:
		for arg in sys.argv[1:]:
			try:
				update(arg)
			except (IOError, OSError), exception:
				safe_print(exception.args[0])