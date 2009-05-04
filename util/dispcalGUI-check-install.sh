#!/bin/sh

echo -e "\033[37;40m*** Checking $HOME/.local\033[0m"

#echo -e "\033[0mChecking $HOME/.local/bin/dispcalGUI\033[32m"
ls $HOME/.local/bin/dispcalGUI 2>/dev/null

#echo -e "\033[0mChecking $HOME/.local/lib/python*/site-packages/dispcalGUI*\033[32m"
ls --color=always --group-directories-first -R $HOME/.local/lib/python*/site-packages/dispcalGUI* 2>/dev/null

#echo -e "\033[0mChecking $HOME/.local/share/dispcalGUI\033[32m"
ls --color=always --group-directories-first -R $HOME/.local/share/dispcalGUI 2>/dev/null

#echo -e "\033[0mChecking $HOME/.local/share/doc/dispcalGUI\033[32m"
ls --color=always --group-directories-first -R $HOME/.local/share/doc/dispcalGUI 2>/dev/null

#echo -e "\033[0mChecking $HOME/.local/share/doc/packages/dispcalGUI*\033[32m"
ls --color=always --group-directories-first -R $HOME/.local/share/doc/packages/dispcalGUI* 2>/dev/null

echo "--------------------------------------------------------------------------------"

echo -e "\033[37;40m*** Checking /usr/local\033[0m"

#echo -e "\033[0mChecking /usr/local/bin/dispcalGUI\033[32m"
ls /usr/local/bin/dispcalGUI 2>/dev/null

#echo -e "\033[0mChecking /usr/local/lib/python*/site-packages/dispcalGUI*\033[32m"
ls --color=always --group-directories-first -R /usr/local/lib/python*/site-packages/dispcalGUI* 2>/dev/null

#echo -e "\033[0mChecking /usr/local/share/dispcalGUI\033[32m"
ls --color=always --group-directories-first -R /usr/local/share/dispcalGUI 2>/dev/null

#echo -e "\033[0mChecking /usr/local/share/doc/dispcalGUI\033[32m"
ls --color=always --group-directories-first -R /usr/local/share/doc/dispcalGUI 2>/dev/null

#echo -e "\033[0mChecking /usr/local/share/doc/packages/dispcalGUI*\033[32m"
ls --color=always --group-directories-first -R /usr/local/share/doc/packages/dispcalGUI* 2>/dev/null

echo "--------------------------------------------------------------------------------"

echo -e "\033[37;40m*** Checking /usr\033[0m"

#echo -e "\033[0mChecking /usr/bin/dispcalGUI\033[32m"
ls /usr/bin/dispcalGUI 2>/dev/null

#echo -e "\033[0mChecking /usr/lib/python*/site-packages/dispcalGUI*\033[32m"
ls --color=always --group-directories-first -R /usr/lib/python*/site-packages/dispcalGUI* 2>/dev/null

#echo -e "\033[0mChecking /usr/share/dispcalGUI\033[32m"
ls --color=always --group-directories-first -R /usr/share/dispcalGUI 2>/dev/null

#echo -e "\033[0mChecking /usr/share/doc/dispcalGUI\033[32m"
ls --color=always --group-directories-first -R /usr/share/doc/dispcalGUI 2>/dev/null

#echo -e "\033[0mChecking /usr/share/doc/packages/dispcalGUI*\033[32m"
ls --color=always --group-directories-first -R /usr/share/doc/packages/dispcalGUI* 2>/dev/null

echo "--------------------------------------------------------------------------------"

echo -e "\033[37;40m*** All done\033[0m"
