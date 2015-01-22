# -*- coding: utf-8 -*-

"""
Audio wrapper module

Can use pygame, pyo or wx.
pygame will be used by default if available.
pyo seems to be buggy under Linux and has a few quirks under Windows.
wx doesn't support fading, changing volume, multiple concurrent sounds, and
only supports wav format.

Example:
sound = Sound("test.wav", loop=True)
sound.Play(fade_ms=1000)

"""

import threading
import time


_initialized = False
_lib = None
_server = None
_sounds = {}
_wx_is_playing = False


def init(lib=None, samplerate=44100, channels=2, buffersize=1024, reinit=False):
	""" (Re-)Initialize sound subsystem """
	# Note on buffer size: Too high values cause crackling during fade, too low
	# values cause choppy playback of ogg files when using pyo (good value for
	# pyo is >= 2048)
	global _initialized, _lib, _server, pygame, pyo, wx
	if _initialized and not reinit:
		# To re-initialize, explicitly set reinit to True
		return
	# Select the audio library we're going to use.
	# User choice or pygame > pyo > wx
	if not lib:
		for lib in ("pygame", "pyo", "wx"):
			result = init(lib, samplerate, channels, buffersize, reinit)
			if not isinstance(result, Exception):
				return result
	elif lib == "pygame":
		try:
			import pygame.mixer
			_lib = "pygame"
		except ImportError:
			_lib = None
		else:
			try:
				if _initialized:
					pygame.mixer.quit()
				pygame.mixer.init(frequency=samplerate, channels=channels,
								  buffer=buffersize)
			except Exception, exception:
				_server = exception
			else:
				_server = pygame.mixer
	elif lib == "pyo":
		try:
			import pyo
			_lib = "pyo"
		except ImportError:
			_lib = None
		else:
			try:
				if _server:
					_server.reinit(sr=samplerate, nchnls=channels,
								   buffersize=buffersize, duplex=0)
				else:
					_server = pyo.Server(sr=samplerate, nchnls=channels,
										 buffersize=buffersize, duplex=0).boot()
					_server.start()
			except Exception, exception:
				_server = exception
	elif lib == "wx":
		try:
			import wx
			_lib = "wx"
		except (ImportError, NotImplementedError):
			_lib = None
	if not _lib:
		raise NotImplementedError("No audio library available")
	_initialized = True
	return _server


def safe_init(lib=None, samplerate=22050, channels=2, buffersize=1536,
			  reinit=False):
	""" Like init(), but catch any exceptions """
	global _initialized
	try:
		return init(lib, samplerate, channels, buffersize, reinit)
	except Exception, exception:
		# So we can check if initialization failed
		_initialized = exception


class Sound(object):

	""" Sound wrapper class """

	def __init__(self, filename, loop=False):
		self._ch = None
		self._filename = filename
		self._lib = _lib
		self._loop = loop
		self._play_count = 0
		self._snd = None
		self._server = _server
		self._thread = -1

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
			elif self._lib == "pygame":
				volume = self._snd.get_volume()
		return volume

	def _set_volume(self, volume):
		if self._snd and self._lib != "wx":
			if self._lib == "pyo":
				volume = self._snd.mul = volume
			elif self._lib == "pygame":
				volume = self._snd.set_volume(volume)
			return True
		return False

	def fade(self, fade_ms, fade_in=None):
		"""
		Fade in/out.
		
		If fade_in is None, fade in/out depending on current volume.
		
		"""
		if fade_in is None:
			fade_in = not self.volume
		if fade_in and not self.is_playing:
			self.play(fade_ms=fade_ms)
		elif self._snd and self._lib != "wx":
			self._thread += 1
			threading.Thread(target=self._fade,
							 args=(fade_ms, fade_in, self._thread)).start()
			return True
		return False

	@property
	def is_playing(self):
		if self._lib == "pyo":
			return self._snd.isOutputting()
		elif self._lib == "pygame":
			return bool(self._ch and self._ch.get_busy())
		return _wx_is_playing

	def play(self, fade_ms=0):
		global _wx_is_playing
		if not _initialized:
			self._server = init()
			self._lib = _lib
		if _initialized and not isinstance(_initialized, Exception):
			if not self._snd and self._filename:
				if (self._filename in _sounds and
					_sounds[self._filename]["lib"] == self._lib and
					_sounds[self._filename]["loop"] == self.loop):
					# Cache hit
					self._snd = _sounds[self._filename]["snd"]
				elif self._lib == "pyo":
					self._snd = pyo.SfPlayer(self._filename, loop=self._loop)
				elif self._lib == "pygame":
					self._snd = pygame.mixer.Sound(self._filename)
				elif self._lib == "wx":
					self._snd = wx.Sound(self._filename)
				if self._snd and not self._filename in _sounds:
					# Cache sound
					_sounds[self._filename] = {"lib": self._lib,
											   "loop": self._loop,
											   "snd": self._snd}
				if self._lib:
					self.volume = 0 if fade_ms else 1
			if self._snd:
				if self._lib == "pyo":
					if not self.is_playing:
						self._snd.out()
				elif self._lib == "pygame":
					if not self.is_playing:
						self._ch = self._snd.play(-1 if self._loop else 0,
												  fade_ms=0)
				elif self._lib == "wx" and self._snd.IsOk():
					flags = wx.SOUND_ASYNC
					if self._loop:
						flags |= wx.SOUND_LOOP
					is_playing = self._snd.Play(flags)
					_wx_is_playing = is_playing
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
			self._server = safe_init()
		try:
			self.fade(fade_ms, fade_in)
		except:
			pass

	def safe_play(self, fade_ms=0):
		""" Like play(), but catch any exceptions """
		if not _initialized:
			self._server = safe_init()
		try:
			self.play(fade_ms)
		except:
			pass

	def safe_stop(self, fade_ms=0):
		""" Like stop(), but catch any exceptions """
		try:
			self.stop(fade_ms)
		except:
			pass

	def stop(self, fade_ms=0):
		if self._snd and self.is_playing:
			if self._lib == "wx":
				self._snd.Stop()
			elif fade_ms:
				self.fade(fade_ms, False)
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
	button.Bind(wx.EVT_BUTTON, lambda event: sound.play(3000))
	panel.Sizer.Add(button, 1)
	button = wx.Button(panel, -1, "Stop")
	button.Bind(wx.EVT_BUTTON, lambda event: sound.stop(3000))
	panel.Sizer.Add(button, 1)
	panel.Sizer.SetSizeHints(frame)
	frame.Show()
	app.MainLoop()
