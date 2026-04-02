import sys
sys.path.insert(0, '.')
try:
    from openfoam_ai.core.openfoam_runner import OpenFOAMRunner
    print('导入成功')
except SyntaxError as e:
    print(f'语法错误: {e}')
    import traceback
    traceback.print_exc()
except Exception as e:
    print(f'其他错误: {e}')
    import traceback
    traceback.print_exc()