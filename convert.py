import os

def convert_to_utf8(path):
    with open(path, 'rb') as f:
        raw = f.read()
    # 检测BOM
    if raw.startswith(b'\xff\xfe'):
        # UTF-16 LE
        content = raw.decode('utf-16')
        print(f'转换 {path}: UTF-16 LE -> UTF-8')
    elif raw.startswith(b'\xfe\xff'):
        # UTF-16 BE
        content = raw.decode('utf-16-be')
        print(f'转换 {path}: UTF-16 BE -> UTF-8')
    elif raw.startswith(b'\xef\xbb\xbf'):
        # UTF-8 with BOM
        content = raw[3:].decode('utf-8')
        print(f'转换 {path}: UTF-8 BOM -> UTF-8')
    else:
        # 尝试UTF-8
        try:
            content = raw.decode('utf-8')
        except UnicodeDecodeError:
            # 回退到latin-1
            content = raw.decode('latin-1')
            print(f'转换 {path}: 未知编码 -> Latin-1')
        return
    # 以UTF-8无BOM写入
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'已写入UTF-8')

# 转换core/__init__.py
convert_to_utf8('openfoam_ai/core/__init__.py')
# 可能还有其他文件
for root, dirs, files in os.walk('openfoam_ai'):
    for f in files:
        if f.endswith('.py'):
            convert_to_utf8(os.path.join(root, f))