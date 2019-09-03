# -*- coding: utf-8 -*-

from ctypes import wintypes
import ctypes


class UNICODE_STRING(ctypes.Structure):

	_fields_ = [('Length',		wintypes.USHORT),
				('MaximumLength', wintypes.USHORT),
				('Buffer',		wintypes.LPWSTR)]
