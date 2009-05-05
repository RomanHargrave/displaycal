@echo off

REM Create a bunch of distributions: A standalone executable, and Installers for Python 2.5 and 2.6

REM Standalone executable
setup.py bdist_standalone > standalone.log 2>&1

REM Python 2.5 Installer
REM C:\Python25\python.exe setup.py build_ext --compiler=mingw32 bdist_wininst --use-distutils > wininst-py2.5.log 2>&1

REM Python 2.6 Installer
C:\Python26\python.exe setup.py bdist_wininst --use-distutils > wininst-py2.6.log 2>&1
