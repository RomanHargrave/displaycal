@echo off
setlocal

call :createpreset "Laptop"       "laptop"
call :createpreset "madVR"        "madVR"
call :createpreset "Office & Web" "office_web"
call :createpreset "Photo"        "photo"
call :createpreset "Prepress"     "prepress"
call :createpreset "Softproof"    "softproof"
call :createpreset "sRGB"         "sRGB"
call :createpreset "Video"        "video"
goto :EOF

:createpreset
echo %1
colprof  -ql -aG -C "Created with dispcalGUI and Argyll CMS" -D "dispcalGUI calibration preset: %~1" "%~dp0..\misc\ti3\%~2"
move /-Y "%~dp0..\misc\ti3\%~2.ic?" "%~dp0..\dispcalGUI\presets\%~2.icc" && if not exist "%~dp0..\misc\ti3\%~2.ic?" python "%~dp0update_presets.py" "%~2"
echo.
goto :EOF
