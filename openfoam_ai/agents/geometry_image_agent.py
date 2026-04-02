"""
Geometry Image Agent - 视觉模型接入与几何图像解析

本模块实现基于视觉模型的几何图像解析功能，用于从用户上传的几何示意图中
提取关键特征并转换为结构化的OpenFOAM配置参数。

遵循AI约束宪法：
- 严禁使用过度简化的二维粗网格代替三维真实网格
- 所有解析结果必须通过Pydantic硬约束验证
- 边界层网格必须满足y+要求
"""

import json
import base64
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

try:
    from PIL import Image
    import numpy as np
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from ..core.validators import (
        SimulationConfig,
        MeshConfig
    )
except ImportError:
    # 作为脚本运行时
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "core"))
    from validators import SimulationConfig, MeshConfig


class GeometryType(Enum):
    """几何类型枚举"""
    RECTANGULAR = "rectangular"  # 矩形
    CIRCULAR = "circular"        # 圆形
    PIPE = "pipe"                # 管道
    CAVITY = "cavity"            # 方腔
    AIRFOIL = "airfoil"          # 翼型
    CUSTOM = "custom"            # 自定义


class BoundaryType(Enum):
    """边界类型枚举"""
    WALL = "wall"
    INLET = "inlet"
    OUTLET = "outlet"
    SYMMETRY = "symmetry"
    PERIODIC = "periodic"


@dataclass
class GeometryFeatures:
    """几何特征数据类"""
    geometry_type: GeometryType
    dimensions: Dict[str, float]  # 长度、宽度、高度等
    boundary_positions: Dict[str, List[float]]  # 边界位置坐标
    aspect_ratio: float  # 长宽比
    is_3d: bool  # 是否三维
    boundary_conditions: List[Dict[str, Any]]  # 边界条件信息
    confidence: float  # 解析置信度 (0-1)
    raw_description: str  # 原始图像描述


class GeometryImageParser:
    """
    几何图像解析器

    功能：
    1. 解析用户上传的几何示意图
    2. 提取关键特征（尺寸、边界位置、拓扑）
    3. 转换为结构化的配置参数
    4. 通过Pydantic硬约束验证
    """

    # 系统提示词（严格遵循AI约束宪法）
    SYSTEM_PROMPT = """你是一位专业的CFD（计算流体力学）几何分析专家，拥有15年工程经验。

【核心任务】
分析用户上传的几何示意图，提取用于OpenFOAM仿真的几何特征参数。

【强制性规则 - 遵循AI约束宪法】
1. 网格分辨率要求：
   - 二维问题：网格数不得少于400（20x20）
   - 三维问题：网格数不得少于8000（20x20x20）
   - 最终测试严禁使用过度简化的二维粗网格代替三维真实网格

2. 几何参数提取精度：
   - 必须提取实际标注的尺寸数值
   - 如无标注，需基于图中比例尺估算
   - 必须识别所有边界类型（入口、出口、壁面、对称面）

3. 边界条件推断：
   - 必须明确每个边界的位置和类型
   - 推断合理的边界条件（如流动入口、压力出口）
   - 识别是否为周期性边界

4. 长宽比限制：
   - 长宽比不得超过100
   - 超过此比例需建议加密网格

【输出格式要求】
必须返回以下JSON格式的结构化数据：
{
    "geometry_type": "rectangular|circular|pipe|cavity|airfoil|custom",
    "dimensions": {
        "length": float,  // 长度（米）
        "width": float,   // 宽度（米）
        "height": float,  // 高度（米，三维）
        "diameter": float // 直径（圆形/管道）
    },
    "boundary_positions": {
        "inlet": [x1, y1, z1],
        "outlet": [x2, y2, z2],
        "walls": [[x1, y1], [x2, y2], ...]
    },
    "aspect_ratio": float,
    "is_3d": boolean,
    "boundary_conditions": [
        {
            "name": "boundary_name",
            "type": "wall|inlet|outlet|symmetry|periodic",
            "location": "位置描述",
            "suggested_condition": "建议的边界条件类型"
        }
    ],
    "confidence": 0.95,  // 解析置信度
    "raw_description": "详细的图像描述文本"
}

【警告】
- 如图像模糊或信息不全，必须降低confidence并说明原因
- 如无法识别关键参数，必须标注为"unknown"而非猜测
- 严禁编造图像中不存在的尺寸或边界
"""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4-vision-preview"):
        """
        初始化几何图像解析器

        Args:
            api_key: OpenAI API密钥（可选，无密钥时使用Mock模式）
            model: 视觉模型名称
        """
        self.api_key = api_key
        self.model = model
        self.client = None

        if OPENAI_AVAILABLE and api_key:
            try:
                self.client = OpenAI(api_key=api_key)
            except Exception as e:
                print(f"[GeometryImageParser] OpenAI初始化失败: {e}")
                print("[GeometryImageParser] 将使用Mock模式")

        self.mock_mode = (self.client is None)

    def encode_image(self, image_path: str) -> str:
        """
        将图像文件编码为base64字符串

        Args:
            image_path: 图像文件路径

        Returns:
            base64编码的图像字符串
        """
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def parse_image(
        self,
        image_path: str,
        user_prompt: Optional[str] = None
    ) -> GeometryFeatures:
        """
        解析几何图像

        Args:
            image_path: 图像文件路径
            user_prompt: 用户额外提示（可选）

        Returns:
            GeometryFeatures对象，包含解析结果
        """
        if self.mock_mode:
            return self._parse_image_mock(image_path, user_prompt)
        else:
            return self._parse_image_vision_api(image_path, user_prompt)

    def _parse_image_vision_api(
        self,
        image_path: str,
        user_prompt: Optional[str] = None
    ) -> GeometryFeatures:
        """
        使用视觉API解析图像

        Args:
            image_path: 图像文件路径
            user_prompt: 用户额外提示

        Returns:
            GeometryFeatures对象
        """
        try:
            base64_image = self.encode_image(image_path)

            prompt = user_prompt or "请分析这张几何示意图，提取OpenFOAM仿真所需的几何特征参数。"

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self.SYSTEM_PROMPT
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000
            )

            response_text = response.choices[0].message.content

            # 提取JSON部分
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1

            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                parsed_data = json.loads(json_str)
            else:
                raise ValueError("响应中未找到有效的JSON格式")

            # 转换为GeometryFeatures对象
            return self._convert_to_geometry_features(parsed_data)

        except Exception as e:
            print(f"[GeometryImageParser] 解析失败: {e}")
            raise

    def _parse_image_mock(
        self,
        image_path: str,
        user_prompt: Optional[str] = None
    ) -> GeometryFeatures:
        """
        Mock模式图像解析（用于测试）

        Args:
            image_path: 图像文件路径
            user_prompt: 用户额外提示

        Returns:
            GeometryFeatures对象
        """
        print("[GeometryImageParser] 使用Mock模式解析图像")

        # 基于文件名推断一些基本信息
        filename = Path(image_path).name.lower()

        # 简单的Mock逻辑
        if "cavity" in filename:
            return GeometryFeatures(
                geometry_type=GeometryType.CAVITY,
                dimensions={"length": 1.0, "width": 1.0, "height": 0.1},
                boundary_positions={
                    "movingWall": [0.5, 1.0, 0.05],
                    "fixedWalls": [[0, 0.5, 0.05], [1.0, 0.5, 0.05]]
                },
                aspect_ratio=1.0,
                is_3d=False,
                boundary_conditions=[
                    {"name": "movingWall", "type": "wall", "location": "顶部",
                     "suggested_condition": "fixedValue (velocity)"},
                    {"name": "fixedWalls", "type": "wall", "location": "其他边界",
                     "suggested_condition": "noSlip"}
                ],
                confidence=0.7,
                raw_description="Mock模式：方腔驱动流几何"
            )
        elif "pipe" in filename:
            return GeometryFeatures(
                geometry_type=GeometryType.PIPE,
                dimensions={"length": 10.0, "diameter": 1.0},
                boundary_positions={
                    "inlet": [0, 0.5, 0],
                    "outlet": [10, 0.5, 0]
                },
                aspect_ratio=10.0,
                is_3d=True,
                boundary_conditions=[
                    {"name": "inlet", "type": "inlet", "location": "左侧",
                     "suggested_condition": "fixedValue (velocity)"},
                    {"name": "outlet", "type": "outlet", "location": "右侧",
                     "suggested_condition": "fixedValue (pressure)"},
                    {"name": "wall", "type": "wall", "location": "管壁",
                     "suggested_condition": "noSlip"}
                ],
                confidence=0.7,
                raw_description="Mock模式：圆管几何"
            )
        else:
            return GeometryFeatures(
                geometry_type=GeometryType.RECTANGULAR,
                dimensions={"length": 2.0, "width": 1.0, "height": 1.0},
                boundary_positions={
                    "inlet": [0, 0.5, 0.5],
                    "outlet": [2.0, 0.5, 0.5]
                },
                aspect_ratio=2.0,
                is_3d=True,
                boundary_conditions=[
                    {"name": "inlet", "type": "inlet", "location": "左侧",
                     "suggested_condition": "fixedValue (velocity)"},
                    {"name": "outlet", "type": "outlet", "location": "右侧",
                     "suggested_condition": "fixedValue (pressure)"}
                ],
                confidence=0.5,
                raw_description="Mock模式：通用矩形几何"
            )

    def _convert_to_geometry_features(self, data: Dict[str, Any]) -> GeometryFeatures:
        """
        将解析的字典数据转换为GeometryFeatures对象

        Args:
            data: 解析的字典数据

        Returns:
            GeometryFeatures对象
        """
        return GeometryFeatures(
            geometry_type=GeometryType(data["geometry_type"]),
            dimensions=data["dimensions"],
            boundary_positions=data["boundary_positions"],
            aspect_ratio=data["aspect_ratio"],
            is_3d=data["is_3d"],
            boundary_conditions=data["boundary_conditions"],
            confidence=data["confidence"],
            raw_description=data["raw_description"]
        )

    def convert_to_simulation_config(
        self,
        features: GeometryFeatures,
        solver_name: str = "icoFoam"
    ) -> SimulationConfig:
        """
        将几何特征转换为OpenFOAM仿真配置

        Args:
            features: 几何特征对象
            solver_name: 求解器名称

        Returns:
            SimulationConfig对象（已通过Pydantic验证）

        Raises:
            ValueError: 如果配置无法通过验证
        """
        try:
            # 根据几何类型推断网格分辨率（遵循宪法要求）
            if features.is_3d:
                nx = ny = nz = 20  # 三维最小20x20x20
                total_cells = nx * ny * nz
            else:
                nx = ny = 20  # 二维最小20x20
                nz = 1
                total_cells = nx * ny

            print(f"[GeometryImageParser] 自动网格分辨率: {nx}x{ny}x{nz} = {total_cells} 单元")
            print(f"[GeometryImageParser] 满足宪法要求: {'是' if total_cells >= (8000 if features.is_3d else 400) else '否'}")

            # 构建几何配置
            if features.geometry_type == GeometryType.PIPE:
                geometry = {
                    "type": "cylindrical",
                    "dimensions": {
                        "L": features.dimensions.get("length", 10.0),
                        "R": features.dimensions.get("diameter", 1.0) / 2.0
                    }
                }
            elif features.geometry_type == GeometryType.CIRCULAR:
                geometry = {
                    "type": "cylindrical",
                    "dimensions": {
                        "L": features.dimensions.get("length", 1.0),
                        "R": features.dimensions.get("diameter", 1.0) / 2.0
                    }
                }
            else:
                # 矩形、方腔等
                geometry = {
                    "type": "rectangular",
                    "dimensions": {
                        "L": features.dimensions.get("length", 1.0),
                        "W": features.dimensions.get("width", 1.0),
                        "H": features.dimensions.get("height", 1.0)
                    }
                }

            # 构建网格配置
            mesh = MeshConfig(
                nx=nx,
                ny=ny,
                nz=nz,
                L=features.dimensions.get("length", 1.0),
                W=features.dimensions.get("width", 1.0),
                H=features.dimensions.get("height", 1.0)
            )

            # 构建求解器配置 (使用camelCase以符合SimulationConfig要求)
            # 确保库朗数满足约束: deltaT <= 0.5 * dx / U
            solver = {
                "name": solver_name,
                "endTime": 0.5,
                "deltaT": 0.001,  # 减小以满足库朗数约束
                "write_interval": 100
            }

            # 构建边界条件（基于提取的特征）
            boundaries = {}
            for bc in features.boundary_conditions:
                boundary_name = bc["name"]
                boundary_type = bc["type"]

                # 创建边界条件对象
                boundaries[boundary_name] = {
                    "type": self._map_boundary_type_to_openfoam(boundary_type),
                    "name": boundary_name
                }

            # 构建完整配置
            config_dict = {
                "task_id": f"geometry_parse_{int(datetime.now().timestamp())}",
                "physics_type": "incompressible",  # 默认不可压流
                "geometry": mesh.dict(),
                "solver": solver,
                "boundary_conditions": boundaries,
                "nu": 1e-05,  # 默认运动粘度
                "rho": 1.0   # 默认密度
            }

            # 通过Pydantic验证（强制约束）
            config = SimulationConfig(**config_dict)

            print(f"[GeometryImageParser] 配置验证通过")
            print(f"[GeometryImageParser] 解析置信度: {features.confidence:.2%}")

            return config

        except Exception as e:
            print(f"[GeometryImageParser] 配置转换失败: {e}")
            raise ValueError(f"配置转换失败: {e}")

    def _map_boundary_type_to_openfoam(self, boundary_type: str) -> str:
        """
        将边界类型映射到OpenFOAM边界条件类型

        Args:
            boundary_type: 边界类型（wall, inlet, outlet, symmetry, periodic）

        Returns:
            OpenFOAM边界条件类型
        """
        mapping = {
            "wall": "noSlip",
            "inlet": "fixedValue",
            "outlet": "fixedValue",
            "symmetry": "zeroGradient",
            "periodic": "cyclic"
        }
        return mapping.get(boundary_type, "fixedValue")

    def validate_confidence(self, features: GeometryFeatures, threshold: float = 0.7) -> bool:
        """
        验证解析置信度

        Args:
            features: 几何特征对象
            threshold: 置信度阈值（默认0.7）

        Returns:
            是否通过置信度验证
        """
        passed = features.confidence >= threshold

        if not passed:
            print(f"[GeometryImageParser] 警告: 解析置信度 {features.confidence:.2%} 低于阈值 {threshold:.2%}")
            print(f"[GeometryImageParser] 建议: 用户提供更清晰的图像或补充尺寸标注")

        return passed


def create_geometry_parser(api_key: Optional[str] = None) -> GeometryImageParser:
    """
    工厂函数：创建几何图像解析器

    Args:
        api_key: OpenAI API密钥（可选）

    Returns:
        GeometryImageParser实例
    """
    return GeometryImageParser(api_key=api_key)