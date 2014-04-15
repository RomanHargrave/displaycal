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
		return self.markup()

	def markup(self, allow_empty_element_tag=False, x3dom=False):
		markup = ["<%s" % self.tagname]
		attrs = []
		for key, value in self.attributes.iteritems():
			value = value.strip().replace("<",
										  "&lt;").replace(">",
														  "&gt;").replace("&",
																		  "&amp;").replace("'",
																						   "&#39;")
			if value in ("FALSE", "TRUE"):
				value = value.lower()
			attrs.append("%s='%s'" % (key, value))
		if attrs:
			markup.append(" " + " ".join(attrs))
		if not allow_empty_element_tag:
			markup.append(">")
		if self.children:
			if allow_empty_element_tag:
				markup.append(">")
			markup.append("\n")
			for child in self.children:
				for line in child.markup(allow_empty_element_tag,
										 x3dom).splitlines():
					markup.append("\t" + line + "\n")
		if not allow_empty_element_tag or self.children:
			# Not XML, or XML with children
			markup.append("</%s>\n" % self.tagname)
		else:
			# XML, no children
			markup.append("/>")
		if (self.tagname == "Material" and
			float(self.attributes.get("transparency",
									  "0").strip()) not in (0.0, 1.0) and x3dom):
			# Fix z-fighting in X3DOM renderer
			markup += "<DepthMode readOnly='true'></DepthMode>"
		return "".join(markup)

	def append_child(self, child):
		child.parent = self
		self.children.append(child)

	def html(self, title="Untitled", xhtml=False, embed_x3dom_runtime=False,
			 x3dom_runtime_baseuri="http://www.x3dom.org/x3dom/release"):
		"""
		Convert X3D to HTML
		
		This will generate HTML5 by default unless you set xhtml=True.
		
		If embed_x3dom_runtime is True, the X3DOM runtime will be embedded in
		the HTML (increases filesize considerably)
		
		"""
		# Get children of scene
		html = re.sub("\s*</?(X3D|Scene)(?:\s+[^>]*)?>\s*", "",
					  self.markup(xhtml, True))
		if not xhtml:
			# Convert uppercase letters at start of tag name to lowercase
			html = re.sub("(</?[A-Z]+)", lambda match: match.groups()[0].lower(),
						  html)
		# Indent
		html = "\n".join(["\t" * 2 + line for line in html.splitlines()]).lstrip()
		# Strip protocol
		runtime_path = re.sub("^\w+://", "", x3dom_runtime_baseuri)
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
		style = '<link rel="stylesheet" href="%s/x3dom.css" />' % local_runtime_path
		script = """<script src="%s/x3dom.js"></script>
		<script>
			if (!window.x3dom) {
				var stylesheet = document.createElement('link');
				stylesheet.setAttribute('rel', 'stylesheet');
				stylesheet.setAttribute('href', '%s/x3dom.css');
				document.getElementsByTagName('head')[0].insertBefore(stylesheet, document.getElementsByTagName('style')[0]);
				document.getElementById('x3d').setAttribute('swfpath', '%s/x3dom.swf');
				document.write('<script src="%s/x3dom.js"><\/script>');
				
			}
		</script>""" % (local_runtime_path, x3dom_runtime_baseuri,
				x3dom_runtime_baseuri, x3dom_runtime_baseuri)
		for resource in ("x3dom.css", "x3dom.js", "x3dom.swf"):
			cachefilename = os.path.join(cachedir, resource)
			body = ""
			if os.path.isfile(cachefilename):
				_safe_print("Using cached file:", cachefilename)
				with open(cachefilename, "rb") as cachefile:
					body = cachefile.read()
			if not body.strip():
				uri = "/".join([x3dom_runtime_baseuri, resource])
				_safe_print("Requesting:", uri)
				response = urllib2.urlopen(uri)
				body = response.read()
				response.close()
			else:
				uri = cachefilename
			if body.strip():
				if embed_x3dom_runtime and resource != "x3dom.swf":
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
		html = """<!DOCTYPE html>
<html>
	<head>
		<meta charset="utf-8" />
		<title>%(title)s</title>
		%(style)s
		<style>
		a {
			color: inherit;
		}
		html, body {
			height: 100%%;
			margin: 0;
			padding: 0;
			overflow: hidden;
		}
		body {
			background: #111;
			background: linear-gradient(#111, #333);
			color: #fff;
			font-family: sans-serif;
			font-size: 12px;
			text-align: center;
		}
		x3d, #x3dom-x3d-object {
			border: 0;
			height: 100%% !important;
			width: 100%% !important;
		}
		#x3dom_error {
			color: #ff4500;
			padding: 5px 0;
			top: -100%%;
		}
		#x3dom_error, #x3dom_logdiv {
			background: rgba(16, 16, 16, .75);
			border: 0;
			display: block !important;
			font-size: 12px;
			height: auto;
			position: absolute;
			transition: all .5s ease;
			width: 100%%;
		}
		#x3dom_logdiv {
			bottom: -100%%;
			max-height: 25%%;
			padding: 5px 0 0;
			text-align: left;
		}
		#x3dom_logdiv p {
			padding: 0 5px;
		}
		#x3dom_logdiv p:last-child {
			padding-bottom: 35px;
		}
		#x3dom_toolbar {
			bottom: -30px;
			padding: 5px 0;
			position: absolute;
			transition: all .5s ease;
			width: 100%%;
			z-index: 9999;
		}
		.button {
			display: inline-block;
			height: 14px;
			padding: 3px 0;
		}
		.button, .options {
			background: #ccc;
			background: linear-gradient(#ccc, #999);
			border: 0;
			border-bottom: 1px outset #999;
			border-left: 1px solid #999;
			border-top: 1px outset #999;
			color: #000;
			cursor: default;
			line-height: 14px;
			min-width: 15ex;
			position: relative;
			text-shadow: 1px 1px #ccc;
			transition: all .125s linear;
			-moz-user-select: none;
			-webkit-user-select: none;
			-ms-user-select: none; 
			user-select: none;
			white-space: nowrap;
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
		.mousedown:hover {
			background: linear-gradient(#999, #666);
			border-color: #666;
		}
		.options {
			border-bottom-right-radius: 0;
			display: none;
			padding: 1px 0;
		}
		.options div {
			border-radius: 3px;
			margin: 0 1px;
			padding: 2px 5px;
		}
		.options div.checked,
		.options div.unchecked {
			text-align: left;
		}
		.options div.checked:before,
		.options div.unchecked:before,
		.selected:before {
			content: '\\2022\\00a0';
		}
		.options div.unchecked:before,
		.selected:before {
			opacity: 0;
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
		.selected {
			display: inline-block;
			padding: 0 6px;
			text-align: left;
			width: 100%%;
		}
		.selected:after {
			color: #666;
			content: '\\25bc';
			font-size: 10px;
			position: absolute;
			right: 10px;
			text-align: right;
			top: 3px;
		}
		</style>
	</head>
	<body>
		<noscript><p>Please enable JavaScript</p></noscript>
		<x3d id="x3d" showStat="false" showLog="false" swfpath="%(local_runtime_path)s/x3dom.swf" x="0px" y="0px">
			<scene>
				%(html)s
			</scene>
		</x3d>
		<p id="x3dom_error"></p>
		<div id="x3dom_toolbar">
			<div class="button">
				<div class="selected">Rotate</div>
				<div class="options">
					<div class="checked" onclick="setViewMode('all', this)">Rotate</div>
					<div class="unchecked" onclick="setViewMode('pan', this)">Pan</div>
					<div class="unchecked" onclick="setViewMode('zoom', this)">Zoom</div>
				</div>
			</div><!--
			--><div class="button">
				<div class="selected">Default</div>
				<div class="options">
					<div class="unchecked" onclick="setRenderMode('lines', this)">Lines</div>
					<div class="unchecked" onclick="setRenderMode('points', this)">Points</div>
					<div class="checked" onclick="setRenderMode(1, this)">Default</div>
					<div class="unchecked" onclick="setRenderMode(.9, this)">Fade 10%%</div>
					<div class="unchecked" onclick="setRenderMode(.8, this)">Fade 20%%</div>
					<div class="unchecked" onclick="setRenderMode(.7, this)">Fade 30%%</div>
					<div class="unchecked" onclick="setRenderMode(.6, this)">Fade 40%%</div>
					<div class="unchecked" onclick="setRenderMode(.5, this)">Fade 50%%</div>
					<div class="unchecked" onclick="setRenderMode(.4, this)">Fade 60%%</div>
					<div class="unchecked" onclick="setRenderMode(.3, this)">Fade 70%%</div>
				</div>
			</div><!--
			--><div class="button">
				<div class="selected">Lights</div>
				<div class="options" id="x3dom_toolbar_lights">
					<div class="checked" onclick="toggleLights('headlight', this)">Headlight</div>
				</div>
			</div><!--
			--><div class="button">
				<div class="selected">Viewpoint</div>
				<div class="options">
					<div class="unchecked" onclick="setViewpoint('negZ')">Top</div>
					<div class="unchecked" onclick="setViewpoint('posZ')">Bottom</div>
					<div class="unchecked" onclick="setViewpoint('negY')">Front</div>
					<div class="unchecked" onclick="setViewpoint('posY')">Back</div>
					<div class="unchecked" onclick="setViewpoint('posX')">Left</div>
					<div class="unchecked" onclick="setViewpoint('negX')">Right</div>
				</div>
			</div><!--
			--><div class="button" onclick="x3d_runtime.fitAll()">Center &amp; fit</div><!--
			--><div class="button" onclick="x3d_runtime.resetView()">Reset</div><!--
			--><div class="button" onclick="window.open(x3d_runtime.getScreenshot())">Screenshot</div><!--
			--><div class="button" onclick="toggleLog()">Toggle log</div>
		</div>
		%(script)s
		<script>
			var x3d_runtime, x3d_rendermode;
			function setOpacity(opacity) {
				var nodes = document.getElementById('x3d').getElementsByTagName('material');
				for (var i = 0; i < nodes.length; i ++) {
					_opacity = nodes[i].getAttribute('_opacity');
					if (_opacity == null) {
						transparency = nodes[i].getAttribute('transparency');
						if (transparency == null) transparency = 0;
						_opacity = 1 - transparency;
						nodes[i].setAttribute('_opacity', _opacity.toString());
					}
					nodes[i].setAttribute('transparency', (1 - parseFloat(_opacity) * opacity).toString());
				}
			}
			function setRenderMode(mode, element) {
				if (mode != x3d_rendermode) {
					switch (x3d_rendermode) {
						case 'lines':
							x3d_runtime.togglePoints(true);
							break;
						case 'points':
							x3d_runtime.togglePoints();
							break;
					}
					x3d_rendermode = mode;
					switch (mode) {
						case 'lines':
							if (x3d_runtime.togglePoints(true) == 1)
								x3d_runtime.togglePoints(true);
							setOpacity(1);
							break;
						case 'points':
							x3d_runtime.togglePoints();
							setOpacity(1);
							break;
						default:
							setOpacity(mode);
					}
					element && setSelected(element);
				}
			}
			function setSelected(element) {
				var siblings = element.parentNode.getElementsByTagName('div');
				element.parentNode.parentNode.getElementsByClassName('selected')[0].innerHTML = element.innerHTML;
				for (var i = 0; i < siblings.length; i ++) siblings[i].setAttribute('class', 'unchecked');
				element.setAttribute('class', 'checked');
			}
			function setViewMode(mode, element) {
				x3d_runtime.getActiveBindable('NavigationInfo').setAttribute('explorationMode', mode);
				element && setSelected(element);
			}
			function setViewpoint(viewpoint) {
				x3d_runtime.showAll(viewpoint);
			}
			function setup() {
				if (window.x3dom) {
					var buttons = document.getElementsByClassName('button');
					for (var i = 0; i < buttons.length; i ++) {
						buttons[i].addEventListener('mousedown', function () {
							var cls = this.getAttribute('class');
							this.setAttribute('class', cls + ' mousedown');
						});
					}
					document.addEventListener('mouseup', function () {
						var elements = document.getElementsByClassName('mousedown'), cls;
						for (var i = 0; i < elements.length; i ++) {
							cls = elements[i].getAttribute('class').replace(/ mousedown$/, '');
							elements[i].setAttribute('class', cls);
						}
					});
					function fixMethod(cls, methodName, args, fix) {
						var method = cls[methodName].toString();
						method = method.replace(/^\\(?\\s*function\\s*\\([^)]*\\)\\s*{/, '');
						method = method.replace(/}\\s*\\)?$/, '');
						args.push(fix(method));
						cls[methodName] = Function.apply(Function, args);
					}
					// Fix lighting clamping
					fixMethod(x3dom.shader.DynamicShader.prototype, 'generateFragmentShader', ['gl', 'properties'], function (method) {
						for (var i = 0; i < 3; i ++) {
							method = method.replace(/(ambient|diffuse|specular)\\s*=\\s*clamp\\(\\1,\\s*0.0,\\s*1.0\\)/, '$1 = max($1, 0.0)');
							method = method.replace(/clamp\\((ambient\\s*\\+\\sdiffuse),\\s*0.0,\\s*1.0\\)/, 'max($1, 0.0)');
						}
						return method;
					});
					// Fix fontsize clamping and text positioning
					fixMethod(x3dom.Texture.prototype, 'updateText', [], function (method) {
						// Fix fontsize clamping
						method = method.replace(/\\s*if\\s*\\(font_size\\s*>\\s*\\d+\\.\\d+\\)\\s*font_size\\s*=\\s*\\d+\\.\\d+\\s*;\\n?/, '');
						// Fix text positioning
						method = method.replace(/this\.node\._mesh\._positions\[0\]\s*=\s*\[[^\]]+\]/,
												'this.node._mesh._positions[0] = [-w + w / 2, -h + h / 2, 0, w + w / 2, -h + h / 2, 0, w + w / 2, h + h / 2, 0, -w + w / 2, h + h / 2, 0]');
						return method;
					});
					//
					x3dom.runtime.ready = function () {
						// Add light toggles for existing lights
						var lights = ['directional', 'point', 'spot'];
						for (var i = 0; i < lights.length; i ++) {
							if (document.getElementById('x3d').getElementsByTagName(lights[i] + 'Light').length) {
								document.getElementById('x3dom_toolbar_lights').innerHTML += '<div class="checked" onclick="toggleLights(\\'' + lights[i] + 'Light\\', this)">' + lights[i][0].toUpperCase() + lights[i].substr(1) + '</div>';
							}
						}
						//
						document.getElementById('x3dom_toolbar').style.bottom = 0;
						x3d_runtime = document.getElementById('x3d').runtime;
						if (x3d_runtime.canvas.backend == 'flash' && !x3d_runtime.canvas.isFlashReady) toggleLog();
					}
				}
				else {
					document.getElementById('x3dom_error').innerHTML = 'ERROR: X3DOM has failed loading. Please check the console for details.';
					document.getElementById('x3dom_error').style.top = 0;
				}
			}
			function toggleLights(which, control) {
				var lights, backup;
				if (which == 'headlight') {
					backup = x3d_runtime.getActiveBindable('NavigationInfo').getAttribute('headlight') == 'false';
					x3dom.debug.logInfo('Toggling ' + which + ' = ' + (backup ? 'true' : 'false'));
					x3d_runtime.getActiveBindable('NavigationInfo').setAttribute('headlight', backup ? 'true' : 'false');
				}
				else {
					lights = document.getElementById('x3d').getElementsByTagName(which);
					if (!lights.length) x3dom.debug.logError('Cannot toggle ' + which + ': There are no ' + which + ' nodes');
					for (var i = 0; i < lights.length; i ++) {
						backup = lights[i].getAttribute('_intensity');
						x3dom.debug.logInfo('Toggling ' + which + ' ' + i + ' intensity = ' + (backup ? backup : '0'));
						if (backup) {
							lights[i].setAttribute('intensity', lights[i].getAttribute('_intensity'));
							lights[i].removeAttribute('_intensity');
						}
						else {
							lights[i].setAttribute('_intensity', lights[i].getAttribute('intensity'));
							lights[i].setAttribute('intensity', '0');
						}
					}
				}
				control && control.setAttribute('class', backup ? 'checked' : 'unchecked');
			}
			function toggleLog(show) {
				if (show == window.undefined) show = x3dom.debug.logContainer.style.bottom[0] != '0';
				x3dom.debug.logContainer.style.bottom = show !== false ? 0 : '-100%%';
				if (x3d_runtime.canvas.backend == 'flash') x3d_runtime.canvas.canvas.setAttribute('wmode', show !== false ? 'opaque' : 'direct');
			}

			setup();
		</script>
	</body>
</html>""" % {"title": title.encode("UTF-8"), "style": style,
				  "script": script,
				  "x3dom_runtime_baseuri": x3dom_runtime_baseuri,
				  "local_runtime_path": local_runtime_path, "html": html}
		if xhtml:
			html = "<?xml version='1.0' encoding='UTF-8'?>\n" + html
			html = re.sub("\s*/>", " />", html)
		else:
			html = re.sub("\s*/>", ">", html)
		return html

	def xhtml(self, *args, **kwargs):
		kwargs["xhtml"] = True
		return self.html(*args, **kwargs)
	
	def x3d(self):
		x3d = "\n".join(["<?xml version='1.0' encoding='UTF-8'?>",
						 '<!DOCTYPE X3D PUBLIC "ISO//Web3D//DTD X3D 3.0//EN" "http://www.web3d.org/specifications/x3d-3.0.dtd">',
						 self.markup(allow_empty_element_tag=True)])
		return x3d

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
						 "profile": "Immersive",
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
					if (tag.attributes.get(token) and
						tag.attributes[token][-1] != " "):
						tag.attributes[token] += " "
				else:
					attribute = _attrchk(attribute, token, tag, indent)
					token = ""
			else:
				if not token in tag.attributes:
					tag.attributes[token] = StrList()
				if not (c.strip() or tag.attributes[token]):
					continue
				if c == '"':
					quote += 1
				if c != '"' or tag.tagname != "FontStyle" or token != "style":
					if c != " " or (tag.attributes[token] and
									tag.attributes[token][-1] != " "):
						tag.attributes[token] += c
				if quote == 2:
					attribute = _attrchk(attribute, token, tag, indent)
					quote = 0
					token = ""
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


def vrmlfile2x3dfile(vrmlpath, x3dpath, html=True, embed_x3dom_runtime=False,
					 worker=None):
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
		if not html:
			_safe_print("Writing", x3dpath)
			with open(x3dpath, "wb") as x3dfile:
				x3dfile.write(x3d.x3d())
		else:
			html = x3d.html(title=os.path.basename(filename),
							embed_x3dom_runtime=embed_x3dom_runtime)
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
