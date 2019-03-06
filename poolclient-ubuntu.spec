# -*- mode: python -*-

block_cipher = None


a = Analysis(['poolclient.py'],
             pathex=['/home/mvogel/yadacoinpoolclient'],
             binaries=[],
             datas=[('yadacoinlogo.png', '.')],
             hiddenimports=['_cffi_backend'],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='poolclient',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          icon='icon.ico',
          console=True )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               name='poolclient')
