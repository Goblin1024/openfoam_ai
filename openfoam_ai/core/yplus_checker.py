"""
y+ 值与边界层网格质量检查模块

提供：
- 基于流动参数的y+估算
- 壁面函数兼容性检查
- 第一层网格高度推荐
- 边界层网格参数建议（膨胀层数、膨胀比）

参考：
- Schlichting, H. (1979). Boundary-Layer Theory. McGraw-Hill.
- White, F. M. (2006). Viscous Fluid Flow. McGraw-Hill.
- OpenFOAM User Guide: Wall Functions and Turbulence Models
"""

import math
import re
import logging
from typing import Dict, Optional, Tuple, List
from pathlib import Path

logger = logging.getLogger(__name__)


class YPlusChecker:
    """y+ 值与边界层网格质量检查器
    
    提供：
    - 基于流动参数的y+估算
    - 壁面函数兼容性检查
    - 第一层网格高度推荐
    - 边界层网格参数建议（膨胀层数、膨胀比）
    """
    
    # 壁面函数与y+要求映射
    WALL_FUNCTION_REQUIREMENTS = {
        # 高Re壁面函数（不解析边界层）
        "kqRWallFunction": {"yplus_min": 30, "yplus_max": 300, "category": "high_Re"},
        "nutkWallFunction": {"yplus_min": 30, "yplus_max": 300, "category": "high_Re"},
        "nutUWallFunction": {"yplus_min": 30, "yplus_max": 300, "category": "high_Re"},
        "epsilonWallFunction": {"yplus_min": 30, "yplus_max": 300, "category": "high_Re"},
        "omegaWallFunction": {"yplus_min": 30, "yplus_max": 300, "category": "high_Re"},
        # 低Re壁面处理（解析边界层）
        "nutLowReWallFunction": {"yplus_min": 0, "yplus_max": 5, "category": "low_Re"},
        "nutUSpaldingWallFunction": {"yplus_min": 0, "yplus_max": 300, "category": "adaptive"},
        # k-omega SST 自动壁面处理
        "kOmegaSST_auto": {"yplus_min": 0, "yplus_max": 300, "category": "adaptive", 
                            "note": "k-omega SST可自动切换，但y+<5时精度最高"},
    }
    
    # 湍流模型与壁面函数推荐
    TURBULENCE_MODEL_WALL_FUNCTIONS = {
        "kEpsilon": {"default_wf": "high_Re", "recommended_yplus": (30, 100)},
        "kOmegaSST": {"default_wf": "adaptive", "recommended_yplus": (0.5, 5), "note": "建议y+≈1以获得最佳精度"},
        "realizableKE": {"default_wf": "high_Re", "recommended_yplus": (30, 100)},
        "SpalartAllmaras": {"default_wf": "adaptive", "recommended_yplus": (0.5, 5)},
        "LES": {"default_wf": "low_Re", "recommended_yplus": (0.5, 2), "note": "LES需要非常精细的壁面网格"},
    }
    
    # 默认膨胀比范围
    DEFAULT_EXPANSION_RATIO_RANGE = (1.1, 1.3)
    
    # 默认边界层网格层数范围
    DEFAULT_N_LAYERS_RANGE = (5, 20)
    
    def __init__(self):
        """初始化y+检查器"""
        logger.debug("YPlusChecker initialized")
    
    def estimate_yplus(self, Re: float, L: float, first_cell_height: float, 
                       rho: float = 1.0, mu: float = 1e-3) -> float:
        """
        估算y+值
        
        基于平板湍流边界层经验公式（Schlichting边界层理论）：
        Cf = 0.058 * Re_L^(-0.2)  (湍流平板摩擦系数)
        tau_w = 0.5 * Cf * rho * U^2
        u_tau = sqrt(tau_w / rho)
        y+ = u_tau * y / nu
        
        Args:
            Re: 雷诺数 (基于特征长度L)
            L: 特征长度 (m)
            first_cell_height: 第一层网格高度 (m)
            rho: 流体密度 (kg/m³)，默认1.0
            mu: 动力粘度 (Pa·s)，默认1e-3
            
        Returns:
            float: 估算的y+值
            
        Reference:
            Schlichting, H. (1979). Boundary-Layer Theory, 7th Ed., McGraw-Hill.
            公式 (21.12): Cf = 0.0592 * Re^(-0.2) for 5e5 < Re < 1e7
        """
        if Re <= 0 or L <= 0 or first_cell_height <= 0:
            logger.warning(f"Invalid input: Re={Re}, L={L}, first_cell_height={first_cell_height}")
            return 0.0
        
        # 运动粘度
        nu = mu / rho
        
        # 估算来流速度 (从雷诺数反推)
        U = Re * nu / L
        
        # 湍流摩擦系数 (Prandtl-Schlichting公式，适用于湍流平板)
        # Cf = 0.058 * Re^(-0.2) 适用于 5e5 < Re < 1e7
        if Re < 5e5:
            # 层流情况使用Blasius解
            Cf = 1.328 / math.sqrt(Re)
            logger.debug(f"Using laminar Cf formula (Re={Re:.2e} < 5e5)")
        else:
            # 湍流情况
            Cf = 0.058 * (Re ** (-0.2))
            logger.debug(f"Using turbulent Cf formula (Re={Re:.2e})")
        
        # 壁面剪切应力
        tau_w = 0.5 * Cf * rho * (U ** 2)
        
        # 摩擦速度
        u_tau = math.sqrt(tau_w / rho)
        
        # y+值
        y_plus = u_tau * first_cell_height / nu
        
        logger.debug(f"Estimated y+: {y_plus:.2f} (Re={Re:.2e}, U={U:.2f} m/s, y={first_cell_height:.2e} m)")
        
        return y_plus
    
    def recommend_first_cell_height(self, Re: float, L: float, target_yplus: float = 1.0,
                                    rho: float = 1.0, mu: float = 1e-3) -> Dict:
        """
        推荐第一层网格高度
        
        基于目标y+值反算第一层网格高度：
        y = y+ * nu / u_tau
        
        Args:
            Re: 雷诺数
            L: 特征长度 (m)
            target_yplus: 目标y+值，默认1.0
            rho: 流体密度 (kg/m³)，默认1.0
            mu: 动力粘度 (Pa·s)，默认1e-3
            
        Returns:
            Dict: {
                "first_cell_height": float,  # 推荐的第一层网格高度 (m)
                "unit": str,                 # 单位
                "target_yplus": float,       # 目标y+值
                "estimated_yplus": float,    # 估算的y+值
                "note": str                  # 说明
            }
        """
        if Re <= 0 or L <= 0 or target_yplus <= 0:
            return {
                "first_cell_height": 0.0,
                "unit": "m",
                "target_yplus": target_yplus,
                "estimated_yplus": 0.0,
                "note": "错误：输入参数必须为正数"
            }
        
        nu = mu / rho
        U = Re * nu / L
        
        # 计算摩擦系数
        if Re < 5e5:
            Cf = 1.328 / math.sqrt(Re)
        else:
            Cf = 0.058 * (Re ** (-0.2))
        
        tau_w = 0.5 * Cf * rho * (U ** 2)
        u_tau = math.sqrt(tau_w / rho)
        
        # 反算第一层网格高度
        first_cell_height = target_yplus * nu / u_tau
        
        # 验证
        estimated_yplus = self.estimate_yplus(Re, L, first_cell_height, rho, mu)
        
        note = f"基于Re={Re:.2e}和target_y+={target_yplus}计算"
        
        logger.info(f"Recommended first cell height: {first_cell_height:.2e} m for y+={target_yplus}")
        
        return {
            "first_cell_height": first_cell_height,
            "unit": "m",
            "target_yplus": target_yplus,
            "estimated_yplus": estimated_yplus,
            "note": note
        }
    
    def check_yplus_compatibility(self, estimated_yplus: float, 
                                   turbulence_model: str) -> Dict:
        """
        检查y+值与湍流模型壁面处理的兼容性
        
        Args:
            estimated_yplus: 估算的y+值
            turbulence_model: 湍流模型名称 (如 "kOmegaSST", "kEpsilon")
            
        Returns:
            Dict: {
                "compatible": bool,          # 是否兼容
                "estimated_yplus": float,    # 输入的y+值
                "required_range": Tuple,     # 要求的y+范围
                "recommendation": str,       # 建议
                "severity": str              # 严重程度: "ok", "warning", "error"
            }
        """
        # 获取湍流模型的推荐范围
        model_info = self.TURBULENCE_MODEL_WALL_FUNCTIONS.get(
            turbulence_model, 
            {"recommended_yplus": (0.5, 300), "note": "未知模型，使用通用范围"}
        )
        
        yplus_min, yplus_max = model_info["recommended_yplus"]
        
        # 检查兼容性
        compatible = yplus_min <= estimated_yplus <= yplus_max
        
        # 确定严重程度和建议
        if compatible:
            if turbulence_model == "kOmegaSST" and estimated_yplus > 5:
                severity = "warning"
                recommendation = (
                    f"y+={estimated_yplus:.1f}在可接受范围内，但k-omega SST在y+≈1时精度最高。"
                    f"建议减小第一层网格高度以获得更好的边界层解析。"
                )
            else:
                severity = "ok"
                recommendation = f"y+={estimated_yplus:.1f}符合{turbulence_model}模型的要求"
        else:
            if estimated_yplus < yplus_min:
                severity = "warning"
                recommendation = (
                    f"y+={estimated_yplus:.2f}过低（最小要求{yplus_min}）。"
                    f"可适当增大第一层网格高度以减少计算量。"
                )
            else:  # estimated_yplus > yplus_max
                severity = "error"
                recommendation = (
                    f"y+={estimated_yplus:.1f}过高（最大允许{yplus_max}）。"
                    f"必须减小第一层网格高度，建议减半或更多。"
                )
        
        # 添加模型特定说明
        note = model_info.get("note", "")
        if note:
            recommendation += f" [{note}]"
        
        logger.debug(f"y+ compatibility check: {turbulence_model}, y+={estimated_yplus:.2f}, "
                    f"compatible={compatible}, severity={severity}")
        
        return {
            "compatible": compatible,
            "estimated_yplus": estimated_yplus,
            "required_range": (yplus_min, yplus_max),
            "recommendation": recommendation,
            "severity": severity
        }
    
    def estimate_boundary_layer_thickness(self, Re: float, L: float) -> float:
        """
        估算边界层厚度
        
        基于平板湍流边界层厚度公式（Schlichting理论）：
        delta = 0.37 * L * Re^(-0.2)
        
        Args:
            Re: 雷诺数
            L: 特征长度 (m)
            
        Returns:
            float: 边界层厚度 (m)
            
        Reference:
            Schlichting, H. (1979). Boundary-Layer Theory, 7th Ed., Eq. (21.16)
        """
        if Re <= 0 or L <= 0:
            return 0.0
        
        if Re < 5e5:
            # 层流边界层: delta = 5.0 * L / sqrt(Re)
            delta = 5.0 * L / math.sqrt(Re)
            logger.debug(f"Using laminar BL thickness formula (Re={Re:.2e})")
        else:
            # 湍流边界层
            delta = 0.37 * L * (Re ** (-0.2))
            logger.debug(f"Using turbulent BL thickness formula (Re={Re:.2e})")
        
        return delta
    
    def calculate_expansion_layers(self, first_cell_height: float, 
                                    total_thickness: float, 
                                    expansion_ratio: float) -> int:
        """
        计算达到指定总厚度所需的膨胀层数
        
        几何级数求和: S_n = h1 * (r^n - 1) / (r - 1)
        反解: n = ln(S_n*(r-1)/h1 + 1) / ln(r)
        
        Args:
            first_cell_height: 第一层网格高度 (m)
            total_thickness: 边界层总厚度 (m)
            expansion_ratio: 膨胀比
            
        Returns:
            int: 建议的层数
        """
        if first_cell_height <= 0 or total_thickness <= 0 or expansion_ratio <= 1.0:
            return 0
        
        if total_thickness <= first_cell_height:
            return 1
        
        # 几何级数求和反解层数
        n = math.log((total_thickness * (expansion_ratio - 1) / first_cell_height) + 1) / math.log(expansion_ratio)
        
        # 向上取整并限制范围
        n_layers = min(max(int(math.ceil(n)), self.DEFAULT_N_LAYERS_RANGE[0]), 
                       self.DEFAULT_N_LAYERS_RANGE[1])
        
        return n_layers
    
    def generate_boundary_layer_advice(self, Re: float, L: float, 
                                        turbulence_model: str = "kOmegaSST",
                                        target_yplus: float = None,
                                        rho: float = 1.0, 
                                        mu: float = 1e-3) -> Dict:
        """
        生成完整的边界层网格建议
        
        Args:
            Re: 雷诺数
            L: 特征长度 (m)
            turbulence_model: 湍流模型，默认"kOmegaSST"
            target_yplus: 目标y+值，None则使用模型推荐值
            rho: 流体密度 (kg/m³)，默认1.0
            mu: 动力粘度 (Pa·s)，默认1e-3
            
        Returns:
            Dict: {
                "first_cell_height": float,      # 第一层网格高度 (m)
                "expansion_ratio": float,        # 膨胀比
                "n_layers": int,                 # 膨胀层数
                "total_bl_thickness": float,     # 边界层总厚度 (m)
                "target_yplus": float,           # 目标y+值
                "estimated_yplus": float,        # 估算的y+值
                "explanation": str               # 详细说明
            }
        """
        # 确定目标y+值
        if target_yplus is None:
            model_info = self.TURBULENCE_MODEL_WALL_FUNCTIONS.get(
                turbulence_model, 
                {"recommended_yplus": (0.5, 5)}
            )
            target_yplus = model_info["recommended_yplus"][0]  # 取下限作为目标
        
        # 计算第一层网格高度
        height_result = self.recommend_first_cell_height(
            Re, L, target_yplus, rho, mu
        )
        first_cell_height = height_result["first_cell_height"]
        estimated_yplus = height_result["estimated_yplus"]
        
        # 估算边界层厚度
        bl_thickness = self.estimate_boundary_layer_thickness(Re, L)
        
        # 确定膨胀比（根据湍流模型）
        if turbulence_model in ["kOmegaSST", "SpalartAllmaras", "LES"]:
            # 低Re模型需要更平滑的过渡
            expansion_ratio = 1.2
        else:
            # 高Re壁面函数可以使用稍大的膨胀比
            expansion_ratio = 1.3
        
        # 计算层数（覆盖边界层厚度的80%）
        target_thickness = 0.8 * bl_thickness
        n_layers = self.calculate_expansion_layers(
            first_cell_height, target_thickness, expansion_ratio
        )
        
        # 计算实际总厚度
        if n_layers > 0 and expansion_ratio > 1.0:
            actual_thickness = first_cell_height * ((expansion_ratio ** n_layers) - 1) / (expansion_ratio - 1)
        else:
            actual_thickness = first_cell_height * n_layers
        
        # 生成说明
        explanation = (
            f"对于Re={Re:.2e}的{turbulence_model}湍流模拟:\n"
            f"  - 估算边界层厚度: {bl_thickness:.4e} m\n"
            f"  - 目标y+值: {target_yplus:.1f} (基于{turbulence_model}模型要求)\n"
            f"  - 推荐第一层网格高度: {first_cell_height:.4e} m\n"
            f"  - 膨胀比: {expansion_ratio:.1f}\n"
            f"  - 建议膨胀层数: {n_layers}层\n"
            f"  - 覆盖边界层厚度: {actual_thickness:.4e} m ({actual_thickness/bl_thickness*100:.1f}%)\n"
        )
        
        if turbulence_model == "kOmegaSST":
            explanation += (
                "  - 注意: k-omega SST模型可自动处理y+过渡，但为获得最佳精度，"
                "建议保持y+≈1并确保边界层内有至少10-15层网格"
            )
        elif turbulence_model in ["kEpsilon", "realizableKE"]:
            explanation += (
                "  - 注意: k-epsilon模型使用高Re壁面函数，要求30<y+<300，"
                "第一层网格必须位于对数律区域"
            )
        
        logger.info(f"Generated BL advice for {turbulence_model}: y+={estimated_yplus:.2f}, "
                   f"h1={first_cell_height:.2e}m, n={n_layers}")
        
        return {
            "first_cell_height": first_cell_height,
            "expansion_ratio": expansion_ratio,
            "n_layers": n_layers,
            "total_bl_thickness": actual_thickness,
            "boundary_layer_thickness": bl_thickness,
            "target_yplus": target_yplus,
            "estimated_yplus": estimated_yplus,
            "explanation": explanation
        }
    
    def parse_yplus_from_postprocessing(self, case_dir: str) -> Dict:
        """
        解析postProcessing/yPlus目录下的y+数据
        
        Args:
            case_dir: 算例目录路径
            
        Returns:
            Dict: {
                "min": float,
                "max": float,
                "avg": float,
                "patches": Dict[str, Dict]  # 各边界的y+统计
            }
        """
        case_path = Path(case_dir)
        yplus_dir = case_path / "postProcessing" / "yPlus"
        
        result = {
            "min": 0.0,
            "max": 0.0,
            "avg": 0.0,
            "patches": {}
        }
        
        if not yplus_dir.exists():
            logger.warning(f"yPlus directory not found: {yplus_dir}")
            return result
        
        # 查找最新的yPlus文件
        yplus_files = list(yplus_dir.glob("*.dat")) + list(yplus_dir.glob("yPlus*"))
        
        if not yplus_files:
            logger.warning(f"No yPlus data files found in {yplus_dir}")
            return result
        
        # 读取最新的文件
        latest_file = max(yplus_files, key=lambda p: p.stat().st_mtime)
        
        try:
            content = latest_file.read_text(encoding='utf-8')
            
            # 解析OpenFOAM yPlus输出格式
            # 格式示例: patchName min max average
            patches_data = {}
            
            for line in content.split('\n'):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                parts = line.split()
                if len(parts) >= 4:
                    patch_name = parts[0]
                    try:
                        y_min = float(parts[1])
                        y_max = float(parts[2])
                        y_avg = float(parts[3])
                        
                        patches_data[patch_name] = {
                            "min": y_min,
                            "max": y_max,
                            "avg": y_avg
                        }
                    except ValueError:
                        continue
            
            # 计算全局统计
            if patches_data:
                all_mins = [d["min"] for d in patches_data.values()]
                all_maxs = [d["max"] for d in patches_data.values()]
                all_avgs = [d["avg"] for d in patches_data.values()]
                
                result["min"] = min(all_mins)
                result["max"] = max(all_maxs)
                result["avg"] = sum(all_avgs) / len(all_avgs)
                result["patches"] = patches_data
                
                logger.info(f"Parsed y+ data: min={result['min']:.2f}, max={result['max']:.2f}, "
                           f"avg={result['avg']:.2f}")
            
        except Exception as e:
            logger.error(f"Error parsing yPlus file {latest_file}: {e}")
        
        return result
    
    def check_mesh_yplus_quality(self, Re: float, L: float, 
                                  first_cell_height: float,
                                  turbulence_model: str = "kOmegaSST",
                                  rho: float = 1.0, 
                                  mu: float = 1e-3) -> Dict:
        """
        综合检查网格y+质量
        
        Args:
            Re: 雷诺数
            L: 特征长度 (m)
            first_cell_height: 第一层网格高度 (m)
            turbulence_model: 湍流模型
            rho: 流体密度 (kg/m³)
            mu: 动力粘度 (Pa·s)
            
        Returns:
            Dict: 包含y+估算、兼容性检查和建议的完整报告
        """
        # 估算y+
        yplus = self.estimate_yplus(Re, L, first_cell_height, rho, mu)
        
        # 检查兼容性
        compatibility = self.check_yplus_compatibility(yplus, turbulence_model)
        
        # 生成边界层建议
        advice = self.generate_boundary_layer_advice(
            Re, L, turbulence_model, None, rho, mu
        )
        
        # 综合评估
        quality_score = 100.0
        
        if compatibility["severity"] == "error":
            quality_score -= 40
        elif compatibility["severity"] == "warning":
            quality_score -= 20
        
        # 检查第一层网格高度与推荐值的偏差
        if advice["first_cell_height"] > 0:
            ratio = first_cell_height / advice["first_cell_height"]
            if ratio > 2.0 or ratio < 0.5:
                quality_score -= 15
        
        quality_score = max(0.0, min(100.0, quality_score))
        
        return {
            "yplus": yplus,
            "compatibility": compatibility,
            "advice": advice,
            "quality_score": quality_score,
            "passed": compatibility["severity"] != "error" and quality_score >= 60,
            "summary": (
                f"y+={yplus:.2f}, 质量评分={quality_score:.0f}/100, "
                f"状态={'通过' if compatibility['severity'] != 'error' else '未通过'}"
            )
        }
    
    def get_wall_function_recommendation(self, turbulence_model: str, 
                                          target_yplus: float = None) -> Dict:
        """
        获取壁面函数推荐
        
        Args:
            turbulence_model: 湍流模型名称
            target_yplus: 目标y+值（可选）
            
        Returns:
            Dict: 壁面函数推荐信息
        """
        model_info = self.TURBULENCE_MODEL_WALL_FUNCTIONS.get(
            turbulence_model,
            {"default_wf": "adaptive", "recommended_yplus": (0.5, 300)}
        )
        
        wf_category = model_info["default_wf"]
        
        # 根据类别推荐具体壁面函数
        if wf_category == "high_Re":
            recommended_wf = ["nutkWallFunction", "epsilonWallFunction"]
            yplus_range = (30, 300)
        elif wf_category == "low_Re":
            recommended_wf = ["nutLowReWallFunction"]
            yplus_range = (0, 5)
        else:  # adaptive
            recommended_wf = ["nutUSpaldingWallFunction", "omegaWallFunction"]
            yplus_range = (0.5, 5) if target_yplus and target_yplus < 10 else (30, 300)
        
        return {
            "turbulence_model": turbulence_model,
            "wall_function_category": wf_category,
            "recommended_wall_functions": recommended_wf,
            "yplus_range": yplus_range,
            "note": model_info.get("note", "")
        }


# 便捷函数接口
def estimate_yplus(Re: float, L: float, first_cell_height: float,
                   rho: float = 1.0, mu: float = 1e-3) -> float:
    """便捷函数：估算y+值"""
    checker = YPlusChecker()
    return checker.estimate_yplus(Re, L, first_cell_height, rho, mu)


def recommend_first_cell_height(Re: float, L: float, target_yplus: float = 1.0,
                                 rho: float = 1.0, mu: float = 1e-3) -> Dict:
    """便捷函数：推荐第一层网格高度"""
    checker = YPlusChecker()
    return checker.recommend_first_cell_height(Re, L, target_yplus, rho, mu)


def check_yplus_compatibility(estimated_yplus: float, turbulence_model: str) -> Dict:
    """便捷函数：检查y+兼容性"""
    checker = YPlusChecker()
    return checker.check_yplus_compatibility(estimated_yplus, turbulence_model)


if __name__ == "__main__":
    # 模块测试
    print("YPlusChecker 模块测试")
    print("=" * 70)
    
    checker = YPlusChecker()
    
    # 测试参数
    Re = 50000  # 雷诺数
    L = 1.0     # 特征长度 1m
    h = 0.001   # 第一层网格高度 1mm
    
    print(f"\n测试参数: Re={Re}, L={L}m, first_cell_height={h}m")
    print("-" * 70)
    
    # 测试1: y+估算
    yplus = checker.estimate_yplus(Re, L, h)
    print(f"\n1. y+估算: y+ = {yplus:.2f}")
    
    # 测试2: 推荐第一层网格高度
    for target in [1.0, 30.0, 50.0]:
        result = checker.recommend_first_cell_height(Re, L, target)
        print(f"\n2. 目标y+={target}时:")
        print(f"   推荐第一层网格高度: {result['first_cell_height']:.4e} m")
    
    # 测试3: 兼容性检查
    print("\n3. y+兼容性检查:")
    for model in ["kOmegaSST", "kEpsilon", "SpalartAllmaras"]:
        compat = checker.check_yplus_compatibility(yplus, model)
        print(f"   {model}: {compat['severity']} - {compat['recommendation'][:50]}...")
    
    # 测试4: 边界层建议
    print("\n4. 边界层网格建议 (kOmegaSST):")
    advice = checker.generate_boundary_layer_advice(Re, L, "kOmegaSST")
    print(f"   第一层高度: {advice['first_cell_height']:.4e} m")
    print(f"   膨胀比: {advice['expansion_ratio']}")
    print(f"   层数: {advice['n_layers']}")
    print(f"   边界层厚度: {advice['boundary_layer_thickness']:.4e} m")
    
    # 测试5: 综合质量检查
    print("\n5. 网格y+质量检查:")
    quality = checker.check_mesh_yplus_quality(Re, L, h, "kOmegaSST")
    print(f"   {quality['summary']}")
    print(f"   质量评分: {quality['quality_score']:.0f}/100")
    
    print("\n" + "=" * 70)
    print("测试完成")
