a = Analysis([os.path.join(HOMEPATH,'support','_mountzlib.py'), os.path.join(HOMEPATH,'support','useUnicode.py'), 'dispcalGUI.py'],
             pathex=['..'])
pyz = PYZ(a.pure)
exe = EXE(pyz,
          a.scripts,
          a.binaries + Tree('lang', 'lang', [])
		   + Tree('presets', 'presets', [])
		   + Tree('theme', 'theme', ['Thumbs.db', '*.ico', '*.icns', '*.txt', '24x24', '48x48', '256x256', 'dispcalGUI-uninstall.png', 'header-readme.png'])
		   + Tree('ti1', 'ti1', [])
		   + [('test.cal', 'test.cal', 'DATA')],
          name=os.path.join('dispcalGUI','dispcalGUI'+('.exe' if sys.platform=='win32' else '')),
          debug=False,
          strip=sys.platform not in('cygwin', 'win32'),
          upx=True,#sys.platform!='win32', # on Windows using upx prevents updating the embedded manifest with reshacker
          console=True , version='winversion.txt', icon=os.path.join('theme','icons','dispcalGUI.ico'),
		  manifest='dispcalGUI.exe.VC90.manifest' if hasattr(sys, "version_info") and sys.version_info[:3] == (2,6,1) else 'dispcalGUI.exe.manifest',
		  append_pkg=True)