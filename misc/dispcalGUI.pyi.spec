# -*- mode: python -*-
sys.path.insert(0, '')
from dispcalGUI.meta import version

a = Analysis([os.path.join('dispcalGUI', 'dispcalGUI.py')],
             pathex=['.'],
             hiddenimports=[],
             hookspath=None)
pyz = PYZ(a.pure)
if sys.platform == 'darwin':
    icon = 'dispcalGUI.icns'
elif sys.platform == 'win32':
    icon = 'dispcalGUI.ico'
else:
    icon = os.path.join('256x256', 'dispcalGUI.png')
if sys.platform == 'win32':
    exe_ext = '.exe'
else:
    exe_ext = ''
exe = EXE(pyz,
          a.scripts,
          exclude_binaries=1,
          name=os.path.join('build', 'pyi.%s' % sys.platform, 'dispcalGUI', 'dispcalGUI%s' % exe_ext),
          debug=False,
          strip=sys.platform != 'win32',
          upx=True,
          console=True,
          icon=os.path.join('dispcalGUI', 'theme', 'icons', icon))
if sys.platform == 'darwin':
    res_dir = os.path.join('..', 'Resources')
else:
    res_dir = '.'
excludes = ['*.backup', '*.bak', '*.~', '.svn']
dist_dir = os.path.join('dist', 'pyi.%s' % sys.platform, 'dispcalGUI-%s' % version)
if sys.platform == "darwin":
    coll_dir = os.path.join('dist', 'pyi.%s' % sys.platform, 'dispcalGUI')
else:
    coll_dir = dist_dir
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               [(os.path.join(res_dir, 'LICENSE.txt'), 'LICENSE.txt', 'DATA'),
                (os.path.join(res_dir, 'README.html'), 'README.html', 'DATA'),
                (os.path.join(res_dir, 'argyll_instruments.json'), os.path.join('dispcalGUI', 'argyll_instruments.json'), 'DATA'),
                (os.path.join(res_dir, 'beep.wav'), os.path.join('dispcalGUI', 'beep.wav'), 'DATA'),
                (os.path.join(res_dir, 'camera_shutter.wav'), os.path.join('dispcalGUI', 'camera_shutter.wav'), 'DATA'),
                (os.path.join(res_dir, 'pnp.ids'), os.path.join('dispcalGUI', 'pnp.ids'), 'DATA'),
                (os.path.join(res_dir, 'test.cal'), os.path.join('dispcalGUI', 'test.cal'), 'DATA'),
                (os.path.join(res_dir, 'icon-windowed.icns'), os.path.join('dispcalGUI', 'theme', 'icons', 'dispcalGUI.icns'), 'DATA')],
               Tree('screenshots', prefix=os.path.join(res_dir, 'screenshots'), excludes=excludes),
               Tree('tests', prefix=os.path.join(res_dir, 'tests'), excludes=excludes),
               Tree('theme', prefix=os.path.join(res_dir, 'theme'), excludes=excludes),
               Tree(os.path.join('dispcalGUI', 'lang'), prefix=os.path.join(res_dir, 'lang'), excludes=excludes),
               Tree(os.path.join('dispcalGUI', 'presets'), prefix=os.path.join(res_dir, 'presets'), excludes=excludes),
               Tree(os.path.join('dispcalGUI', 'ref'), prefix=os.path.join(res_dir, 'ref'), excludes=excludes),
               Tree(os.path.join('dispcalGUI', 'report'), prefix=os.path.join(res_dir, 'report'), excludes=excludes),
               Tree(os.path.join('dispcalGUI', 'theme'), prefix=os.path.join(res_dir, 'theme'), excludes=excludes),
               Tree(os.path.join('dispcalGUI', 'ti1'), prefix=os.path.join(res_dir, 'ti1'), excludes=excludes),
               Tree(os.path.join('dispcalGUI', 'xrc'), prefix=os.path.join(res_dir, 'xrc'), excludes=excludes),
               strip=sys.platform != 'win32',
               upx=True,
               name=coll_dir)
if sys.platform == 'darwin':
    app = BUNDLE(coll,
                 name=os.path.join(dist_dir, 'dispcalGUI.app'))

    # Create ref, tests, ReadMe and license symlinks in directory
    # containing the app bundle
    os.symlink(os.path.join('dispcalGUI.app', 'Contents', 'Resources',
                            'ref'), os.path.join(dist_dir, 'ref'))
    os.symlink(os.path.join('dispcalGUI.app', 'Contents', 'Resources',
                            'tests'), os.path.join(dist_dir, 'tests'))
    os.symlink(os.path.join('dispcalGUI.app', 'Contents', 'Resources',
                            'README.html'), os.path.join(dist_dir,
                                                         'README.html'))
    os.symlink(os.path.join('dispcalGUI.app', 'Contents', 'Resources',
                            'LICENSE.txt'), os.path.join(dist_dir,
                                                         'LICENSE.txt'))
