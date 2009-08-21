#!/usr/bin/env python
# -*- coding: utf-8 -*-

import decimal
Decimal = decimal.Decimal

def stripzeros(n):
	"""
	Strip zeros and convert to decimal.
	
	Will always return the shortest decimal representation
	(1.0 becomes 1, 1.234567890 becomes 1.23456789).
	
	"""
	n = str(n)
	if n.find(".") < 0:
		n += "."
	try:
		n = Decimal(n.rstrip("0"))
	except decimal.InvalidOperation, exception:
		pass
	return n
