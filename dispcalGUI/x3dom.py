# -*- coding: utf-8 -*-

from __future__ import with_statement
import os
import re
import string
import urllib2

from defaultpaths import cache
from options import verbose, debug
from log import safe_print as _safe_print
from util_io import GzipFileProper
from util_str import StrList, safe_str, safe_unicode
from worker import Error
import localization as lang


class VRMLParseError(Error):
	pass


class Tag(object):

	""" X3D Tag """

	def __init__(self, tagname, **attributes):
		self.parent = None
		self.tagname = tagname
		self.children = []
		self.attributes = attributes

	def __str__(self):
		if self.parent:
			xml = []
		else:
			# Root element
			xml = ['<?xml version="1.0" encoding="UTF-8"?>\n',
				   '<!DOCTYPE X3D PUBLIC "ISO//Web3D//DTD X3D 3.0//EN" "http://www.web3d.org/specifications/x3d-3.0.dtd">\n']
		
		xml.append("<%s" % self.tagname)
		attrs = []
		for key, value in self.attributes.iteritems():
			value = value.strip().replace("<",
										  "&lt;").replace(">",
														  "&gt;").replace("&",
																		  "&amp;").replace('"',
																						   "&quot;")
			if value in ("FALSE", "TRUE"):
				value = value.lower()
			attrs.append('%s="%s"' % (key, value))
		if attrs:
			xml.append(" " + " ".join(attrs))
		xml.append(">")
		if self.children:
			xml.append("\n")
			for child in self.children:
				for line in str(child).splitlines():
					xml.append("\t" + line + "\n")
		xml.append("</%s>\n" % self.tagname)
		return "".join(xml)

	def append_child(self, child):
		child.parent = self
		self.children.append(child)


def _attrchk(attribute, token, tag, indent):
	if attribute:
		if verbose > 1 or debug:
			if tag.attributes.get(token):
				safe_print(indent, "attribute %r %r" % (token,
														tag.attributes[token]))
		attribute = False
	return attribute


def safe_print(*args, **kwargs):
	if verbose > 1 or debug:
		_safe_print(*args, **kwargs)


def vrml2x3dom(vrml, worker=None):
	""" Convert VRML to X3D """
	x3d = Tag("X3D",  **{"xmlns:xsd": "http://www.w3.org/2001/XMLSchema-instance",
						 "profile": "Full",
						 "version": "3.0",
						 "xsd:noNamespaceSchemaLocation": "http://www.web3d.org/specifications/x3d-3.0.xsd"})
	tag = Tag("Scene")
	x3d.append_child(tag)
	token = ""
	valid_token_chars = string.ascii_letters + string.digits + "_"
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
	maxi = len(vrml) - 1.0
	lastprogress = 0
	for i, c in enumerate(vrml):
		curprogress = int(i / maxi * 100)
		if worker:
			if curprogress > lastprogress:
				worker.lastmsg.write("%i%%\n" % curprogress)
			if getattr(worker, "thread_abort", False):
				return False
		if curprogress > lastprogress:
			lastprogress = curprogress
			if curprogress < 100:
				end = None
			else:
				end = "\n"
			_safe_print.write("\r%i%%" % curprogress, end=end)
		if ord(c) < 32 and c not in "\n\r\t":
			raise VRMLParseError("Parse error: Got invalid character %r" % c)
		elif c == "{":
			safe_print(indent, "start tag %r" % token)
			indent += "  "
			attribute = False
			if token:
				if token[0] not in string.ascii_letters:
					raise VRMLParseError("Invalid token", token)
			else:
				raise VRMLParseError("Parse error: Empty token")
			child = Tag(token)
			tag.append_child(child)
			tag = child
			token = ""
		elif c == "}":
			attribute = _attrchk(attribute, token, tag, indent)
			indent = indent[:-2]
			safe_print(indent, "end tag %r" % tag.tagname)
			if tag.parent:
				tag = tag.parent
			else:
				raise VRMLParseError("Parse error: Stray '}'")
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
					tag.attributes[token] = StrList()
				if not (c.strip() or tag.attributes[token]):
					continue
				tag.attributes[token] += c
		elif c not in (" ", "\n", "\r", "\t"):
			if c in valid_token_chars:
				token += c
			else:
				raise VRMLParseError("Parse error: Got invalid character %r" % c)
		elif token:
			if token[0] not in string.ascii_letters:
				raise VRMLParseError("Parse error: Invalid token", token)
			if token == "children":
				token = ""
			elif c in (" ", "\t"):
				if not attribute:
					attribute = True
					if token in tag.attributes:
						# Overwrite existing attribute
						tag.attributes[token] = StrList()
	return x3d


def vrmlfile2x3dfile(vrmlpath, x3dpath, embed=False, html=True, worker=None):
	"""
	Convert VRML file located at vrmlpath to HTML and write to x3dpath
	
	"""
	filename, ext = os.path.splitext(vrmlpath)
	if ext.lower() in (".gz", ".wrz"):
		cls = GzipFileProper
	else:
		cls = open
	with cls(vrmlpath, "rb") as vrmlfile:
		vrml = vrmlfile.read()
	if worker:
		worker.recent.write("%s %s\n" % (lang.getstr("converting"),
										 os.path.basename(vrmlpath)))
	_safe_print(lang.getstr("converting"), vrmlpath)
	filename, ext = os.path.splitext(x3dpath)
	try:
		x3d = vrml2x3dom(vrml, worker)
		if not x3d:
			_safe_print(lang.getstr("aborted"))
			return False
		if not embed or not html:
			_safe_print("Writing", x3dpath)
			with open(x3dpath, "wb") as x3dfile:
				x3dfile.write(str(x3d))
			x3d = x3dpath
		if html:
			html = x3d2html(x3d, title=os.path.basename(filename),
							embed=embed)
			_safe_print("Writing", x3dpath + ".html")
			with open(x3dpath + ".html", "wb") as htmlfile:
				htmlfile.write(html)
	except KeyboardInterrupt:
		x3d = False
	except VRMLParseError, exception:
		return exception
	except EnvironmentError, exception:
		return exception
	except Exception, exception:
		import traceback
		_safe_print(traceback.format_exc())
		return exception
	return True


def x3d2html(x3d, title="Untitled",
			 runtime_uri="http://www.x3dom.org/x3dom/release", embed=False):
	"""
	Convert X3D to HTML
	
	If embed is False (default), x3d needs to be a path to a .x3d file,
	otherwise it should be a X3D document
	
	"""
	if embed:
		# Strip XML declaration and doctype
		html = re.sub("<[?!][^>]*>\s*", "", str(x3d))
		# Get children of scene
		html = re.sub("\s*</?(X3D|Scene)(?:\s+[^>]*)?>\s*", "", html)
		# Convert uppercase letters at start of tag name to lowercase
		html = re.sub("(</?[A-Z]+)", lambda match: match.groups()[0].lower(),
					  html)
		# Indent
		html = "\n".join(["\t" * 3 + line for line in html.splitlines()])
	else:
		html = ('<inline url="%s" mapDEFToID="true" nameSpaceName="scene"></inline>' %
				os.path.basename(safe_unicode(x3d).encode("UTF-8")))
	# Strip protocol
	runtime_path = re.sub("^\w+://", "", runtime_uri)
	# domain.com -> com.domain
	runtime_path = re.sub("^(?:www\.)?(\w+)((?:\.\w+)+)", "\\2.\\1",
						  runtime_path)[1:]
	# com.domain/path -> com.domain.path
	runtime_path = re.sub("^([^/]+)/", "\\1.", runtime_path)
	cachedir = os.path.join(cache,
							os.path.join(*runtime_path.split("/")))
	if not os.path.isdir(cachedir):
		_safe_print("Creating cache directory:", cachedir)
		os.makedirs(cachedir)
	local_runtime_path = "file:///" + safe_unicode(cachedir).encode("UTF-8").lstrip("/").replace(os.path.sep, "/")
	style = '<link rel="stylesheet" href="%s/x3dom.css">' % local_runtime_path
	script = """<script src="%s/x3dom.js"></script>
		<script>
			if (!window.x3dom) {
				document.getElementById('x3d').setAttribute('swfpath', '%s/x3dom.swf');
				document.write('<link rel="stylesheet" href="%s/x3dom.css"><script src="%s/x3dom.js"><\/script>');
				
			}
		</script>""" % (local_runtime_path, runtime_uri,
			runtime_uri, runtime_uri)
	for resource in ("x3dom.css", "x3dom.js", "x3dom.swf"):
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
		else:
			uri = cachefilename
		if body.strip():
			if embed and resource != "x3dom.swf":
				if resource == "x3dom.css":
					style = "<style>%s</style>" % body
				else:
					script = "<script>%s</script>" % body
			if not os.path.isfile(cachefilename):
				with open(cachefilename, "wb") as cachefile:
					cachefile.write(body)
		else:
			_safe_print("Error: Empty document:", uri)
			if os.path.isfile(cachefilename):
				_safe_print("Removing", cachefilename)
				os.remove(cachefilename)
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
	</head>
	<body>
		<noscript><p>Please enable JavaScript</p></noscript>
		<p id="x3dom_error"></p>
		<x3d id="x3d" showStat="false" showLog="false" swfpath="%(local_runtime_path)s/x3dom.swf" x="0px" y="0px">
			<scene>
				%(html)s
			</scene>
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
					}
				}
			}
			else {
				document.getElementById('x3dom_error').innerHTML = 'X3DOM has failed loading. Please check the console for errors.';
				document.getElementById('x3dom_error').style.display = 'block';
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
			function setsize() {
				document.getElementById('x3d').setAttribute('width', document.body.offsetWidth);
				document.getElementById('x3d').setAttribute('height', document.body.offsetHeight);
			};
			window.addEventListener('resize', setsize);
			setsize();
		</script>
	</body>
</html>""" % {"title": title.encode("UTF-8"), "style": style, "script": script,
			  "runtime_uri": runtime_uri, "local_runtime_path": local_runtime_path,
			  "html": html}
