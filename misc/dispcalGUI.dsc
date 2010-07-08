Debtransform-Tar: ${PACKAGE}-${VERSION}.tar.gz
Format: 1.0
Source: ${DEBPACKAGE}
Version: ${VERSION}
Binary: ${DEBPACKAGE}
Maintainer: ${MAINTAINER} <${MAINTAINER_EMAIL}>
Architecture: any
Build-Depends: debhelper (>= 4.1.16), gcc, python (>= ${PY_MINVERSION}), python (<= ${PY_MAXVERSION}), python-all-dev, libxinerama-dev, libxrandr-dev, libxxf86vm-dev
Files: 
 ffffffffffffffffffffffffffffffff 1 ${DEBPACKAGE}_${VERSION}.orig.tar.gz
 ffffffffffffffffffffffffffffffff 1 ${DEBPACKAGE}_${VERSION}-1.diff.tar.gz
