This is pyinstaller "dispcalGUI edition", based on trunk rev. 706 
(http://svn.pyinstaller.org/trunk), with the following changes:

- patched Build.py, Makespec.py (MS Windows manifest and resource support), 
  bindepend.py (additional DLLs added to the exclude list, added POSIX regex 
  excludes for all .so filenames starting with 'lib' except libpython and 
  libwx, added MS Windows 'Common Controls' assembly exclude, altered DLL 
  dependency walking code so it doesn't warn when it can't find a DLL that is 
  in the exclude list, and added MS Windows assembly dependency walking code), 
  Sconstruct, source/windows/run.rc, source/windows/runw.rc (3x MS 
  VisualStudio C++ 9.0 compatibility fixes, only needed to build the 
  bootloaders with VS 9.0)
- commented out win32comgenpy in rthooks.dat because the hook is broken but 
  not needed by dispcalGUI anyway
- added manifest.py (MS Windows manifest support) along with example files 
  (application.manifest, assembly.manifest, application.config) and template 
  (apptemplate.manifest)
- added resource.py (MS Windows resource support)

Please also see http://pyinstaller.python-hosting.com/ticket/39 and 
http://groups.google.com/group/PyInstaller/browse_thread/thread/4b5d827412deb1c2

Manifest and resource support require the Python for Windows Extensions
https://sourceforge.net/projects/pywin32/