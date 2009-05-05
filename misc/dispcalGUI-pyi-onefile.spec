from distutils.util import get_platform

sys.path.insert(1, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(1, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "util"))

from dispcalGUI.meta import name, version
from winmanifest import mktempmanifest
from winversion import mktempver

manifestpath = mktempmanifest(os.path.join("misc", name + 
	(".exe.VC90.manifest" if hasattr(sys, "version_info") and 
	sys.version_info[:3] == (2,6,1) else ".exe.manifest")))
versionpath = mktempver(os.path.join("misc", "winversion.txt"))

a = Analysis([os.path.join(HOMEPATH,"support","_mountzlib.py"), 
	os.path.join(HOMEPATH,"support","useUnicode.py"), os.path.join(name, 
	name + ".py")], pathex=[os.path.join(name)])
pyz = PYZ(a.pure,
	level=5) # zlib compression level 0-9
exe = EXE(pyz,
	a.scripts + [("O", "", "OPTION")],
	a.binaries + Tree(os.path.join(name, "lang"), "lang", [".svn"])
	+ Tree(os.path.join(name, "presets"), "presets", [".svn"])
	+ Tree(os.path.join(name, "theme"), "theme", ["*.icns", "*.ico", "*.txt",
		".svn", "Thumbs.db", "22x22", "24x24", "48x48", "256x256", 
		"dispcalGUI-uninstall.png"])
	+ Tree(os.path.join(name, "ti1"), "ti1", [".svn"])
	+ [("test.cal", os.path.join(name, "test.cal"), "DATA")],
	name=os.path.join("..", "build", "pyi.%s-onefile" % get_platform(), name + 
		"-" + version, name + (".exe" if sys.platform in ("cygwin", "win32") 
		else "")),
	debug=False,
	strip=sys.platform not in ("cygwin", "win32"),
	upx=False,
	console=True,
	version=versionpath,
	icon=os.path.join(name, "theme", "icons", name + ".ico"),
	manifest=manifestpath,
	append_pkg=True)
data_files = []
if sys.platform in ("cygwin", "win32"):
	data_files += [(os.path.join("theme", "icons", name + "-uninstall.ico"), 
		os.path.join(name, "theme", "icons", name + "-uninstall.ico"), "DATA")]
elif sys.platform != "darwin":
	for size in [16, 22, 24, 32, 48, 256]:
		data_files += [(os.path.join("theme", "icons", size + "x" + size, 
			name + ".png"), os.path.join(name, "theme", "icons", size + "x" + 
			size, name + ".png"), "DATA")]
coll = COLLECT(exe,
	data_files
	+ Tree("screenshots", "screenshots", [".svn", "Thumbs.db"])
	+ Tree("theme", "theme", [".svn", "Thumbs.db"])
	+ [("LICENSE.txt", "LICENSE.txt", "DATA")]
	+ [("README.html", "README.html", "DATA")],
	strip=sys.platform not in("cygwin", "win32"),
	upx=False,
	name=os.path.join("..", "dist", "pyi.%s-onefile" % get_platform(), name + 
		"-" + version))

os.remove(manifestpath)
os.rmdir(os.path.dirname(manifestpath))
os.remove(versionpath)
os.rmdir(os.path.dirname(versionpath))