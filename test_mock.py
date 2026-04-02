import sys
sys.path.insert(0, '.')

from openfoam_ai.agents.prompt_engine import PromptEngine

# 创建Mock模式的PromptEngine（无API密钥）
engine = PromptEngine(api_key=None)
print("测试Mock模式配置生成")

# 测试不同关键词
test_inputs = [
    "方腔驱动流",
    "管道湍流",
    "翼型可压缩流动",
    "自然对流传热",
    "多相流VOF",
    "随机测试"
]

for inp in test_inputs:
    print(f"\n输入: '{inp}'")
    try:
        config = engine.natural_language_to_config(inp)
        print(f"  物理类型: {config.get('physics_type')}")
        print(f"  求解器: {config.get('solver', {}).get('name')}")
        print(f"  网格: {config.get('geometry', {}).get('mesh_resolution')}")
        print(f"  备注: {config.get('note', '')[:50]}...")
    except Exception as e:
        print(f"  错误: {e}")
        import traceback
        traceback.print_exc()

print("\nMock模式测试完成")