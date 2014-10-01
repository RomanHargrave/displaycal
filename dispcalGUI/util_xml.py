# -*- coding: utf-8 -*-


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
