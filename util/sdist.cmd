@echo off

for /F usebackq %%a in (`python -c "from dispcalGUI import meta;print meta.version"`) do (
	set version=%%a
)

REM Source tarball
setup.py sdist --formats=gztar --use-setuptools 2>&1 | tee dispcalGUI-%version%.sdist.log

