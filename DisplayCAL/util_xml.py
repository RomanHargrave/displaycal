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


class ETreeDict(OrderedDict):

	def __init__(self, parent_element):
		OrderedDict.__init__(self, parent_element.items())
		for element in parent_element:
			if not element.tag in self:
				self[element.tag] = []
			self[element.tag].append(ETreeDict(element))
			text = element.text
			if text:
				text = text.strip()
				if text:
					self[element.tag].append(text)

	def __repr__(self):
		"""
		od.__repr__() <==> repr(od)
		"""
		l = []
		for k, v in self.iteritems():
			l.append("%r: %r" % (k, v))
		return "{%s}" % ", ".join(l)

	def json(self):
		# Being lazy
		return repr(self).replace("'", '"')


class XMLDict(ETreeDict):

	def __init__(self, xml):
		parent_element = ET.fromstring(xml)
		ETreeDict.__init__(self, parent_element)
