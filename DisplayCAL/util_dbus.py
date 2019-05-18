# -*- coding: utf-8 -*-

import sys

try:
	import dbus
	from dbus.mainloop import glib

	from util_xml import XMLDict
except ImportError:
	if sys.platform not in ("darwin", "win32"):
		raise

	DBusException = Exception
else:
	glib.threads_init()

	dbus_session = dbus.SessionBus()
	dbus_system = dbus.SystemBus()

	DBusException = dbus.exceptions.DBusException


from util_str import safe_str


BUSTYPE_SESSION = 1
BUSTYPE_SYSTEM = 2


class DBusObject(object):

	def __init__(self, bus_type, bus_name, object_path=None, iface_name=None):
		self._bus_type = bus_type
		self._bus_name = bus_name
		self._object_path = object_path
		self._iface_name = iface_name
		self._proxy = None
		self._iface = None
		if object_path:
			if bus_type == BUSTYPE_SESSION:
				bus = dbus_session
			else:
				bus = dbus_system
			interface = self._bus_name
			if self._iface_name:
				interface += "." + self._iface_name
			try:
				self._proxy = bus.get_object(bus_name, object_path)
				self._iface = dbus.Interface(self._proxy,
											 dbus_interface=interface)
			except (TypeError, ValueError,
					dbus.exceptions.DBusException), exception:
				raise DBusObjectError(exception, self._bus_name)
		self._introspectable = None

	def __getattr__(self, name):
		name = "".join(part.capitalize() for part in name.split("_"))
		try:
			return getattr(self._iface, name)
		except (AttributeError, TypeError, ValueError,
				dbus.exceptions.DBusException), exception:
			raise DBusObjectError(exception, self._bus_name)

	@property
	def properties(self):
		if not self._proxy:
			return {}
		interface = self._bus_name
		if self._iface_name:
			interface += "." + self._iface_name
		try:
			iface = dbus.Interface(self._proxy, "org.freedesktop.DBus.Properties")
			return iface.GetAll(interface)
		except (TypeError, ValueError,
				dbus.exceptions.DBusException), exception:
			raise DBusObjectError(exception, self._bus_name)

	def introspect(self):
		if not self._introspectable:
			self._introspectable = DBusObject(self._bus_type,
											  "org.freedesktop.DBus",
											  "/" + self._bus_name.replace(".", "/"),
											  "Introspectable")
		xml = self._introspectable.Introspect()
		return XMLDict(xml)


class DBusObjectError(DBusException):

	def __init__(self, exception, bus_name=None):
		self._dbus_error_name = getattr(exception, "get_dbus_name",
								  lambda: None)()
		if self._dbus_error_name == "org.freedesktop.DBus.Error.ServiceUnknown":
			exception = "%s: %s" % (exception, bus_name)
		Exception.__init__(self, safe_str(exception))

	def get_dbus_name(self):
		return self._dbus_error_name
