# OpenFOAM AI 交互式 GUI 使用指南

## 🚀 快速启动

### 方法一：双击启动（推荐）
```
双击 start_gui.bat
```

### 方法二：命令行启动
```bash
cd E:\openfoam_ai
.venv\Scripts\python.exe launch_gui.py
```

浏览器将自动打开界面：`http://127.0.0.1:7860`

---

## 🎯 界面功能

### 1. 创建算例
- 在 **Case Description** 输入框中描述您的仿真需求
- 点击 **Create Case** 按钮
- AI 将自动生成 OpenFOAM 算例配置

**示例输入：**
```
Cylinder flow with Re=100 for Karman vortex street study
```

### 2. 修改算例
- 在 **Modification Request** 中输入修改要求
- 点击 **Modify Case** 按钮
- 系统将使用 AI 更新配置

**示例修改：**
```
Increase mesh resolution to 100x50 and change end time to 10s
```

### 3. 运行仿真

#### 生成网格
- 点击 **Generate Mesh** 按钮
- 系统自动运行 `blockMesh`

#### 运行求解器
- 设置 **Max Time**（最大运行时间，秒）
- 点击 **Run Simulation** 按钮
- 系统自动运行求解器（icoFoam/pimpleFoam 等）

### 4. 查看结果

#### 选择字段
- **Field** 下拉菜单：选择 U（速度）或 p（压力）

#### 视图控制
- **Zoom** 滑块：放大/缩小视图（0.5x - 5x）
- **Pan X/Y** 滑块：平移视图
- 点击 **Update View** 应用更改

#### 结果图说明
结果图包含 4 个面板：
1. **Field Contour** - 场量云图（速度/压力）
2. **Streamlines** - 流线图
3. **Vorticity** - 涡量图（用于识别涡旋）
4. **Convergence Monitor** - 收敛监控曲线

### 5. 审查算例
- 点击 **Review Case** 按钮
- 系统使用 Critic Agent 检查配置合理性
- 显示评分和建议

### 6. 截图功能
- 右键点击结果图像
- 选择 "图片另存为" 保存截图
- 或使用浏览器的截图工具

---

## 📁 文件位置

生成的算例保存在：
```
gui_cases/
└── [case_name]/
    ├── 0/                    # 初始条件
    ├── constant/             # 物理常数
    ├── system/               # 系统设置
    ├── logs/                 # 运行日志
    ├── preview.png           # 概念预览图
    └── result_U_*.png        # 仿真结果图
```

---

## 💡 使用示例：卡门涡街仿真

### 步骤 1：创建算例
```
输入：Create a 2D cylinder flow with Re=100 to study Karman vortex street
点击：Create Case
```

### 步骤 2：生成网格
```
点击：Generate Mesh
```

### 步骤 3：运行仿真
```
设置：Max Time = 10
点击：Run Simulation
```

### 步骤 4：查看结果
```
选择：Field = U
调整：Zoom = 2.0（放大查看涡旋）
点击：Update View
```

### 步骤 5：截图保存
```
右键点击结果图 → 图片另存为
```

---

## ⚠️ 注意事项

1. **OpenFOAM 安装**：要运行实际仿真，需要安装 OpenFOAM
   - 如果没有安装，系统会生成模拟数据用于演示

2. **运行时间**：
   - 简单算例（ cavity ）：几秒到几十秒
   - 复杂算例（ cylinder ）：几分钟到几十分钟
   - 建议使用较小的 Max Time 进行测试

3. **浏览器兼容性**：
   - 推荐使用 Chrome 或 Edge
   - 确保浏览器允许弹窗（用于自动打开界面）

---

## 🔧 故障排除

### GUI 无法启动
```bash
# 检查依赖
.venv\Scripts\python.exe -c "import gradio; print(gradio.__version__)"

# 重新安装 Gradio
.venv\Scripts\python.exe -m pip install gradio>=4.0.0
```

### 仿真运行失败
- 检查 OpenFOAM 是否安装：`blockMesh -help`
- 检查算例文件是否完整
- 查看日志：`gui_cases/[case_name]/logs/`

### 结果图不更新
- 确保仿真已完成（非运行中）
- 点击 **Update View** 刷新
- 检查 Case Configuration 是否显示正确

---

## 📞 支持

如有问题，请检查：
1. 虚拟环境是否激活
2. KIMI API Key 是否有效
3. OpenFOAM 是否正确安装
