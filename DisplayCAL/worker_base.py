# -*- coding: utf-8 -*-

from __future__ import with_statement
from binascii import hexlify
import atexit
import multiprocessing as mp
import os
import pipes
import re
import shutil
import subprocess as sp
import sys
import tempfile
import textwrap
import traceback

if sys.platform == "win32":
	import win32api

from argyll_names import (names as argyll_names, altnames as argyll_altnames,
						  optional as argyll_optional)
from config import exe_ext, fs_enc, get_data_path, getcfg, profile_ext
from debughelpers import (Error, Info, UnloggedError, UnloggedInfo,
						  UnloggedWarning, Warn)
from log import LogFile, safe_print
from meta import name as appname
from options import debug, verbose
from util_os import getenvu, quote_args, which
from util_str import safe_basestring, safe_str, safe_unicode
import CGATS
import colormath
import config
import ICCProfile as ICCP
import localization as lang


def Property(func):
	return property(**func())


def _mp_generate_B2A_clut(chunk, thread_abort_event, progress_queue,
						  profile_filename, intent, direction, pcs,
						  use_cam_clipping, clutres, step, threshold,
						  threshold2, interp, Linterp, m2, XYZbp, XYZwp, bpc,
						  abortmessage="Aborted"):
	"""
	B2A cLUT generation worker
	
	This should be spawned as a multiprocessing process
	
	"""
	if debug:
		safe_print("comtypes?", "comtypes" in str(sys.modules.keys()))
		safe_print("numpy?", "numpy" in str(sys.modules.keys()))
		safe_print("wx?", "wx" in str(sys.modules.keys()))
		safe_print("x3dom?", "x3dom" in str(sys.modules.keys()))
	try:
		if not config.cfg.items(config.ConfigParser.DEFAULTSECT):
			config.initcfg()
		idata = []
		abmaxval = 255 + (255 / 256.0)
		profile = ICCP.ICCProfile(profile_filename)
		xicclu1 = Xicclu(profile, intent, direction, "n", pcs, 100)
		if use_cam_clipping:
			# Use CAM Jab for clipping for cLUT grid points after a given
			# threshold
			xicclu2 = Xicclu(profile, intent, direction, "n", pcs, 100,
							 use_cam_clipping=True)
		prevperc = 0
		count = 0
		chunksize = len(chunk)
		for a in chunk:
			if thread_abort_event.is_set():
				if use_cam_clipping:
					xicclu2.exit()
				xicclu1.exit()
				return Info(abortmessage)
				return
			for b in xrange(clutres):
				for c in xrange(clutres):
					d, e, f = [v * step for v in (a, b, c)]
					if profile.connectionColorSpace == "XYZ":
						# Apply TRC to XYZ values to distribute them optimally
						# across cLUT grid points.
						XYZ = [interp[i](v) for i, v in enumerate((d, e, f))]
						##print "%3.6f %3.6f %3.6f" % tuple(XYZ), '->',
						# Scale into device colorspace
						v = m2.inverted() * XYZ
						if bpc and XYZbp != [0, 0, 0]:
							v = colormath.blend_blackpoint(v[0], v[1], v[2],
													None, XYZbp)
						##print "%3.6f %3.6f %3.6f" % tuple(v)
						##raw_input()
						if intent == "a":
							v = colormath.adapt(*v + [XYZwp,
													  profile.tags.wtpt.ir.values()])
					else:
						# Legacy CIELAB
						L = Linterp(d * 100)
						v = L, -128 + e * abmaxval, -128 + f * abmaxval
					idata.append("%.6f %.6f %.6f" % tuple(v))
					# Lookup CIE -> device values through profile using xicclu
					if not use_cam_clipping or (pcs == "x" and
												a <= threshold and
												b <= threshold and
												c <= threshold):
						xicclu1(v)
					if use_cam_clipping and (pcs == "l" or
											 a > threshold2 or
											 b > threshold2 or
											 c > threshold2):
						xicclu2(v)
					count += 1.0
				perc = round(count / (chunksize * clutres ** 2) * 100)
				if progress_queue and perc > prevperc:
					progress_queue.put(perc - prevperc)
					prevperc = perc
		if use_cam_clipping:
			xicclu2.exit()
			data2 = xicclu2.get()
		else:
			data2 = []
		xicclu1.exit()
		data1 = xicclu1.get()
		return idata, data1, data2
	except Exception, exception:
		safe_print(traceback.format_exc())
		return exception
	finally:
		progress_queue.put(EOFError())
		if "--multiprocessing-fork" in sys.argv[1:]:
			atexit._run_exitfuncs()


def check_argyll_bin(paths=None):
	""" Check if the Argyll binaries can be found. """
	prev_dir = None
	for name in argyll_names:
		exe = get_argyll_util(name, paths)
		if not exe:
			if name in argyll_optional:
				continue
			return False
		cur_dir = os.path.dirname(exe)
		if prev_dir:
			if cur_dir != prev_dir:
				if name in argyll_optional:
					if verbose: safe_print("Warning: Optional Argyll "
										   "executable %s is not in the same "
										   "directory as the main executables "
										   "(%s)." % (exe, prev_dir))
				else:
					if verbose: safe_print("Error: Main Argyll "
										   "executable %s is not in the same "
										   "directory as the other executables "
										   "(%s)." % (exe, prev_dir))
					return False
		else:
			prev_dir = cur_dir
	if verbose >= 3: safe_print("Argyll binary directory:", cur_dir)
	if debug: safe_print("[D] check_argyll_bin OK")
	if debug >= 2:
		if not paths:
			paths = getenvu("PATH", os.defpath).split(os.pathsep)
			argyll_dir = (getcfg("argyll.dir") or "").rstrip(os.path.sep)
			if argyll_dir:
				if argyll_dir in paths:
					paths.remove(argyll_dir)
				paths = [argyll_dir] + paths
		safe_print("[D] Searchpath:\n  ", "\n  ".join(paths))
	# Fedora doesn't ship Rec709.icm
	config.defaults["3dlut.input.profile"] = get_data_path(os.path.join("ref",
																		"Rec709.icm")) or \
											 get_data_path(os.path.join("ref", "sRGB.icm")) or ""
	config.defaults["testchart.reference"] = get_data_path(os.path.join("ref", 
																		"ColorChecker.cie")) or ""
	config.defaults["gamap_profile"] = get_data_path(os.path.join("ref", "sRGB.icm")) or ""
	return True


argyll_utils = {}

def get_argyll_util(name, paths=None):
	""" Find a single Argyll utility. Return the full path. """
	cfg_argyll_dir = getcfg("argyll.dir")
	if paths:
		cache_key = os.pathsep.join(paths)
	else:
		cache_key = cfg_argyll_dir
	exe = argyll_utils.get(cache_key, {}).get(name, None)
	if exe:
		return exe
	if not paths:
		paths = getenvu("PATH", os.defpath).split(os.pathsep)
		argyll_dir = (cfg_argyll_dir or "").rstrip(os.path.sep)
		if argyll_dir:
			if argyll_dir in paths:
				paths.remove(argyll_dir)
			paths = [argyll_dir] + paths
	elif verbose >= 4:
		safe_print("Info: Searching for", name, "in", os.pathsep.join(paths))
	for path in paths:
		for altname in argyll_altnames.get(name, []):
			exe = which(altname + exe_ext, [path])
			if exe:
				break
		if exe:
			break
	if verbose >= 4:
		if exe:
			safe_print("Info:", name, "=", exe)
		else:
			safe_print("Info:", "|".join(argyll_altnames[name]), 
					   "not found in", os.pathsep.join(paths))
	if exe:
		if not cache_key in argyll_utils:
			argyll_utils[cache_key] = {}
		argyll_utils[cache_key][name] = exe
	return exe


def get_argyll_utilname(name, paths=None):
	""" Find a single Argyll utility. Return the basename without extension. """
	exe = get_argyll_util(name, paths)
	if exe:
		exe = os.path.basename(os.path.splitext(exe)[0])
	return exe


def get_argyll_version(name, paths=None):
	"""
	Determine version of a certain Argyll utility.
	
	"""
	argyll_version_string = get_argyll_version_string(name, paths)
	return parse_argyll_version_string(argyll_version_string)


def get_argyll_version_string(name, paths=None):
	argyll_version_string = "0.0.0"
	cmd = get_argyll_util(name, paths)
	if sys.platform == "win32":
		startupinfo = sp.STARTUPINFO()
		startupinfo.dwFlags |= sp.STARTF_USESHOWWINDOW
		startupinfo.wShowWindow = sp.SW_HIDE
	else:
		startupinfo = None
	try:
		p = sp.Popen([cmd.encode(fs_enc), "-?"], stdin=sp.PIPE,
					 stdout=sp.PIPE, stderr=sp.STDOUT,
					 startupinfo=startupinfo)
	except Exception, exception:
		safe_print(exception)
		return argyll_version_string
	for i, line in enumerate((p.communicate()[0] or "").splitlines()):
		if isinstance(line, basestring):
			line = line.strip()
			if "version" in line.lower():
				argyll_version_string = line[line.lower().find("version") + 8:]
				break
	return argyll_version_string


def parse_argyll_version_string(argyll_version_string):
	argyll_version = re.findall("(\d+|[^.\d]+)", argyll_version_string)
	for i, v in enumerate(argyll_version):
		try:
			argyll_version[i] = int(v)
		except ValueError:
			pass
	return argyll_version


def printcmdline(cmd, args=None, fn=safe_print, cwd=None):
	"""
	Pretty-print a command line.
	"""
	if args is None:
		args = []
	if cwd is None:
		cwd = os.getcwdu()
	fn("  " + cmd)
	i = 0
	lines = []
	for item in args:
		ispath = False
		if item.find(os.path.sep) > -1:
			if os.path.dirname(item) == cwd:
				item = os.path.basename(item)
			ispath = True
		if sys.platform == "win32":
			item = sp.list2cmdline([item])
			if not item.startswith('"'):
				item = quote_args([item])[0]
		else:
			item = pipes.quote(item)
		lines.append(item)
		i += 1
	for line in lines:
		fn(textwrap.fill(line, 80, expand_tabs=False, 
						 replace_whitespace=False, initial_indent="    ", 
						 subsequent_indent="      "))


class ThreadAbort(object):

	def __init__(self):
		self.manager = mp.Manager()
		self.event = self.manager.Event()

	def __nonzero__(self):
		return self.event.is_set()
    
	def __cmp__(self, other):
		if self.event.is_set() < other:
			return -1
		if self.event.is_set() > other:
			return 1
		return 0


class WorkerBase(object):

	def __init__(self):
		"""
		Create and return a new base worker instance.
		"""
		self.sessionlogfile = None
		self.subprocess_abort = False
		self.tempdir = None
		self._thread_abort = ThreadAbort()

	def create_tempdir(self):
		""" Create a temporary working directory and return its path. """
		if not self.tempdir or not os.path.isdir(self.tempdir):
			# we create the tempdir once each calibrating/profiling run 
			# (deleted by 'wrapup' after each run)
			if verbose >= 2:
				if not self.tempdir:
					msg = "there is none"
				else:
					msg = "the previous (%s) no longer exists" % self.tempdir
				safe_print(appname + ": Creating a new temporary directory "
						   "because", msg)
			try:
				self.tempdir = tempfile.mkdtemp(prefix=appname + u"-")
			except Exception, exception:
				self.tempdir = None
				return Error("Error - couldn't create temporary directory: " + 
							 safe_str(exception))
		return self.tempdir
	
	def isalive(self, subprocess=None):
		""" Check if subprocess is still alive """
		if not subprocess:
			subprocess = getattr(self, "subprocess", None)
		return (subprocess and
				((hasattr(subprocess, "poll") and 
				  subprocess.poll() is None) or
				 (hasattr(subprocess, "isalive") and 
				  subprocess.isalive())))
	
	def log(self, *args, **kwargs):
		""" Log to global logfile and session logfile (if any) """
		msg = " ".join(safe_basestring(arg) for arg in args)
		fn = kwargs.get("fn", safe_print)
		fn(msg)
		if self.sessionlogfile:
			self.sessionlogfile.write(msg + "\n")

	@Property
	def thread_abort():
		def fget(self):
			return self._thread_abort
		
		def fset(self, abort):
			if abort:
				self._thread_abort.event.set()
			else:
				self._thread_abort.event.clear()
		
		return locals()
	
	def xicclu(self, profile, idata, intent="r", direction="f", order="n",
			   pcs=None, scale=1, cwd=None, startupinfo=None, raw=False,
			   logfile=None, use_icclu=False, use_cam_clipping=False,
			   get_clip=False, show_actual_if_clipped=False,
			   input_encoding=None, output_encoding=None):
		"""
		Call xicclu, feed input floats into stdin, return output floats.
		
		input data needs to be a list of 3-tuples (or lists) with floats,
		alternatively a list of strings.
		output data will be returned in same format, or as list of strings
		if 'raw' is true.
		
		"""
		with Xicclu(profile, intent, direction, order, pcs, scale, cwd,
					startupinfo, use_icclu, use_cam_clipping, logfile,
					self, show_actual_if_clipped, input_encoding,
					output_encoding) as xicclu:
			xicclu(idata)
		return xicclu.get(raw, get_clip)


class Xicclu(WorkerBase):
	def __init__(self, profile, intent="r", direction="f", order="n",
				 pcs=None, scale=1, cwd=None, startupinfo=None, use_icclu=False,
				 use_cam_clipping=False, logfile=None, worker=None,
				 show_actual_if_clipped=False, input_encoding=None,
				 output_encoding=None):
		WorkerBase.__init__(self)
		self.logfile = logfile
		self.worker = worker
		self.temp = False
		utilname = "icclu" if use_icclu else "xicclu"
		xicclu = get_argyll_util(utilname)
		if not xicclu:
			raise Error(lang.getstr("argyll.util.not_found", utilname))
		if not isinstance(profile, (CGATS.CGATS, ICCP.ICCProfile)):
			if profile.lower().endswith(".cal"):
				profile = CGATS.CGATS(profile)
			else:
				profile = ICCP.ICCProfile(profile)
		is_profile = isinstance(profile, ICCP.ICCProfile)
		if not profile.fileName or not os.path.isfile(profile.fileName):
			if not cwd:
				cwd = self.create_tempdir()
				if isinstance(cwd, Exception):
					raise cwd
			fd, profile.fileName = tempfile.mkstemp(profile_ext, dir=cwd)
			stream = os.fdopen(fd, "wb")
			profile.write(stream)
			stream.close()
			self.temp = True
		elif not cwd:
			cwd = os.path.dirname(profile.fileName)
		profile_basename = safe_unicode(os.path.basename(profile.fileName))
		profile_path = profile.fileName
		if sys.platform == "win32":
			profile_path = win32api.GetShortPathName(profile_path)
		self.profile_path = safe_str(profile_path)
		if sys.platform == "win32" and not startupinfo:
			startupinfo = sp.STARTUPINFO()
			startupinfo.dwFlags |= sp.STARTF_USESHOWWINDOW
			startupinfo.wShowWindow = sp.SW_HIDE
		xicclu = safe_str(xicclu)
		cwd = safe_str(cwd)
		args = [xicclu, "-s%s" % scale]
		if utilname == "xicclu":
			if (is_profile and
				show_actual_if_clipped and "A2B0" in profile.tags and
				("B2A0" in profile.tags or direction == "if")):
				args.append("-a")
			if use_cam_clipping:
				args.append("-b")
			if get_argyll_version("xicclu") >= [1, 6]:
				# Add encoding parameters
				# Note: Not adding -e -E can cause problems due to unitialized
				# in_tvenc and out_tvenc variables in xicclu.c for Argyll 1.6.x
				if not input_encoding:
					input_encoding = "n"
				if not output_encoding:
					output_encoding = "n"
				args += ["-e" + input_encoding, "-E" + output_encoding]
		args.append("-f" + direction)
		if is_profile:
			if profile.profileClass not in ("abst", "link"):
				args.append("-i" + intent)
				if order != "n":
					args.append("-o" + order)
			if pcs and profile.profileClass != "link":
				args.append("-p" + pcs)
		args.append(self.profile_path)
		if debug or verbose > 1:
			self.sessionlogfile = LogFile(profile_basename + ".xicclu",
										  os.path.dirname(profile.fileName))
			if is_profile:
				profile_act = ICCP.ICCProfile(profile.fileName)
				self.sessionlogfile.write("Profile ID %s (actual %s)" %
										  (hexlify(profile.ID),
										   hexlify(profile_act.calculateID(False))))
			if cwd:
				self.log(lang.getstr("working_dir"))
				indent = "  "
				for name in cwd.split(os.path.sep):
					self.log(textwrap.fill(name + os.path.sep, 80, 
										   expand_tabs=False, 
										   replace_whitespace=False, 
										   initial_indent=indent, 
										   subsequent_indent=indent))
					indent += " "
				self.log("")
			self.log(lang.getstr("commandline"))
			printcmdline(xicclu if debug or verbose > 2 else
						 os.path.basename(xicclu), args[1:], fn=self.log,
						 cwd=cwd)
			self.log("")
		self.startupinfo = startupinfo
		self.args = args
		self.cwd = cwd
		self.spawn()

	def spawn(self):
		self.closed = False
		self.output = []
		self.errors = []
		self.stdout = tempfile.SpooledTemporaryFile()
		self.stderr = tempfile.SpooledTemporaryFile()
		self.subprocess = sp.Popen(self.args, stdin=sp.PIPE, stdout=self.stdout,
								   stderr=self.stderr, cwd=self.cwd,
								   startupinfo=self.startupinfo)
	
	def __call__(self, idata):
		if not isinstance(idata, basestring):
			idata = list(idata)  # Make a copy
			for i, v in enumerate(idata):
				if isinstance(v, (float, int, long)):
					self([idata])
					return
				if not isinstance(v, basestring):
					for n in v:
						if not isinstance(n, (float, int, long)):
							raise TypeError("xicclu: Expecting list of "
											"strings or n-tuples with "
											"floats")
					idata[i] = " ".join([str(n) for n in v])
		else:
			idata = idata.splitlines()
		numrows = len(idata)
		chunklen = 1000
		i = 0
		p = self.subprocess
		while True:
			# Process in chunks to prevent broken pipe if input data is too
			# large
			if self.subprocess_abort or self.thread_abort:
				if p.poll() is None:
					p.stdin.write("\n")
					p.stdin.close()
					p.wait()
				raise Info(lang.getstr("aborted"))
			if p.poll() is None:
				# We don't use communicate() because it will end the
				# process
				p.stdin.write("\n".join(idata[chunklen * i:
											  chunklen * (i + 1)]) + "\n")
				p.stdin.flush()
			else:
				# Error
				break
			if self.logfile:
				self.logfile.write("\r%i%%" % min(round(chunklen * (i + 1) /
												   float(numrows) * 100),
											 100))
			if chunklen * (i + 1) > numrows - 1:
				break
			i += 1
	
	def __enter__(self):
		return self
	
	def __exit__(self, etype=None, value=None, tb=None):
		self.exit()
		if tb:
			return False
	
	def close(self):
		if self.closed:
			return
		p = self.subprocess
		if p.poll() is None:
			try:
				p.stdin.write("\n")
			except IOError:
				pass
			p.stdin.close()
		p.wait()
		self.stdout.seek(0)
		self.output = self.stdout.readlines()
		self.stdout.close()
		self.stderr.seek(0)
		self.errors = self.stderr.readlines()
		self.stderr.close()
		if self.sessionlogfile and self.errors:
			self.sessionlogfile.write("\n".join(self.errors))
		if self.logfile:
			self.logfile.write("\n")
		self.closed = True
		if p.returncode:
			# Error
			raise IOError("\n".join(self.errors))

	def exit(self):
		self.close()
		if self.temp and os.path.isfile(self.profile_path):
			os.remove(self.profile_path)
			if self.tempdir and not os.listdir(self.tempdir):
				try:
					shutil.rmtree(self.tempdir, True)
				except Exception, exception:
					safe_print(u"Warning - temporary directory '%s' could "
							   u"not be removed: %s" % 
							   tuple(safe_unicode(s) for s in 
									 (self.tempdir, exception)))
	
	def get(self, raw=False, get_clip=False):
		if raw:
			if self.sessionlogfile:
				self.sessionlogfile.write("\n".join(self.output))
				self.sessionlogfile.close()
			return self.output
		parsed = []
		j = 0
		for i, line in enumerate(self.output):
			line = line.strip()
			if line.startswith("["):
				if self.sessionlogfile:
					self.sessionlogfile.write(line)
				continue
			elif not "->" in line:
				if self.sessionlogfile and line:
					self.sessionlogfile.write(line)
				continue
			elif self.sessionlogfile:
				self.sessionlogfile.write("#%i %s" % (j, line))
			parts = line.split("->")[-1].strip().split()
			clip = parts.pop() == "(clip)"
			if clip:
				parts.pop()
			parsed.append([float(n) for n in parts])
			if get_clip:
				parsed[-1].append(clip)
			j += 1
		if self.sessionlogfile:
			self.sessionlogfile.close()
		return parsed
	
	@Property
	def subprocess_abort():
		def fget(self):
			if self.worker:
				return self.worker.subprocess_abort
			return False
		
		def fset(self, v):
			pass
		
		return locals()
	
	@Property
	def thread_abort():
		def fget(self):
			if self.worker:
				return self.worker.thread_abort
			return False
		
		def fset(self, v):
			pass
		
		return locals()
