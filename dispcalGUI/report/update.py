#!/usr/bin/env python
# -*- coding: utf-8 -*-

from time import strftime
import codecs
import os
import re
import shutil
import sys
sys.path.insert(0, "..")

from config import get_data_path, initcfg
from safe_print import safe_print
import jspacker
import localization as lang


def subst(report):
	# read original report
	try:
		orig_report = codecs.open(report, "r", "UTF-8")
	except (IOError, OSError), exception:
		safe_print(lang.getstr("error.file.open", 
							   report))
		return
	orig_report_html = orig_report.read()
	orig_report.close()
	
	# read report template
	report_html_template_path = get_data_path(os.path.join("report", 
														   "report.html"))
	if not report_html_template_path:
		safe_print(lang.getstr("file.missing", 
							   report_html_template_path))
		return
	try:
		report_html_template = codecs.open(report_html_template_path, "r", 
									   "UTF-8")
	except (IOError, OSError), exception:
		safe_print(lang.getstr("error.file.open", 
							   report_html_template_path))
		return
	report_html = report_html_template.read()
	report_html_template.close()
	
	# create report
	report_html = report_html.replace("${PLANCKIAN}", 
									  re.search('id="FF_planckian"\s*(.*?)\s*disabled="disabled"', 
												orig_report_html).groups()[0])
	report_html = report_html.replace("${DISPLAY}", 
									  re.search('"FF_display"\s*value="(.+?)"\s\/>', 
												orig_report_html).groups()[0])
	report_html = report_html.replace("${INSTRUMENT}", 
									  re.search('"FF_instrument"\s*value="(.+?)"\s\/>', 
												orig_report_html).groups()[0])
	report_html = report_html.replace("${WHITEPOINT}", 
									  re.search('"FF_whitepoint"\s*value="(.+?)"\s\/>', 
												orig_report_html).groups()[0])
	report_html = report_html.replace("${WHITEPOINT_NORMALIZED}", 
									  re.search('"FF_whitepoint_normalized"\s*value="(.+?)"\s\/>', 
												orig_report_html).groups()[0])
	report_html = report_html.replace("${PROFILE}", 
									  re.search('"FF_profile"\s*value="(.+?)"\s\/>', 
												orig_report_html).groups()[0])
	report_html = report_html.replace("${PROFILE_WHITEPOINT}", 
									  re.search('"FF_profile_whitepoint"\s*value="(.+?)"\s\/>', 
												orig_report_html).groups()[0])
	report_html = report_html.replace("${PROFILE_WHITEPOINT_NORMALIZED}", 
									  re.search('"FF_profile_whitepoint_normalized"\s*value="(.+?)"\s\/>', 
												orig_report_html).groups()[0])
	report_html = report_html.replace("${TESTCHART}", 
									  re.search('"FF_testchart"\s*value="(.+?)"\s\/>', 
												orig_report_html).groups()[0])
	report_html = report_html.replace("${ADAPTION}", 
									  re.search('"FF_adaption"\s*value="(.+?)"\s\/>', 
												orig_report_html).groups()[0])
	report_html = report_html.replace("${DATETIME}", 
									  re.search('"FF_datetime"\s*value="(.+?)"\s\/>', 
												orig_report_html).groups()[0])
	report_html = report_html.replace("${REF}", 
									  re.search('"FF_data_ref"\s*value="(.+?)"\s\/>', 
												orig_report_html,
												re.DOTALL).groups()[0])
	report_html = report_html.replace("${MEASURED}", 
									  re.search('"FF_data_in"\s*value="(.+?)"\s\/>', 
												orig_report_html,
												re.DOTALL).groups()[0])
	report_html = report_html.replace("${CAL_ENTRYCOUNT}", 
									  re.search("CAL_ENTRYCOUNT\s*=\s*(.+?);", 
												orig_report_html).groups()[0])
	report_html = report_html.replace("${CAL_RGBLEVELS}", 
									  re.search("CAL_RGBLEVELS\s*=\s*(.+?);", 
												orig_report_html).groups()[0])
	report_html = report_html.replace("${GRAYSCALE}", 
									  re.search("CRITERIA_GRAYSCALE\s*=\s*(.+?);", 
												orig_report_html).groups()[0])
	for include in ("base.css", "compare.css", "compare-dark-light.css", 
					"compare-dark.css", "compare-light.css", 
					"compare-light-dark.css", "print.css", 
					"jsapi-packages.js", "jsapi-patches.js", 
					"compare.constants.js", "compare.variables.js", 
					"compare.functions.js", "compare.init.js"):
		path = get_data_path(os.path.join("report", include))
		if not path:
			safe_print(lang.getstr("file.missing", include))
			return
		try:
			f = codecs.open(path, "r", "UTF-8")
		except (IOError, OSError), exception:
			safe_print(lang.getstr("error.file.open", path))
			return
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
	
	# backup original report
	shutil.move(report, "%s.%s" % (report, strftime("%Y-%m-%d_%H-%M-%S")))
	
	# write report
	try:
		report_html_file = codecs.open(report, "w", "UTF-8")
	except (IOError, OSError), exception:
		safe_print(lang.getstr("error.file.create", save_path))
		return
	report_html_file.write(report_html)
	report_html_file.close()


if __name__ == "__main__":
	initcfg()
	lang.init()
	if not sys.argv[1:]:
		safe_print("Update existing report(s) with current template files.")
		safe_print("Usage: %s report1.html [report2.html...]" % 
				   os.path.basename(sys.argv[0]))
	else:
		for arg in sys.argv[1:]:
			subst(arg)