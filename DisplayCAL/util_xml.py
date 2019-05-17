# -*- coding: utf-8 -*-

try:
	from xml.etree import ElementTree as ET
except ImportError:
	pass

from ordereddict import OrderedDict


def dict2xml(d, elementname="element", pretty=True, allow_attributes=True,
			 level=0):
	indent = pretty and "\t" * level or ""
	xml = []
	attributes = []
	children = []

	if isinstance(d, (dict, list)):
		start_tag = []
		start_tag.append(indent + "<" + elementname)

		if isinstance(d, dict):
			for key, value in d.iteritems():
				if isinstance(value, (dict, list)) or not allow_attributes:
					children.append(dict2xml(value, key, pretty,
											 allow_attributes, level + 1))
				else:
					if pretty:
						attributes.append("\n" + indent)
					attributes.append(' %s="%s"' % (key, escape(unicode(value))))
		else:
			for value in d:
				children.append(dict2xml(value, "item", pretty,
										 allow_attributes, level + 1))

		start_tag.extend(attributes)
		start_tag.append(children and ">" or "/>")
		xml.append("".join(start_tag))

		if children:
			for child in children:
				xml.append(child)

			xml.append("%s</%s>" % (indent, elementname))
	else:
		xml.append("%s<%s>%s</%s>" % (indent, elementname, escape(unicode(d)),
									  elementname))

	return (pretty and "\n" or "").join(xml)


def escape(xml):
	return xml.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


class OrderedDictSimpleRepr(OrderedDict):

	def __repr__(self):
		"""
		od.__repr__() <==> repr(od)
		"""
		l = []
		for k, v in self.iteritems():
			l.append("%r: %r" % (k, v))
		return "{%s}" % ", ".join(l)


class ETreeDict(OrderedDictSimpleRepr):

	# Roughly follow "Converting Between XML and JSON"
	# https://www.xml.com/pub/a/2006/05/31/converting-between-xml-and-json.html

	def __init__(self, etree):
		OrderedDictSimpleRepr.__init__(self)
		children = len(etree)
		if etree.attrib or etree.text or children:
			self[etree.tag] = OrderedDictSimpleRepr(('@' + k, v)
													for k, v in
													etree.attrib.iteritems())
			if etree.text:
				text = etree.text.strip()
				if etree.attrib or children:
					if text:
						self[etree.tag]['#text'] = text
				else:
					self[etree.tag] = text
			if children:
				d = self[etree.tag]
				for child in etree:
					for k, v in ETreeDict(child).iteritems():
						if k in d:
							if not isinstance(d[k], list):
								d[k] = [d[k]]
							d[k].append(v)
						else:
							d[k] = v
		else:
			self[etree.tag] = None

	@property
	def json(self):
		import json
		return json.dumps(self)


class XMLDict(ETreeDict):

	def __init__(self, xml):
		etree = ET.fromstring(xml)
		ETreeDict.__init__(self, etree)
