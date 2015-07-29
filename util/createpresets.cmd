@echo off
setlocal

if not "%~1"=="" (
	if not "%~2"=="" goto single
)

call :createpreset "Default"      "default"
call :createpreset "eeColor"      "video_eeColor"
call :createpreset "Laptop"       "laptop"
call :createpreset "madVR"        "video_madVR"
call :createpreset "Office & Web" "office_web"
call :createpreset "Photo"        "photo"
call :createpreset "Prepress"     "prepress"
call :createpreset "ReShade"      "video_ReShade"
call :createpreset "Resolve"      "video_resolve"
call :createpreset "Softproof"    "softproof"
call :createpreset "sRGB"         "sRGB"
call :createpreset "Video"        "video"
goto :EOF

:single
:createpreset
echo %1
colprof  -ql -aG -C "Created with dispcalGUI and Argyll CMS" -D "dispcalGUI calibration preset: %~1" "%~dp0..\misc\ti3\%~2"
move /-Y "%~dp0..\misc\ti3\%~2.ic?" "%~dp0..\dispcalGUI\presets\%~2.icc" && if not exist "%~dp0..\misc\ti3\%~2.ic?" python "%~dp0update_presets.py" "%~2"
echo.
goto :EOF
