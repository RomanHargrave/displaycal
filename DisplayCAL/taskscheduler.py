#!/usr/bin/env python2
# -*- coding: utf-8 -*-

"""
Task Scheduler interface. Currently only implemented for Windows (Vista and up).
The implementation is currently minimal and incomplete when it comes to
creating tasks (all tasks are created for the 'INTERACTIVE' group and with
only logon triggers and exec actions available).

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

from __future__ import with_statement
from itertools import izip, imap
import codecs
import os
import subprocess as sp
import sys
import tempfile

import pywintypes

from log import safe_print
from meta import name as appname
from safe_print import enc
from util_os import getenvu
from util_str import safe_str, safe_unicode, universal_newlines


RUNLEVEL_HIGHESTAVAILABLE = "HighestAvailable"
RUNLEVEL_LEASTPRIVILEGE = "LeastPrivilege"

MULTIPLEINSTANCES_IGNORENEW = "IgnoreNew"
MULTIPLEINSTANCES_STOPEXISTING = "StopExisting"


class LogonTrigger(object):

	def __init__(self, enabled=True):
		self.enabled = enabled

	def __unicode__(self):
		return """    <LogonTrigger>
      <Enabled>%s</Enabled>
    </LogonTrigger>""" % str(self.enabled).lower()


class ExecAction(object):

	def __init__(self, cmd, args=None):
		self.cmd = cmd
		self.args = args or []

	def __unicode__(self):
		return """    <Exec>
      <Command>%s</Command>
      <Arguments>%s</Arguments>
    </Exec>""" % (self.cmd, sp.list2cmdline(self.args))


class Task(object):

	def __init__(self, name="", author="", description="", group_id="S-1-5-4",
				 runlevel=RUNLEVEL_HIGHESTAVAILABLE,
				 multiple_instances=MULTIPLEINSTANCES_IGNORENEW,
				 disallow_start_if_on_batteries=False,
				 stop_if_going_on_batteries=False,
				 allow_hard_terminate=True,
				 start_when_available=False,
				 run_only_if_network_available=False,
				 stop_on_idle_end=False,
				 restart_on_idle=False,
				 allow_start_on_demand=True,
				 enabled=True,
				 hidden=False,
				 run_only_if_idle=False,
				 wake_to_run=False,
				 execution_time_limit="PT72H",
				 priority=5,
				 triggers=None,
				 actions=None):
		self.kwargs = locals()
		self.triggers = triggers or []
		self.actions = actions or []

	def add_exec_action(self, cmd, args=None):
		self.actions.append(ExecAction(cmd, args))

	def add_logon_trigger(self, enabled=True):
		self.triggers.append(LogonTrigger(enabled))

	def write_xml(self, xmlfilename):
		with open(xmlfilename, "wb") as xmlfile:
			xmlfile.write(codecs.BOM_UTF16_LE + str(self))

	def __str__(self):
		kwargs = dict(self.kwargs)
		for name, value in kwargs.iteritems():
			if isinstance(value, bool):
				kwargs[name] = str(value).lower()
		triggers = "\n".join(unicode(trigger) for trigger in self.triggers)
		actions = "\n".join(unicode(action) for action in self.actions)
		kwargs.update({"triggers": triggers, "actions": actions})
		return universal_newlines(("""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Author>%(author)s</Author>
    <Description>%(description)s</Description>
    <URI>\%(name)s</URI>
  </RegistrationInfo>
  <Triggers>
%(triggers)s
  </Triggers>
  <Principals>
    <Principal id="Author">
      <GroupId>%(group_id)s</GroupId>
      <RunLevel>%(runlevel)s</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>%(multiple_instances)s</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>%(disallow_start_if_on_batteries)s</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>%(stop_if_going_on_batteries)s</StopIfGoingOnBatteries>
    <AllowHardTerminate>%(allow_hard_terminate)s</AllowHardTerminate>
    <StartWhenAvailable>%(start_when_available)s</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>%(run_only_if_network_available)s</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>%(stop_on_idle_end)s</StopOnIdleEnd>
      <RestartOnIdle>%(restart_on_idle)s</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>%(allow_start_on_demand)s</AllowStartOnDemand>
    <Enabled>%(enabled)s</Enabled>
    <Hidden>%(hidden)s</Hidden>
    <RunOnlyIfIdle>%(run_only_if_idle)s</RunOnlyIfIdle>
    <WakeToRun>%(wake_to_run)s</WakeToRun>
    <ExecutionTimeLimit>%(execution_time_limit)s</ExecutionTimeLimit>
    <Priority>%(priority)i</Priority>
  </Settings>
  <Actions Context="Author">
%(actions)s
  </Actions>
</Task>""" % kwargs)).replace("\n", "\r\n").encode("UTF-16-LE")


class TaskScheduler(object):

	def __init__(self):
		self.__ts = None

	@property
	def _ts(self):
		if not self.__ts:
			import pythoncom
			from win32com.taskscheduler.taskscheduler import (CLSID_CTaskScheduler,
															  IID_ITaskScheduler)
			self.__ts = pythoncom.CoCreateInstance(CLSID_CTaskScheduler, None,
												   pythoncom.CLSCTX_INPROC_SERVER,
												   IID_ITaskScheduler)
		return self.__ts

	def __contains__(self, name):
		return name + ".job" in self._ts.Enum()

	def __getitem__(self, name):
		return self._ts.Activate(name)

	def __iter__(self):
		return iter(job[:-4] for job in self._ts.Enum())

	def create_task(self, name, author="", description="",
					group_id="S-1-5-4",
					runlevel=RUNLEVEL_HIGHESTAVAILABLE,
					multiple_instances=MULTIPLEINSTANCES_IGNORENEW,
					disallow_start_if_on_batteries=False,
					stop_if_going_on_batteries=False,
					allow_hard_terminate=True,
					start_when_available=False,
					run_only_if_network_available=False,
					stop_on_idle_end=False,
					restart_on_idle=False,
					allow_start_on_demand=True,
					enabled=True,
					hidden=False,
					run_only_if_idle=False,
					wake_to_run=False,
					execution_time_limit="PT72H",
					priority=5,
					triggers=None,
					actions=None,
					replace_existing=False):
		"""
		Create a new task.
		
		If replace_existing evaluates to True, delete any existing task with
		same name first, otherwise raise KeyError.
		
		"""

		kwargs = locals()
		del kwargs["self"]
		del kwargs["replace_existing"]

		if name in self and not replace_existing:
			raise KeyError("The task %s already exists" % name)

		tempdir = tempfile.mkdtemp(prefix=appname + u"-")
		task = Task(**kwargs)
		xmlfilename = os.path.join(tempdir, name + ".xml")
		task.write_xml(xmlfilename)
		try:
			return self._schtasks(["/Create", "/TN", name, "/XML", xmlfilename])
		finally:
			os.remove(xmlfilename)
			os.rmdir(tempdir)

	def create_logon_task(self, name, cmd, args=None,
						  author="", description="",
						  group_id="S-1-5-4",
						  runlevel=RUNLEVEL_HIGHESTAVAILABLE,
						  multiple_instances=MULTIPLEINSTANCES_IGNORENEW,
						  disallow_start_if_on_batteries=False,
						  stop_if_going_on_batteries=False,
						  allow_hard_terminate=True,
						  start_when_available=False,
						  run_only_if_network_available=False,
						  stop_on_idle_end=False,
						  restart_on_idle=False,
						  allow_start_on_demand=True,
						  enabled=True,
						  hidden=False,
						  run_only_if_idle=False,
						  wake_to_run=False,
						  execution_time_limit="PT72H",
						  priority=5,
						  replace_existing=False):

		kwargs = locals()
		del kwargs["self"]
		del kwargs["cmd"]
		del kwargs["args"]
		kwargs.update({"triggers": [LogonTrigger()],
					   "actions": [ExecAction(cmd, args)]})
		return self.create_task(**kwargs)

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
		return self._schtasks(["/Run", "/TN", name])

	def has_task(self, name):
		""" Same as name in self """
		return name in self

	def query_task(self, name):
		"""
		Query task.
		
		"""
		return self._schtasks(["/Query", "/TN", name])

	def _schtasks(self, args, echo=False):
		args.insert(0, "schtasks.exe")
		startupinfo = sp.STARTUPINFO()
		startupinfo.dwFlags |= sp.STARTF_USESHOWWINDOW
		startupinfo.wShowWindow = sp.SW_HIDE
		p = sp.Popen([safe_str(arg) for arg in args], stdin=sp.PIPE,
					 stdout=sp.PIPE, stderr=sp.STDOUT, startupinfo=startupinfo)
		stdout, stderr = p.communicate()
		if echo:
			safe_print(safe_unicode(stdout, enc))
		self.lastreturncode = p.returncode
		return p.returncode == 0
	
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
