Debtransform-Tar: ${PACKAGE}-${VERSION}.tar.gz
Format: 1.0
Source: ${DEBPACKAGE}
Version: ${VERSION}
Binary: ${DEBPACKAGE}
Maintainer: ${MAINTAINER} <${MAINTAINER_EMAIL}>
Architecture: all
Build-Depends: debhelper (>= 5.0.38), python
Files: 
 ffffffffffffffffffffffffffffffff 1 ${DEBPACKAGE}_${VERSION}.orig.tar.gz
 ffffffffffffffffffffffffffffffff 1 ${DEBPACKAGE}_${VERSION}-1.diff.tar.gz
