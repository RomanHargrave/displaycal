@echo off

for /F usebackq %%a in (`python -c "from dispcalGUI import meta;print meta.version"`) do (
	set version=%%a
)

REM Source tarball
python setup.py sdist 0install %* --formats=gztar --use-distutils 2>&1 | tee dispcalGUI-%version%.sdist.log
