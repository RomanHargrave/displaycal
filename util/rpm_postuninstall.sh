#!/bin/sh

which xdg-desktop-menu 2>&1 >/dev/null && xdg-desktop-menu forceupdate || true
which xdg-icon-resource 2>&1 >/dev/null && xdg-icon-resource forceupdate || true
