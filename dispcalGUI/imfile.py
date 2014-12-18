# -*- coding: utf-8 -*-

from __future__ import with_statement
import math
import os
import struct
import time
import zlib

from meta import name as appname, version


def write(data, stream_or_filename, bitdepth=16, format=None, dimensions=None,
		  extrainfo=None):
	Image(data, bitdepth, extrainfo).write(stream_or_filename, format, dimensions)


class Image(object):

	""" Write 8 or 16 bit image files in DPX, PNG or TIFF format.
	
	Writing of single color images is highly optimized when using a single
	pixel as image data and setting dimensions explicitly.
	
	"""

	def __init__(self, data, bitdepth=16, extrainfo=None):
		self.bitdepth = bitdepth
		self.data = data
		self.extrainfo = extrainfo or {}

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
		# http://www.simplesystems.org/users/bfriesen/dpx/S268M_Revised.pdf

		# Generic file header (768 bytes)
		stream.write("SDPX")  # Magic number
		stream.write(struct.pack(">I", 8192))  # Offset to image data
		stream.write("V2.0\0\0\0\0")  # ASCII version

		# Optimize for single color
		optimize = len(self.data) == 1 and len(self.data[0]) == 1 and dimensions

		# Image data
		imgdata = []
		# 10-bit code adapted from GraphicsMagick dpx.c:WriteSamples
		if self.bitdepth == 10:
			shifts = (22, 12, 2)  # RGB
		for i, scanline in enumerate(self.data):
			if self.bitdepth == 10:
				packed = []
				for RGB in scanline:
					packed_u32 = 0
					for datum, sample in enumerate(RGB):
						packed_u32 |= (sample << shifts[datum])
					packed.append(struct.pack(">I", packed_u32))
				scanline = "".join(packed)
			else:
				scanline = "".join("".join(self._pack(v) for v in RGB) for RGB in
								   scanline)
			if not optimize:
				# Pad lines with binary zeros so they end on 4-byte boundaries
				scanline = scanline.ljust(int(math.ceil(len(scanline) / 4.0)) * 4, "\0")
			imgdata.append(scanline)
		imgdata = "".join(imgdata)
		if optimize:
			# Optimize for single color
			imgdata *= dimensions[0]
			# Pad lines with binary zeros so they end on 4-byte boundaries
			imgdata = imgdata.ljust(int(math.ceil(len(imgdata) / 4.0)) * 4, "\0")
			imgdata *= dimensions[1]
			w, h = dimensions
		else:
			w, h = len(self.data[0]), len(self.data)

		# Generic file header (cont.)
		stream.write(struct.pack(">I", 8192 + len(imgdata)))  # File size
		stream.write("\0\0\0\1")  # DittoKey (1 = not same as previous frame)
		stream.write(struct.pack(">I", 768 + 640 + 256))  # Generic section header length
		stream.write(struct.pack(">I", 256 + 128))  # Industry-specific section header length
		stream.write(struct.pack(">I", 0))  # User-defined data length
		stream.write((stream.name or "").ljust(99, "\0")[-99:] + "\0")  # File name
		# Date & timestamp
		tzoffset = round((time.mktime(time.localtime()) -
						  time.mktime(time.gmtime())) / 60.0 / 60.0)
		if tzoffset < 0:
			tzoffset = "%.2i" % tzoffset
		else:
			tzoffset = "+%.2i" % tzoffset
		stream.write(time.strftime("%Y:%m:%d:%H:%M:%S") + tzoffset + "\0\0")
		stream.write(("%s %s" % (appname, version)).ljust(100, "\0"))  # Creator
		stream.write("\0" * 200)  # Project
		stream.write("\0" * 200)  # Copyright
		stream.write("\xff" * 4)  # EncryptKey 0xffffffff = not encrypted
		stream.write("\0" * 104)  # Reserved

		# Generic image header (640 bytes)
		stream.write("\0\0")  # Orientation 0 = left to right, top to bottom
		stream.write("\0\1")  # Number of image elements
		stream.write(struct.pack(">I", w))  # Pixels per line
		stream.write(struct.pack(">I", h))  # Lines per image element

		# Generic image header - image element
		stream.write("\0" * 4)  # 0 = unsigned data
		stream.write("\0" * 4)  # Reference low data code value
		stream.write("\xff" * 4)  # Reference low quantity
		stream.write(struct.pack(">I", 2 ** self.bitdepth - 1))  # Reference high data code value
		stream.write("\xff" * 4)  # Reference high quantity
		stream.write(chr(50))  # Descriptor 50 = RGB
		stream.write("\2")  # Transfer 2 = linear
		stream.write("\2")  # Colorimetric 2 = not applicable
		stream.write(chr(self.bitdepth))  # BitSize
		stream.write("\0\1")  # Packing 1 = filled 32-bit words
		stream.write("\0\0")  # Encoding 0 = not encoded
		stream.write(struct.pack(">I", 8192))  # Image data offset
		stream.write("\0" * 4)  # End of line padding
		stream.write("\0" * 4)  # End of image padding
		stream.write("RGB / Linear".ljust(32, "\0"))  # Description

		# Seven additional unused image elements
		stream.write("\0" * 72 * 7)

		# Generic image header (cont.)
		stream.write("\0" * 52)  # Reserved

		# Generic image source header (256 bytes)
		sw, sh = [self.extrainfo.get("original_" + dim,
									 locals()[dim[0]]) for dim in ("width",
																   "height")]
		# X offset
		stream.write(struct.pack(">I", self.extrainfo.get("offset_x",
														  (sw - w) / 2)))
		# Y offset
		stream.write(struct.pack(">I", self.extrainfo.get("offset_y",
														  (sh - h) / 2)))
		# X center
		stream.write(struct.pack(">f", self.extrainfo.get("center_x", sw / 2.0)))
		# Y center
		stream.write(struct.pack(">f", self.extrainfo.get("center_y", sh / 2.0)))
		stream.write(struct.pack(">I", sw))  # X original size
		stream.write(struct.pack(">I", sh))  # Y original size
		stream.write("\0" * 100)  # Source image file name
		stream.write("\0" * 24)  # Source image date & timestamp
		stream.write("\0" * 32)  # Input device name
		stream.write("\0" * 32)  # Input device serial number
		stream.write("\0" * 2 * 4)  # Border
		stream.write("\0\0\0\1" * 2)  # Pixel aspect ratio
		stream.write("\xff" * 4)  # X scanned size
		stream.write("\xff" * 4)  # Y scanned size
		stream.write("\0" * 20)  # Reserved

		# Industry-specific film info header (256 bytes)
		stream.write("\0" * 2)  # Film mfg. ID code
		stream.write("\0" * 2)  # Film type
		stream.write("\0" * 2)  # Offset in perfs
		stream.write("\0" * 6)  # Prefix
		stream.write("\0" * 4)  # Count
		stream.write("\0" * 32)  # Format
		# Frame position in sequence
		stream.write(struct.pack(">I", self.extrainfo.get("frame_position",
														  2 ** 32 - 1)))
		# Sequence length
		stream.write(struct.pack(">I", self.extrainfo.get("sequence_length",
														  2 ** 32 - 1)))
		# Held count
		stream.write(struct.pack(">I", self.extrainfo.get("held_count", 1)))
		# Frame rate of original
		if "frame_rate" in self.extrainfo:
			stream.write(struct.pack(">f", self.extrainfo["frame_rate"]))
		else:
			stream.write("\xff" * 4)
		# Shutter angle of camera in degrees
		stream.write("\xff" * 4)
		stream.write("\0" * 32)  # Frame identification - e.g. keyframe
		stream.write("\0" * 100)  # Slate
		stream.write("\0" * 56)  # Reserved
		
		# Industry-specific TV info header (128 bytes)
		# SMPTE time code
		stream.write("".join(chr(int(str(v), 16)) for v in
							 self.extrainfo.get("timecode", ["ff"] * 4)))
		stream.write("\xff" * 4)  # User bits
		stream.write("\xff")  # Interlace
		stream.write("\xff")  # Field number
		stream.write("\xff")  # Video signal standard
		stream.write("\0")  # Zero for byte alignment
		stream.write("\xff" * 4)  # H sampling rate Hz
		stream.write("\xff" * 4)  # V sampling rate Hz
		stream.write("\xff" * 4)  # Temporal sampling or frame rate Hz
		stream.write("\xff" * 4)  # Time offset in ms from sync to 1st pixel
		stream.write("\xff" * 4)  # Gamma
		stream.write("\xff" * 4)  # Black level code value
		stream.write("\xff" * 4)  # Black gain
		stream.write("\xff" * 4)  # Breakpoint
		stream.write("\xff" * 4)  # Reference white level code value
		stream.write("\xff" * 4)  # Integration time in s
		stream.write("\0" * 76)  # Reserved

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
		imgdata = []
		for i, scanline in enumerate(self.data):
			# Add a scanline, filter type 0
			imgdata.append("\0")
			for RGB in scanline:
				RGB = "".join(self._pack(v) for v in RGB)
				if optimize:
					RGB *= dimensions[0]
				imgdata.append(RGB)
		imgdata = "".join(imgdata)
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
