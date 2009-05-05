#!/bin/sh

echo -e "\033[37;40m*** Checking $HOME/.local\033[0m"

ls --color=always $HOME/.local/bin/dispcalGUI 2>/dev/null

ls --color=always --group-directories-first -R $HOME/.local/lib/python*/site-packages/dispcalGUI* 2>/dev/null

ls --color=always $HOME/.local/share/applications/dispcalGUI.desktop 2>/dev/null

ls --color=always --group-directories-first -R $HOME/.local/share/dispcalGUI 2>/dev/null

ls --color=always --group-directories-first -R $HOME/.local/share/doc/dispcalGUI 2>/dev/null

ls --color=always --group-directories-first -R $HOME/.local/share/doc/packages/dispcalGUI* 2>/dev/null

ls --color=always $HOME/.local/share/icons/hicolor/*/apps/dispcalGUI.png 2>/dev/null

echo "--------------------------------------------------------------------------------"

echo -e "\033[37;40m*** Checking /usr/local\033[0m"

ls --color=always /usr/local/bin/dispcalGUI 2>/dev/null

ls --color=always --group-directories-first -R /usr/local/lib/python*/site-packages/dispcalGUI* 2>/dev/null

ls --color=always /usr/local/share/applications/dispcalGUI.desktop 2>/dev/null

ls --color=always --group-directories-first -R /usr/local/share/dispcalGUI 2>/dev/null

ls --color=always --group-directories-first -R /usr/local/share/doc/dispcalGUI 2>/dev/null

ls --color=always --group-directories-first -R /usr/local/share/doc/packages/dispcalGUI* 2>/dev/null

ls --color=always /usr/local/share/icons/hicolor/*/apps/dispcalGUI.png 2>/dev/null

echo "--------------------------------------------------------------------------------"

echo -e "\033[37;40m*** Checking /usr\033[0m"

ls --color=always /usr/bin/dispcalGUI 2>/dev/null

ls --color=always --group-directories-first -R /usr/lib/python*/site-packages/dispcalGUI* 2>/dev/null

ls --color=always /usr/share/applications/dispcalGUI.desktop 2>/dev/null

ls --color=always --group-directories-first -R /usr/share/dispcalGUI 2>/dev/null

ls --color=always --group-directories-first -R /usr/share/doc/dispcalGUI 2>/dev/null

ls --color=always --group-directories-first -R /usr/share/doc/packages/dispcalGUI* 2>/dev/null

ls --color=always /usr/share/icons/hicolor/*/apps/dispcalGUI.png 2>/dev/null

echo "--------------------------------------------------------------------------------"

echo -e "\033[37;40m*** All done\033[0m"
