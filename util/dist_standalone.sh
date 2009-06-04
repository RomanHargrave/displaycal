#!/bin/sh

# Standalone executable
./setup.py bdist_pyi -F --use-distutils 2>&1 | tee pyi.log
