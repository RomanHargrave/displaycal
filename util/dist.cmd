@echo off

for /F usebackq %%a in (`python -c "import sys;print sys.version[:3]"`) do (
	set python_version=%%a
)

for /F usebackq %%a in (`python -c "from dispcalGUI import meta;print meta.version"`) do (
	set version=%%a
)

REM Standalone executable
setup.py bdist_standalone inno --use-distutils

REM ZIP
pushd dist\py2exe.win32-py%python_version%
zip -9 -r ..\dispcalGUI-%version%-win32.zip dispcalGUI-%version%
popd

REM Python 2.5 Installer
C:\Python25\python.exe setup.py bdist_wininst --use-distutils 2>&1 | tee wininst-py2.5.log

REM Python 2.6 Installer
C:\Python26\python.exe setup.py bdist_wininst --use-distutils 2>&1 | tee wininst-py2.6.log
