#!/usr/bin/env python2
# -*- coding: utf-8 -*-

"""
Task Scheduler interface. Currently only implemented for Windows.

Note that most of the functionality requires administrative privileges.

Has a dict-like interface to query existing tasks.

>>> ts = TaskScheduler()

Check if task "name" exists:
>>> "name" in ts
or
>>> ts.has_task("name")

Get existing task "name":
>>> task = ts["name"]
or
>>> ts.get("name")

Run task:
>>> task.Run()
or
>>> ts.run("name")

Get task exit and startup error codes:
>>> exitcode, startup_error_code = task.GetExitCode()
or
>>> exitcode, startup_error_code = ts.get_exit_code(task)

Create a new task to be run under the current user account at logon:
>>> task = ts.create("name", "program.exe", ["arg1", "arg2", "argn"])

"""

from itertools import izip, imap
import os
import subprocess as sp
import sys

import pythoncom
import pywintypes
import win32api
from win32com.taskscheduler.taskscheduler import *

from log import safe_print
from safe_print import enc
from util_os import getenvu
from util_str import safe_unicode


class TaskScheduler(object):

	def __init__(self):
		self._ts = pythoncom.CoCreateInstance(CLSID_CTaskScheduler, None,
											  pythoncom.CLSCTX_INPROC_SERVER,
											  IID_ITaskScheduler)

	def __contains__(self, name):
		return name + ".job" in self._ts.Enum()

	def __getitem__(self, name):
		return self._ts.Activate(name)

	def __iter__(self):
		return iter(job[:-4] for job in self._ts.Enum())

	def create(self, name, cmd, args=None,
			   flags=TASK_FLAG_RUN_ONLY_IF_LOGGED_ON,
			   task_flags=0,
			   trigger_type=TASK_EVENT_TRIGGER_AT_LOGON,
			   trigger_flags=0, replace_existing=False):
		"""
		Create a new task.
		
		If replace_existing evaluates to True, delete any existing task with
		same name first, otherwise raise KeyError.
		
		"""

		if name in self:
			if replace_existing:
				self.delete(name)
			else:
				raise KeyError("The task %s already exists" % name)

		task = self._ts.NewWorkItem(name)
		task.SetApplicationName(sp.list2cmdline([cmd]))
		if args:
			task.SetParameters(sp.list2cmdline(args))
		task.SetFlags(flags)
		task.SetTaskFlags(task_flags)
		task.SetAccountInformation(getenvu("USERNAME"), None)
		self._ts.AddWorkItem(name, task)
		tr_ind, tr = task.CreateTrigger()
		tt = tr.GetTrigger()
		tt.Flags = trigger_flags
		tt.TriggerType = trigger_type
		tr.SetTrigger(tt)
		pf = task.QueryInterface(pythoncom.IID_IPersistFile)
		pf.Save(None, 1)

	def delete(self, name):
		""" Delete existing task """
		self._ts.Delete(name)

	def get(self, name, default=None):
		""" Get existing task """
		if name in self:
			return self[name]
		return default

	def get_exit_code(self, task):
		"""
		Shorthand for task.GetExitCode().
		
		Return a 2-tuple exitcode, startup_error_code.
		
		Call win32api.FormatMessage() on either value to get a readable message
		
		"""
		return task.GetExitCode()
	
	def items(self):
		return zip(self, self.tasks())
	
	def iteritems(self):
		return izip(self, self.itertasks())
	
	def itertasks(self):
		return imap(self.get, self)

	def run(self, name):
		""" Run existing task """
		startupinfo = sp.STARTUPINFO()
		startupinfo.dwFlags |= sp.STARTF_USESHOWWINDOW
		startupinfo.wShowWindow = sp.SW_HIDE
		p = sp.Popen(["schtasks.exe", "/Run", "/TN", name], stdin=sp.PIPE,
					 stdout=sp.PIPE, stderr=sp.STDOUT, startupinfo=startupinfo)
		stdout, stderr = p.communicate()
		safe_print(safe_unicode(stdout, enc))
		return p.returncode

	def has_task(self, name):
		""" Same as name in self """
		return name in self
	
	def tasks(self):
		return map(self.get, self)


if __name__ == "__main__":

	def print_task_attr(name, attr, *args):
		print "%18s:" % name,
		if callable(attr):
			try:
				print attr(*args)
			except pywintypes.com_error, exception:
				print WindowsError(*exception.args)
			except TypeError, exception:
				print exception
		else:
			print attr

	ts = TaskScheduler()

	for taskname, task in ts.iteritems():
		print "=" * 79
		print "%18s:" % "Task", taskname
		for name in dir(task):
			if name == "GetRunTimes":
				continue
			attr = getattr(task, name)
			if name.startswith("Get"):
				if name in ("GetTrigger", "GetTriggerString"):
					for i in xrange(task.GetTriggerCount()):
						print_task_attr(name[3:] +"(%i)" % i, attr, i)
				else:
					print_task_attr(name[3:], attr)
