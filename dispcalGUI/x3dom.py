# -*- coding: utf-8 -*-

from __future__ import with_statement
import os
import re


from options import verbose, debug
from safe_print import safe_print as _safe_print
from util_io import GzipFileProper


class Tag(object):

	""" X3D Tag """

	def __init__(self, tagname, **attributes):
		self.parent = None
		self.tagname = tagname[0].lower() + tagname[1:]
		self.children = []
		self.attributes = attributes

	def __str__(self):
		html = ["<%s" % self.tagname]
		attrs = []
		for key, value in self.attributes.iteritems():
			value = value.strip()
			if value in ("FALSE", "TRUE"):
				value = value.lower()
			attrs.append('%s="%s"' % (key, value))
		if attrs:
			html.append(" " + " ".join(attrs))
		html.append(">")
		if self.children:
			html.append("\n")
			for child in self.children:
				for line in str(child).splitlines():
					html.append("\t" + line + "\n")
		html.append("</%s>\n" % self.tagname)
		return "".join(html)

	def append_child(self, child):
		child.parent = self
		self.children.append(child)


def _attrchk(attribute, token, tag, indent):
	if attribute:
		safe_print(indent, "attribute %r %r" % (token, tag.attributes[token]))
		attribute = False
	return attribute


def safe_print(*args, **kwargs):
	if verbose > 1 or debug:
		_safe_print(*args, **kwargs)


def vrml2x3dom(vrml):
	""" Convert VRML to X3D """
	tag = Tag("scene", DEF="scene")
	token = ""
	attribute = False
	quote = 0
	listing = False
	# Remove comments
	vrml = re.sub("#[^\n\r]*", "", vrml)
	# <class> <Token> { -> <Token> {
	vrml = re.sub("\w+[ \t]+(\w+\s*\{)", "\\1", vrml)
	# Remove commas
	vrml = re.sub(",\s*", " ", vrml)
	indent = ""
	for c in vrml:
		if c == "{":
			safe_print(indent, "start tag %r" % token)
			indent += "  "
			attribute = False
			child = Tag(token)
			tag.append_child(child)
			tag = child
			token = ""
		elif c == "}":
			attribute = _attrchk(attribute, token, tag, indent)
			indent = indent[:-2]
			safe_print(indent, "end tag %r" % tag.tagname)
			tag = tag.parent
			token = ""
		elif c == "[":
			if token:
				safe_print(indent, "listing %r" % token)
				listing = True
		elif c == "]":
			attribute = _attrchk(attribute, token, tag, indent)
			token = ""
			listing = False
		elif attribute:
			if c in ("\n", "\r"):
				if listing:
					if tag.attributes.get(token):
						tag.attributes[token] += " "
				else:
					attribute = _attrchk(attribute, token, tag, indent)
					token = ""
			elif c == '"':
				quote += 1
				if quote == 2:
					attribute = _attrchk(attribute, token, tag, indent)
					quote = 0
					token = ""
			else:
				if not token in tag.attributes:
					tag.attributes[token] = ""
				if not (c.strip() or tag.attributes[token]):
					continue
				tag.attributes[token] += c
		elif c not in (" ", "\n", "\r", "\t"):
			token += c
		elif token:
			if token == "children":
				token = ""
			elif c in (" ", "\t"):
				if not attribute:
					attribute = True
					if token in tag.attributes:
						# Overwrite existing attribute
						tag.attributes[token] = ""
	return tag


def vrmlfile2x3dhtmlfile(vrmlpath, htmlpath):
	"""
	Convert VRML file located at vrmlpath to HTML and write to htmlpath
	
	"""
	filename, ext = os.path.splitext(vrmlpath)
	if ext.lower() in (".gz", ".wrz"):
		cls = GzipFileProper
	else:
		cls = open
	with cls(vrmlpath, "r") as vrmlfile:
		vrml = vrmlfile.read()
	filename, ext = os.path.splitext(vrmlpath)
	html = x3dom2html(vrml2x3dom(vrml), title=os.path.basename(filename))
	with open(htmlpath, "w") as htmlfile:
		htmlfile.write(html)


def x3dom2html(x3dom, title="Untitled",
			   runtime_uri="http://www.x3dom.org/x3dom/release"):
	""" Convert X3D to HTML """
	return """<!DOCTYPE html>
<html>
	<head>
		<meta charset="utf-8" />
		<title>%(title)s</title>
		<link rel="stylesheet" href="%(runtime_uri)s/x3dom.css">
		<script src="%(runtime_uri)s/x3dom.js"></script>
		<style>
		* {
			color: #fff;
		}
		html, body {
			background: linear-gradient(#111, #333);
			height: 100%%;
			margin: 0;
			padding: 0;
			overflow: hidden;
			text-align: center;
		}
		x3d {
			border: 0;
		}
		#no_x3dom {
			display: none;
		}
		</style>
	</head>
	<body>
		<noscript><p>Please enable JavaScript</p></noscript>
		<p id="no_x3dom">The <a href="%(runtime_uri)s">X3DOM Runtime</a> seems to have failed loading. Please make sure you have internet connectivity.</p>
		<x3d id="canvas" showStat="false" showLog="false" x="0px" y="0px">
%(html)s
		</x3d>
		<script>
		if (!window.x3dom) document.getElementById('no_x3dom').style.display = 'block';
		function setsize() {
			document.getElementById('canvas').setAttribute('width', document.body.offsetWidth);
			document.getElementById('canvas').setAttribute('height', document.body.offsetHeight);
		};
		window.addEventListener('resize', setsize);
		setsize();
		</script>
	</body>
</html>""" % {"title": title, "runtime_uri": runtime_uri,
			  "html":"\n".join(["\t" * 3 + line for line in
								str(x3dom).splitlines()])}
