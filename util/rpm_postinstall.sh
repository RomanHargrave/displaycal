#!/bin/sh

# Update icon cache and menu
which xdg-icon-resource > /dev/null 2>&1 && xdg-icon-resource forceupdate || true
which xdg-desktop-menu > /dev/null 2>&1 && xdg-desktop-menu forceupdate || true
