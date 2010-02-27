@echo off
setlocal

for %%a in ("%~dp0..\misc\ti3\*.ti3") do (
	if /i "%%~na"=="laptop"     call :createpreset "-qm -t -g2.4 -f1 -k0 colprof -qm -aS"           "Laptop"       "%%~dpna"
	if /i "%%~na"=="office_web" call :createpreset "-qm -t6500 -g2.4 -f1 -k0 colprof -qm -aS"       "Office & Web" "%%~dpna"
	if /i "%%~na"=="prepress"   call :createpreset "-qh -t5000 -b130 -g2.4 -f1 -k0 colprof -qh -ax" "Prepress"     "%%~dpna"
	if /i "%%~na"=="photo"      call :createpreset "-qh -t5000 -g2.4 -f1 -k0 colprof -qh -ax"       "Photo"        "%%~dpna"
	if /i "%%~na"=="video"      call :createpreset "-qh -t6500 -g2.4 -f1 -k0 colprof -qm -aS"       "Video"        "%%~dpna"
)
goto :EOF

:createpreset
colprof  -v -ql -aG -C "Created with dispcalGUI and Argyll CMS: dispcal %~1" -D "dispcalGUI calibration preset: %~2" "%~3"
move /-Y "%~dpn3.icm" "%~dp0..\dispcalGUI\presets\%~n3.icc"
goto :EOF