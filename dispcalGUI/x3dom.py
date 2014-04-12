# -*- coding: utf-8 -*-

from __future__ import with_statement
import os
import re
import urllib2

from defaultpaths import cache
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


def vrmlfile2x3dhtmlfile(vrmlpath, htmlpath, embed=False):
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
	html = x3dom2html(vrml2x3dom(vrml), title=os.path.basename(filename),
					  embed=embed)
	with open(htmlpath, "w") as htmlfile:
		htmlfile.write(html)


def x3dom2html(x3dom, title="Untitled",
			   runtime_uri="http://www.x3dom.org/x3dom/release", embed=False):
	""" Convert X3D to HTML """
	style = '<link rel="stylesheet" href="%s/x3dom.css">' % runtime_uri
	script = '<script src="%s/x3dom.js"></script>' % runtime_uri
	if embed:
		# Strip protocol
		runtime_path = re.sub("^\w+://", "", runtime_uri)
		# domain.com -> com.domain
		runtime_path = re.sub("^(?:www\.)?(\w+)((?:\.\w+)+)", "\\2.\\1",
							  runtime_path)[1:]
		# com.domain/path -> com.domain.path
		runtime_path = re.sub("^([^/]+)/", "\\1.", runtime_path)
		for resource in ("x3dom.css", "x3dom.js"):
			cachedir = os.path.join(cache,
									os.path.join(*runtime_path.split("/")))
			if not os.path.isdir(cachedir):
				_safe_print("Creating cache directory:", cachedir)
				os.makedirs(cachedir)
			cachefilename = os.path.join(cachedir, resource)
			body = ""
			if os.path.isfile(cachefilename):
				_safe_print("Using cached file:", cachefilename)
				with open(cachefilename, "rb") as cachefile:
					body = cachefile.read()
			if not body.strip():
				uri = "/".join([runtime_uri, resource])
				_safe_print("Requesting:", uri)
				response = urllib2.urlopen(uri)
				body = response.read()
				response.close()
			if body.strip():
				if resource == "x3dom.css":
					style = "<style>%s</style>" % body
				else:
					script = "<script>%s</script>" % body
				if not os.path.isfile(cachefilename):
					with open(cachefilename, "wb") as cachefile:
						cachefile.write(body)
			else:
				_safe_print("Error: Empty document:", resource)
	return """<!DOCTYPE html>
<html>
	<head>
		<meta charset="utf-8" />
		<title>%(title)s</title>
		%(style)s
		<style>
		html, body {
			background: linear-gradient(#111, #333);
			color: #fff;
			height: 100%%;
			margin: 0;
			padding: 0;
			overflow: hidden;
			text-align: center;
		}
		x3d {
			border: 0;
		}
		#x3dom_error {
			display: none;
			position: absolute;
			width: 100%%;
		}
		#x3dom_toolbar {
			background: rgba(16, 16, 16, .75);
			bottom: -30px;
			display: none;
			padding: 5px 0;
			position: absolute;
			transition: all .5s linear;
			width: 100%%;
		}
		.button, .options {
			background: linear-gradient(#ccc, #999);
			border: 0;
			border-bottom: 1px outset #999;
			border-left: 1px solid #999;
			border-top: 1px outset #999;
			color: #000;
			cursor: default;
			display: inline-block;
			line-height: 14px;
			padding: 3px;
			position: relative;
			text-shadow: 1px 1px #ccc;
			transition: all .125s linear;
			width: 14ex;
		}
		.button:first-child, .options {
			border-bottom-left-radius: 5px;
			border-left: 1px outset #999;
			border-top-left-radius: 5px;
		}
		.button:last-child, .options {
			border-bottom-right-radius: 5px;
			border-right: 1px outset #999;
			border-top-right-radius: 5px;
		}
		.options {
			border-bottom-right-radius: 0;
			display: none;
		}
		.options div {
			border-radius: 3px;
			padding: 3px;
		}
		.options div:hover {
			background: rgba(16, 16, 16, .75);
			color: #fff;
			text-shadow: 1px 1px #000;
		}
		.button:hover .options {
			bottom: -1px;
			display: block;
			left: -1px;
			position: absolute;
		}
		.selected:after {
			color: #666;
			content: ' \\25bc';
			font-size: 10px;
		}
		</style>
		%(script)s
		<script>
			if (window.x3dom) {
				x3dom.runtime.ready = function () {
					if (!document.getElementsByTagName('canvas').length) {
						document.getElementById('x3dom_error').innerHTML = 'X3DOM did not create a canvas. Please check the console for errors.';
						document.getElementById('x3dom_error').style.display = 'block';
					}
					else {
						window.x3d_runtime = document.getElementById('x3d').runtime;
						document.getElementById('x3dom_toolbar').style.display = 'block';
						document.getElementById('x3dom_toolbar').style.bottom = 0;
						x3d_runtime.fitAll()
					}
				}
			}
			function setSelected(element) {
				element.parentNode.parentNode.getElementsByClassName('selected')[0].innerHTML = element.innerHTML;
			}
			function setViewMode(mode, element) {
				x3d_runtime.getActiveBindable('NavigationInfo').setAttribute('explorationMode', mode);
				setSelected(element);
			}
			function setViewpoint(viewpoint, element) {
				x3d_runtime.showAll(viewpoint);
			}
		</script>
	</head>
	<body>
		<noscript><p>Please enable JavaScript</p></noscript>
		<p id="x3dom_error"></p>
		<x3d id="x3d" showStat="false" showLog="false" x="0px" y="0px">
%(html)s
		</x3d>
		<div id="x3dom_toolbar">
			<div class="button">
				<div class="selected">Rotate</div>
				<div class="options">
					<div onclick="setViewMode('all', this)">Rotate</div>
					<div onclick="setViewMode('pan', this)">Pan</div>
					<div onclick="setViewMode('zoom', this)">Zoom</div>
				</div>
			</div><!--
			--><div class="button" onclick="x3d_runtime.togglePoints(); this.innerHTML = this.innerHTML == 'Points' ? 'Solid' : 'Points'">Solid</div><!--
			--><div class="button">
				<div class="selected">Viewpoint</div>
				<div class="options">
					<div onclick="setViewpoint('negZ', this)">Top</div>
					<div onclick="setViewpoint('posZ', this)">Bottom</div>
					<div onclick="setViewpoint('negY', this)">Front</div>
					<div onclick="setViewpoint('posY', this)">Back</div>
					<div onclick="setViewpoint('posX', this)">Left</div>
					<div onclick="setViewpoint('negX', this)">Right</div>
				</div>
			</div><!--
			--><div class="button" onclick="x3d_runtime.fitAll()">Center &amp; fit</div><!--
			--><div class="button" onclick="x3d_runtime.resetView()">Reset</div><!--
			--><div class="button" onclick="window.open(x3d_runtime.getScreenshot())">Screenshot</div>
		</div>
		<script>
		if (!window.x3dom) {
			document.getElementById('x3dom_error').innerHTML = 'X3DOM has failed loading. Please check the console for errors.';
			document.getElementById('x3dom_error').style.display = 'block';
		}
		function setsize() {
			document.getElementById('x3d').setAttribute('width', document.body.offsetWidth);
			document.getElementById('x3d').setAttribute('height', document.body.offsetHeight);
		};
		window.addEventListener('resize', setsize);
		setsize();
		</script>
	</body>
</html>""" % {"title": title, "style": style, "script": script,
			  "runtime_uri": runtime_uri,
			  "html":"\n".join(["\t" * 3 + line for line in
								str(x3dom).splitlines()])}
