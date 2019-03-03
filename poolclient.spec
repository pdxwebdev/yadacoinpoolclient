# -*- mode: python -*-

block_cipher = None


a = Analysis(['poolclient.py'],
             pathex=['X:\\yadacoinpoolclient'],
             binaries=[],
             datas=[],
             hiddenimports=[],
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
          console=True,
          icon='icon.ico' )
coll = COLLECT(exe,
          a.binaries + [('msvcp120.dll', 'C:\\Windows\\System32\\msvcp120.dll', 'BINARY'),
                        ('msvcr120.dll', 'C:\\Windows\\System32\\msvcr120.dll', 'BINARY'),
                        ('libeay32.dll', 'C:\\Program Files\\Python36\\DLLs\\libeay32.dll', 'BINARY'),
                        ('coincurve\\libsecp256k1.dll', 'X:\\yadacoinpoolclient\\libsecp256k1.dll', 'BINARY')],
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               name='poolclient')
