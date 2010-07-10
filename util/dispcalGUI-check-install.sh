#!/bin/bash

echo -e "\033[37;40m*** Checking $HOME/.local\033[0m"

ls -l -G -h --color=always $HOME/.local/bin/dispcalGUI 2>/dev/null && echo

ls -l -G -h --color=always --group-directories-first -R $HOME/.local/lib/python*/*-packages/dispcalGUI* 2>/dev/null && echo

ls -l -G -h --color=always $HOME/.local/share/applications/dispcalGUI.desktop 2>/dev/null && echo

ls -l -G -h --color=always --group-directories-first -R $HOME/.local/share/dispcalGUI 2>/dev/null && echo

ls -l -G -h --color=always --group-directories-first -R $HOME/.local/share/doc/dispcalGUI* 2>/dev/null && echo

ls -l -G -h --color=always --group-directories-first -R $HOME/.local/share/doc/packages/dispcalGUI* 2>/dev/null && echo

ls -l -G -h --color=always $HOME/.local/share/icons/hicolor/*/apps/dispcalGUI.png 2>/dev/null

echo "--------------------------------------------------------------------------------"

echo -e "\033[37;40m*** Checking /usr/local\033[0m"

ls -l -G -h --color=always /usr/local/bin/dispcalGUI 2>/dev/null && echo

ls -l -G -h --color=always --group-directories-first -R /usr/local/lib/python*/*-packages/dispcalGUI* 2>/dev/null && echo

ls -l -G -h --color=always /usr/local/share/applications/dispcalGUI.desktop 2>/dev/null && echo

ls -l -G -h --color=always --group-directories-first -R /usr/local/share/dispcalGUI 2>/dev/null && echo

ls -l -G -h --color=always --group-directories-first -R /usr/local/share/doc/dispcalGUI* 2>/dev/null && echo

ls -l -G -h --color=always --group-directories-first -R /usr/local/share/doc/packages/dispcalGUI* 2>/dev/null && echo

ls -l -G -h --color=always /usr/local/share/icons/hicolor/*/apps/dispcalGUI.png 2>/dev/null

echo "--------------------------------------------------------------------------------"

echo -e "\033[37;40m*** Checking /usr\033[0m"

ls -l -G -h --color=always /usr/bin/dispcalGUI 2>/dev/null && echo

ls -l -G -h --color=always --group-directories-first -R /usr/lib/python*/*-packages/dispcalGUI* 2>/dev/null && echo

ls -l -G -h --color=always /usr/share/applications/dispcalGUI.desktop 2>/dev/null && echo

ls -l -G -h --color=always --group-directories-first -R /usr/share/dispcalGUI 2>/dev/null && echo

ls -l -G -h --color=always --group-directories-first -R /usr/share/doc/dispcalGUI* 2>/dev/null && echo

ls -l -G -h --color=always --group-directories-first -R /usr/share/doc/packages/dispcalGUI* 2>/dev/null && echo

ls -l -G -h --color=always /usr/share/icons/hicolor/*/apps/dispcalGUI.png 2>/dev/null

echo "--------------------------------------------------------------------------------"

echo -e "\033[37;40m*** Checking /etc/hotplug/usb\033[0m"

ls -l -G -h --color=always --group-directories-first -R /etc/hotplug/usb/Argyll* 2>/dev/null

echo "--------------------------------------------------------------------------------"

echo -e "\033[37;40m*** Checking /etc/udev\033[0m"

ls -l -G -h --color=always --group-directories-first -R /etc/udev/*/*-Argyll.* 2>/dev/null

echo "--------------------------------------------------------------------------------"

echo -e "\033[37;40m*** Checking /usr/share/PolicyKit/policy\033[0m"

ls -l -G -h --color=always /usr/share/PolicyKit/policy/color-device-file.policy 2>/dev/null

echo "--------------------------------------------------------------------------------"

echo -e "\033[37;40m*** Checking /usr/share/hal/fdi/policy/10osvendor\033[0m"

ls -l -G -h --color=always /usr/share/hal/fdi/policy/10osvendor/19-color.fdi 2>/dev/null

echo "--------------------------------------------------------------------------------"

echo -e "\033[37;40m*** All done\033[0m"
