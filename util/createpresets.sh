#!/bin/sh

cprt="Created with dispcalGUI and Argyll CMS"
desc="dispcalGUI calibration preset:"

pushd "`dirname \"$0\"`/../misc/ti3"

for name in "laptop" "office_web" "madVR" "prepress" "photo" "softproof" "sRGB" "video" ; do
	case "$name" in
		laptop)
		colprof  -v -ql -aG -C "$cprt" -D "$desc Laptop"       "$name";;
	case "$name" in
		madVR)
		colprof  -v -ql -aG -C "$cprt" -D "$desc madVR"        "$name";;
	case "$name" in
		office_web)
		colprof  -v -ql -aG -C "$cprt" -D "$desc Office & Web" "$name";;
	case "$name" in
		prepress)
		colprof  -v -ql -aG -C "$cprt" -D "$desc Prepress"     "$name";;
	case "$name" in
		photo)
		colprof  -v -ql -aG -C "$cprt" -D "$desc Photo"        "$name";;
	case "$name" in
		softproof)
		colprof  -v -ql -aG -C "$cprt" -D "$desc Softproof"    "$name";;
	case "$name" in
		sRGB)
		colprof  -v -ql -aG -C "$cprt" -D "$desc sRGB"         "$name";;
	case "$name" in
		video)
		colprof  -v -ql -aG -C "$cprt" -D "$desc Video"        "$name";;
	esac
	mv -i "$name.icc" "`dirname \"$0\"`/../../dispcalGUI/presets/$name.icc"
done

popd
