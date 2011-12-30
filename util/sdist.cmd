@echo off

for /F usebackq %%a in (`python -c "from dispcalGUI import meta;print meta.version"`) do (
	set version=%%a
)

REM Source tarball
python setup.py sdist --formats=gztar --use-distutils 2>&1 | tee dispcalGUI-%version%.sdist.log

REM 0install feed
for /F usebackq %%a in (`python -c "import os,time;print time.strftime('%%Y-%%m-%%d', time.localtime(os.stat(r'dist\dispcalGUI-%version%.tar.gz').st_mtime))"`) do (
	set released=%%a
)
which 0launch.exe > nul && (
	echo Updating 0install feed...
	0launch http://0install.net/2006/interfaces/0publish --add-version=%version% --archive-url="http://dispcalgui.hoech.net/download.php?version=%version%&suffix=.tar.gz" --archive-file=dist\dispcalGUI-%version%.tar.gz --set-main="dispcalGUI-%version%/dispcalGUI.pyw" --set-released="%released%" --set-stability=stable -x dist\0install\dispcalGUI.xml
)
