import os
import sys

def clean_file(path):
    with open(path, 'rb') as f:
        data = f.read()
    if b'\x00' in data:
        print(f'清理空字节: {path} ({data.count(b"\\x00")}个)')
        data = data.replace(b'\x00', b'')
        with open(path, 'wb') as f:
            f.write(data)
        return True
    else:
        # 检查其他异常字符？比如UTF-8 BOM
        if data.startswith(b'\xef\xbb\xbf'):
            print(f'移除UTF-8 BOM: {path}')
            data = data[3:]
            with open(path, 'wb') as f:
                f.write(data)
            return True
    return False

# 清理核心模块
root = 'openfoam_ai'
for dirpath, dirnames, filenames in os.walk(root):
    for fname in filenames:
        if fname.endswith('.py'):
            full = os.path.join(dirpath, fname)
            clean_file(full)

print('清理完成')