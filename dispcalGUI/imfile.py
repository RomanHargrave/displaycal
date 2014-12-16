# -*- coding: utf-8 -*-

from __future__ import with_statement
import math
import os
import struct
import time
import zlib

from meta import name as appname


def write(data, stream_or_filename, bitdepth=16, format=None, dimensions=None):
	Image(data, bitdepth).write(stream_or_filename, format, dimensions)


class Image(object):

	""" Write 8 or 16 bit image files in DPX, PNG or TIFF format.
	
	Writing of single color images is highly optimized when using a single
	pixel as image data and setting dimensions explicitly.
	
	"""

	def __init__(self, data, bitdepth=16):
		self.bitdepth = bitdepth
		self.data = data

	def _pack(self, n):
		n = int(round(n))
		if self.bitdepth == 16:
			data = struct.pack(">H", n)
		elif self.bitdepth == 8:
			data = chr(n)
		else:
			raise ValueError("Unsupported bitdepth: %r" % self.bitdepth)
		return data

	def _write_dpx(self, stream, dimensions=None):
		# Very helpful: http://www.fileformat.info/format/dpx/egff.htm

		# Length of all headers combined
		headersizes = {"generic": 768 + 640 + 256,
					   "industry": 256 + 128}

		# Generic file header (768 bytes)
		stream.write("SDPX")  # Magic number
		stream.write(struct.pack(">I", 8192))  # Offset to image data
		stream.write("V1.0\0\0\0\0")  # ASCII version

		# Optimize for single color
		optimize = len(self.data) == 1 and len(self.data[0]) == 1 and dimensions

		# Image data
		imgdata = []
		for i, scanline in enumerate(self.data):
			for RGB in scanline:
				scanline = "".join(self._pack(v) for v in RGB)
				#if not optimize:
					## Pad lines with binary zeros so they end on 4-byte boundaries
					#scanline = scanline.ljust(int(math.ceil(len(scanline) / 4.0)) * 4, "\0")
				imgdata.append(scanline)
		imgdata = "".join(imgdata)
		if optimize:
			# Optimize for single color
			imgdata *= dimensions[0]
			## Pad lines with binary zeros so they end on 4-byte boundaries
			#imgdata = imgdata.ljust(int(math.ceil(len(imgdata) / 4.0)) * 4, "\0")
			imgdata *= dimensions[1]
			w, h = dimensions
		else:
			w, h = len(self.data[0]), len(self.data)

		# Generic file header (cont.)
		stream.write(struct.pack(">I", 8192 + len(imgdata)))  # File size
		stream.write("\0\0\0\1")  # DittoKey (1 = not same as previous frame)
		stream.write(struct.pack(">I", headersizes["generic"]))  # Generic section header length
		stream.write(struct.pack(">I", headersizes["industry"]))  # Industry-specific section header length
		stream.write(struct.pack(">I", 0))  # User-defined data length
		stream.write(os.path.basename(stream.name or "").ljust(100, "\0")[:100])  # File name
		stream.write(time.strftime("%Y:%m:%d:%H:%M:%S:+00") + "\0")  # Date & timestamp
		stream.write(appname.ljust(100, "\0"))  # Creator
		stream.write("\0" * 200)  # Project
		stream.write("\0" * 200)  # Copyright
		stream.write("\xff" * 4)  # EncryptKey 0xffffffff = not encrypted
		stream.write("\0" * 104)  # Reserved

		# Image header (640 bytes)
		stream.write("\0\0")  # Orientation 0 = left to right, top to bottom
		stream.write("\0\1")  # Number of image elements
		stream.write(struct.pack(">I", w))  # Pixels per line
		stream.write(struct.pack(">I", h))  # Lines per image element

		# Image header - image element
		stream.write("\0" * 4)  # 0 = unsigned data
		stream.write("\0" * 4)  # Reference low data code value
		stream.write("\0" * 4)  # Reference low quantity
		stream.write(struct.pack(">I", 2 ** self.bitdepth - 1))  # Reference high data code value
		stream.write("\xff" * 4)  # Reference high quantity
		stream.write(chr(50))  # Descriptor 50 = RGB
		stream.write("\0")  # Transfer 0 = user defined
		stream.write("\0")  # Colorimetric 0 = user defined
		stream.write(chr(self.bitdepth))  # BitSize
		stream.write("\0\0")  # Packing 0 = packed 32-bit words
		stream.write("\0\0")  # Encoding 0 = not encoded
		stream.write(struct.pack(">I", 8192))  # Image data offset
		stream.write("\0" * 4)  # End of line padding
		stream.write("\0" * 4)  # End of image padding
		stream.write("\0" * 32)  # Description

		# Seven additional unused image elements
		stream.write("\0" * 72 * 7)

		# Image header (cont.)
		stream.write("\0" * 52)  # Reserved

		# Orientation header (256 bytes)
		stream.write("\0" * 4)  # X offset
		stream.write("\0" * 4)  # Y offset
		stream.write("\0" * 4)  # X center
		stream.write("\0" * 4)  # Y center
		stream.write(struct.pack(">I", w))  # X original size
		stream.write(struct.pack(">I", h))  # Y original size
		stream.write(os.path.basename(stream.name or "").ljust(100, "\0")[:100])  # Source image file name
		stream.write(time.strftime("%Y:%m:%d:%H:%M:%S:+00") + "\0")  # Date & timestamp
		stream.write("\0" * 32)  # Input device name
		stream.write("\0" * 32)  # Input device serial number
		stream.write("\0" * 2 * 4)  # Border
		stream.write("\0" * 4 * 2)  # Aspect ratio
		stream.write("\0" * 28)  # Reserved

		# Film & TV info headers - not used
		stream.write("\0" * (256 + 128))

		# Padding so image data begins at 8K boundary
		stream.write("\0" * 6144)

		# Write image data
		stream.write(imgdata)

	def _write_png(self, stream, dimensions=None):
		# Header
		stream.write("\x89PNG\r\n\x1a\n")
		# IHDR image header length
		stream.write(struct.pack(">I", 13))
		# IHDR image header chunk type
		ihdr = ["IHDR"]
		# Optimize for single color
		optimize = len(self.data) == 1 and len(self.data[0]) == 1 and dimensions
		# IHDR: width, height
		if optimize:
			w, h = dimensions
		else:
			w, h = len(self.data[0]), len(self.data)
		ihdr.extend([struct.pack(">I", w), struct.pack(">I", h)])
		# IHDR: Bit depth
		ihdr.append(chr(self.bitdepth))
		# IHDR: Color type 2 (truecolor)
		ihdr.append("\2")
		# IHDR: Compression method 0 (deflate)
		ihdr.append("\0")
		# IHDR: Filter method 0 (adaptive)
		ihdr.append("\0")
		# IHDR: Interlace method 0 (none)
		ihdr.append("\0")
		ihdr = "".join(ihdr)
		stream.write(ihdr)
		stream.write(struct.pack(">I", zlib.crc32(ihdr) & 0xFFFFFFFF))
		# IDAT image data chunk type
		scanlines = []
		for i, scanline in enumerate(self.data):
			# Add a scanline, filter type 0
			scanlines.append("\0")
			for RGB in scanline:
				scanline = "".join(self._pack(v) for v in RGB)
				if optimize:
					scanline *= dimensions[0]
				scanlines.append(scanline)
		imgdata = "".join(scanlines)
		if optimize:
			imgdata *= dimensions[1]
		imgdata = zlib.compress(imgdata, 9)
		stream.write(struct.pack(">I", len(imgdata)))
		idat = ["IDAT"]
		idat.append(imgdata)
		idat = "".join(idat)
		stream.write(idat)
		stream.write(struct.pack(">I", zlib.crc32(idat) & 0xFFFFFFFF))
		# IEND chunk
		stream.write("\0" * 4)
		stream.write("IEND")
		stream.write(struct.pack(">I", zlib.crc32("IEND") & 0xFFFFFFFF))

	def _write_tiff(self, stream, dimensions=None):
		# Very helpful: http://www.fileformat.info/format/tiff/corion.htm

		# Header
		stream.write("MM\0*")  # Note: We use big-endian byte order

		# Offset of image directory
		stream.write("\0\0\0\x08")

		# Image data
		imgdata = []
		for i, scanline in enumerate(self.data):
			for RGB in scanline:
				imgdata.append("".join(self._pack(v) for v in RGB))
		imgdata = "".join(imgdata)
		if len(self.data) == 1 and len(self.data[0]) == 1 and dimensions:
			# Optimize for single color
			imgdata *= dimensions[0] * dimensions[1]
			w, h = dimensions
		else:
			w, h = len(self.data[0]), len(self.data)

		# Image file directory (IFD)

		# Tag, type, length, offset or data, is data (otherwise offset)
		ifd = [(0x100, 3, 1, w, True),  # ImageWidth
			   (0x101, 3, 1, h, True),  # ImageLength
			   (0x106, 3, 1, 2, True),  # PhotometricInterpretation
			   (0x115, 3, 1, 3, True),  # SamplesPerPixel
			   (0x117, 4, 1, len(imgdata), True)  # StripByteCounts
			   ]
		# BitsPerSample
		ifd.append((0x102, 3, 3, 10 + (len(ifd) + 2) * 12 + 4, False))
		# StripOffsets
		ifd.append((0x111, 3, 1, 10 + (len(ifd) + 1) * 12 + 4 + 6, True))

		ifd.sort()  # Must be ascending order!

		stream.write(struct.pack(">H", len(ifd)))  # Number of entries

		for tag, tagtype, length, payload, is_data in ifd:
			stream.write(struct.pack(">H", tag))
			stream.write(struct.pack(">H", tagtype))
			stream.write(struct.pack(">I", length))
			if is_data and tagtype == 3:
				# A word left-aligned in a dword
				stream.write(struct.pack(">H", payload))
				stream.write("\0\0")
			else:
				stream.write(struct.pack(">I", payload))

		# PlanarConfiguration default is 1 = RGBRGBRGB...

		# End of IFD
		stream.write("\0" * 4)

		# BitsPerSample (6 bytes)
		stream.write(struct.pack(">H", self.bitdepth) * 3)

		# Write image data
		stream.write(imgdata)

	def write(self, stream_or_filename, format=None, dimensions=None):
		if not format:
			if isinstance(stream_or_filename, basestring):
				format = os.path.splitext(stream_or_filename)[1].lstrip(".").upper()
				if format == "TIF":
					format += "F"
			else:
				format = "PNG"
		if not hasattr(self, "_write_" + format.lower()):
			raise ValueError("Unsupported format: %r" % format)
		if isinstance(stream_or_filename, basestring):
			stream = open(stream_or_filename, "wb")
		else:
			stream = stream_or_filename
		with stream:
			getattr(self, "_write_" + format.lower())(stream, dimensions)
