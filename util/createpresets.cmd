@echo off
setlocal

for %%a in ("%~dp0..\misc\ti3\*.ti3") do (
	if /i "%%~na"=="laptop"     call :createpreset "Laptop"       "%%~dpna"
	if /i "%%~na"=="office_web" call :createpreset "Office & Web" "%%~dpna"
	if /i "%%~na"=="prepress"   call :createpreset "Prepress"     "%%~dpna"
	if /i "%%~na"=="photo"      call :createpreset "Photo"        "%%~dpna"
	if /i "%%~na"=="softproof"  call :createpreset "Softproof"    "%%~dpna"
	if /i "%%~na"=="video"      call :createpreset "Video"        "%%~dpna"
)
goto :EOF

:createpreset
colprof  -v -ql -aG -C "Created with dispcalGUI and Argyll CMS" -D "dispcalGUI calibration preset: %~1" "%~2"
move /-Y "%~dpn2.icm" "%~dp0..\dispcalGUI\presets\%~n2.icc"
goto :EOF