all:
	./setup.py build --use-distutils

clean:
	-rm -rf build

dist:
	util/sdist.sh

distclean: clean
	-rm -f INSTALLED_FILES
	-rm -f setuptools-*.egg
	-rm -f use-distutils

html:
	./setup.py readme

install:
	./setup.py install --use-distutils

uninstall:
	./setup.py uninstall --use-distutils
