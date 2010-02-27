#!/bin/sh

cprt="Created with dispcalGUI and Argyll CMS: dispcal"
desc="dispcalGUI calibration preset:"

pushd "`dirname \"$0\"`/../misc/ti3"

for name in "laptop" "office_web" "prepress" "photo" "video" ; do
	case "$name" in
		laptop)
		colprof  -v -ql -aG -C "$cprt -qm -t -g2.4 -f1 -k0 colprof -qm -aS"           -D "$desc Laptop"       "$name";;
	case "$name" in
		office_web)
		colprof  -v -ql -aG -C "$cprt -qm -t6500 -g2.4 -f1 -k0 colprof -qm -aS"       -D "$desc Office & Web" "$name";;
	case "$name" in
		prepress)
		colprof  -v -ql -aG -C "$cprt -qh -t5000 -b130 -g2.4 -f1 -k0 colprof -qh -ax" -D "$desc Prepress"     "$name";;
	case "$name" in
		photo)
		colprof  -v -ql -aG -C "$cprt -qh -t5000 -g2.4 -f1 -k0 colprof -qh -ax"       -D "$desc Photo"        "$name";;
	case "$name" in
		video)
		colprof  -v -ql -aG -C "$cprt -qh -t6500 -g2.4 -f1 -k0 colprof -qm -aS"       -D "$desc Video"        "$name";;
	esac
	mv -i "$name.icc" "`dirname \"$0\"`/../../dispcalGUI/presets/$name.icc"
done

popd
