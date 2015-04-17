# -*- coding: utf-8 -*-

"""
Audio wrapper module

Can use pygame, pyglet, pyo or wx.
pygame will be used by default if available.
pyglet can only be used if version >= 1.2.2 is available, and still has a few 
bugs e.g. crackling/popping issues with 8 bits per sample audio under Windows.
pyo is still buggy under Linux and has a few quirks under Windows.
pyglet seems like the best bet in the long run as pygame development is stagnant
since 2009.
wx doesn't support fading, changing volume, multiple concurrent sounds, and
only supports wav format.

Example:
sound = Sound("test.wav", loop=True)
sound.Play(fade_ms=1000)

"""

import threading
import time

from log import safe_print


_ch = {}
_initialized = False
_lib = None
_lib_version = None
_server = None
_snd = {}
_sounds = {}


def init(lib=None, samplerate=44100, channels=2, buffersize=2048, reinit=False):
	""" (Re-)Initialize sound subsystem """
	# Note on buffer size: Too high values cause crackling during fade, too low
	# values cause choppy playback of ogg files when using pyo (good value for
	# pyo is >= 2048)
	global _initialized, _lib, _lib_version, _server, pygame, pyglet, pyo, wx
	if _initialized and not reinit:
		# To re-initialize, explicitly set reinit to True
		return
	# Select the audio library we're going to use.
	# User choice or pygame > pyo > pyglet > wx
	if not lib:
		for lib in ("pygame", "pyo", "pyglet", "wx"):
			try:
				return init(lib, samplerate, channels, buffersize, reinit)
			except Exception, exception:
				pass
		raise exception
	elif lib == "pygame":
		try:
			import pygame, pygame.mixer
			_lib = "pygame"
		except ImportError:
			_lib = None
		else:
			if _initialized:
				pygame.mixer.quit()
			pygame.mixer.init(frequency=samplerate, channels=channels,
							  buffer=buffersize)
			_server = pygame.mixer
			_lib_version = pygame.__version__
	elif lib == "pyglet":
		try:
			import pyglet
			version = []
			for item in pyglet.version.split("."):
				try:
					version.append(int(item))
				except ValueError:
					version.append(item)
			if version < [1, 2, 2]:
				raise ImportError("pyglet version %s is too old" %
								  pyglet.version)
			_lib = "pyglet"
		except ImportError:
			_lib = None
		else:
			_server = pyglet.media
			_lib_version = pyglet.version
	elif lib == "pyo":
		try:
			import pyo
			_lib = "pyo"
		except ImportError:
			_lib = None
		else:
			if isinstance(_server, pyo.Server):
				_server.reinit(sr=samplerate, nchnls=channels,
							   buffersize=buffersize, duplex=0)
			else:
				_server = pyo.Server(sr=samplerate, nchnls=channels,
									 buffersize=buffersize, duplex=0).boot()
				_server.start()
				_lib_version = ".".join(str(v) for v in pyo.getVersion())
	elif lib == "wx":
		try:
			import wx
			_lib = "wx"
		except ImportError:
			_lib = None
		else:
			_server = wx
			_lib_version = wx.__version__
	if not _lib:
		raise RuntimeError("No audio library available")
	_initialized = True
	return _server


def safe_init(lib=None, samplerate=22050, channels=2, buffersize=2048,
			  reinit=False):
	""" Like init(), but catch any exceptions """
	global _initialized
	try:
		return init(lib, samplerate, channels, buffersize, reinit)
	except Exception, exception:
		# So we can check if initialization failed
		_initialized = exception
		return exception


def Sound(filename, loop=False, raise_exceptions=False):
	""" Sound caching mechanism """
	if (filename, loop) in _sounds:
		# Cache hit
		return _sounds[(filename, loop)]
	else:
		try:
			sound = _Sound(filename, loop)
		except Exception, exception:
			if raise_exceptions:
				raise
			safe_print(exception)
			sound = _Sound(None, loop)
		_sounds[(filename, loop)] = sound
		return sound


class _DummySound(object):

	""" Dummy sound wrapper class """

	def __init__(self, filename, loop=False):
		pass

	def fade(self, fade_ms, fade_in=None):
		return True

	@property
	def is_playing(self):
		return False

	def play(self, fade_ms=0):
		return True

	@property
	def play_count(self):
		return 0

	def safe_fade(self, fade_ms, fade_in=None):
		return True

	def safe_play(self, fade_ms=0):
		return True

	def safe_stop(self, fade_ms=0):
		return True

	def stop(self, fade_ms=0):
		return True

	volume = 0


class _Sound(object):

	""" Sound wrapper class """

	def __init__(self, filename, loop=False):
		self._filename = filename
		self._is_playing = False
		self._lib = _lib
		self._loop = loop
		self._play_timestamp = 0
		self._play_count = 0
		self._thread = -1
		if not _initialized:
			init()
		if _initialized and not isinstance(_initialized, Exception):
			if not self._lib and _lib:
				self._lib = _lib
			if not self._snd and self._filename:
				if self._lib == "pyo":
					self._snd = pyo.SfPlayer(self._filename, loop=self._loop)
				elif self._lib == "pyglet":
					snd = pyglet.media.load(self._filename, streaming=False)
					self._ch = pyglet.media.Player()
					self._snd = snd
				elif self._lib == "pygame":
					self._snd = pygame.mixer.Sound(self._filename)
				elif self._lib == "wx":
					self._snd = wx.Sound(self._filename)

	def _get_ch(self):
		return _ch.get((self._filename, self._loop))

	def _set_ch(self, ch):
		_ch[(self._filename, self._loop)] = ch

	_ch = property(_get_ch, _set_ch)

	def _fade(self, fade_ms, fade_in, thread):
		volume = self.volume
		if fade_ms and ((fade_in and volume < 1) or (not fade_in and volume)):
			count = 200
			for i in xrange(count + 1):
				if fade_in:
					self.volume = volume + i / float(count) * (1.0 - volume)
				else:
					self.volume = volume - i / float(count) * volume
				time.sleep(fade_ms / 1000.0 / count)
				if self._thread is not thread:
					# If we are no longer the current thread, return immediately
					return
		if not self.volume:
			self.stop()

	def _get_volume(self):
		volume = 1.0
		if self._snd:
			if self._lib == "pyo":
				volume = self._snd.mul
			elif self._lib == "pyglet":
				volume = self._ch.volume
			elif self._lib == "pygame":
				volume = self._snd.get_volume()
		return volume

	def _set_volume(self, volume):
		if self._snd and self._lib != "wx":
			if self._lib == "pyo":
				self._snd.mul = volume
			elif self._lib == "pyglet":
				self._ch.volume = volume
			elif self._lib == "pygame":
				self._snd.set_volume(volume)
			return True
		return False

	def _get_snd(self):
		return _snd.get((self._filename, self._loop))

	def _set_snd(self, snd):
		_snd[(self._filename, self._loop)] = snd

	_snd = property(_get_snd, _set_snd)

	def fade(self, fade_ms, fade_in=None):
		"""
		Fade in/out.
		
		If fade_in is None, fade in/out depending on current volume.
		
		"""
		if fade_in is None:
			fade_in = not self.volume
		if fade_in and not self.is_playing:
			return self.play(fade_ms=fade_ms)
		elif self._snd and self._lib != "wx":
			self._thread += 1
			threading.Thread(target=self._fade,
							 args=(fade_ms, fade_in, self._thread)).start()
			return True
		return False

	@property
	def is_playing(self):
		if self._lib == "pyo":
			return bool(self._snd and self._snd.isOutputting())
		elif self._lib == "pyglet":
			return bool(self._ch and self._ch.playing and self._ch.source and
						(self._loop or time.time() - self._play_timestamp <
						 self._ch.source.duration))
		elif self._lib == "pygame":
			return bool(self._ch and self._ch.get_busy())
		return self._is_playing

	def play(self, fade_ms=0):
		if self._snd:
			volume = self.volume
			self.stop()
			if self._lib == "pyglet":
				# Can't reuse the player, won't replay the sound under Mac OS X
				# and Linux even when seeking to start position which allows
				# replaying the sound under Windows.
				self._ch = pyglet.media.Player()
				self.volume = volume
			if not self.is_playing and fade_ms and volume == 1:
				self.volume = 0
			self._play_timestamp = time.time()
			if self._lib == "pyo":
				self._snd.out()
			elif self._lib == "pyglet":
				if self._loop:
					snd = pyglet.media.SourceGroup(self._snd.audio_format,
												   self._snd.video_format)
					snd.loop = True
					snd.queue(self._snd)
				else:
					snd = self._snd
				self._ch.queue(snd)
				self._ch.play()
			elif self._lib == "pygame":
				self._ch = self._snd.play(-1 if self._loop else 0,
										  fade_ms=0)
			elif self._lib == "wx" and self._snd.IsOk():
				flags = wx.SOUND_ASYNC
				if self._loop:
					flags |= wx.SOUND_LOOP
					# The best we can do is have the correct state reflected
					# for looping sounds only
					self._is_playing = True
				# wx.Sound.Play is supposed to return True on success.
				# When I tested this, it always returned False, but still
				# played the sound.
				self._snd.Play(flags)
			if self._lib:
				self._play_count += 1
			if fade_ms and self._lib != "wx":
				self.fade(fade_ms, True)
			return True
		return False

	@property
	def play_count(self):
		return self._play_count

	def safe_fade(self, fade_ms, fade_in=None):
		""" Like fade(), but catch any exceptions """
		if not _initialized:
			safe_init()
		try:
			return self.fade(fade_ms, fade_in)
		except Exception, exception:
			return exception

	def safe_play(self, fade_ms=0):
		""" Like play(), but catch any exceptions """
		if not _initialized:
			safe_init()
		try:
			return self.play(fade_ms)
		except Exception, exception:
			return exception

	def safe_stop(self, fade_ms=0):
		""" Like stop(), but catch any exceptions """
		try:
			return self.stop(fade_ms)
		except Exception, exception:
			return exception

	def stop(self, fade_ms=0):
		if self._snd and self.is_playing:
			if self._lib == "wx":
				self._snd.Stop()
				self._is_playing = False
			elif fade_ms:
				self.fade(fade_ms, False)
			else:
				if self._lib == "pyglet":
					self._ch.pause()
				else:
					self._snd.stop()
				if self._lib == "pygame":
					self._ch = None
			return True
		else:
			return False

	volume = property(_get_volume, _set_volume)


if __name__ == "__main__":
	import wx
	from config import get_data_path
	sound = Sound(get_data_path("theme/engine_hum_loop.wav"), True)
	app = wx.App(0)
	frame = wx.Frame(None, -1, "Test")
	frame.Bind(wx.EVT_CLOSE, lambda event: (sound.stop(1000) and
											_lib != "wx" and time.sleep(1),
											event.Skip()))
	panel = wx.Panel(frame)
	panel.Sizer = wx.BoxSizer()
	button = wx.Button(panel, -1, "Play")
	button.Bind(wx.EVT_BUTTON, lambda event: not sound.is_playing and
											 sound.play(3000))
	panel.Sizer.Add(button, 1)
	button = wx.Button(panel, -1, "Stop")
	button.Bind(wx.EVT_BUTTON, lambda event: sound.is_playing and
											 sound.stop(3000))
	panel.Sizer.Add(button, 1)
	panel.Sizer.SetSizeHints(frame)
	frame.Show()
	app.MainLoop()
