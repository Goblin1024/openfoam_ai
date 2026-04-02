# OpenFOAM AI Agent

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![OpenFOAM](https://img.shields.io/badge/OpenFOAM-v11-orange.svg)](https://www.openfoam.com/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

**Making CFD Simulations as Simple as Speaking** 🚀

OpenFOAM AI Agent is an automated CFD (Computational Fluid Dynamics) simulation agent system based on Large Language Models. Through natural language descriptions, AI automatically completes the entire process from geometric modeling to result visualization.

## 🎯 Core Features

- 🗣️ **Natural Language Interaction**: Describe simulation requirements in Chinese or English, AI automatically understands and executes
- 🤖 **Multi-Agent Architecture**: Manager, Critic, and Specialist Agents work collaboratively
- 🛡️ **Anti-Hallucination Mechanism**: Multi-layer validation ensures physical reasonableness and research-grade quality
- 🧠 **Memory-Based Modeling**: Supports intelligent interaction modes like "modify based on previous results"
- 🖼️ **Multimodal Input**: Supports natural language and geometric image parsing
- 🔧 **Self-Healing Capability**: Automatically detects and fixes simulation divergence issues
- 📊 **Automatic Post-Processing**: Generates contour plots, streamlines, vector plots and other visualizations

## 🚀 Quick Start

### Requirements

- **Python**: 3.10 or higher
- **OpenFOAM**: Foundation v11 or ESI v2312 (optional, for real computation)
- **Operating System**: Windows / Linux / macOS

### Installation

#### Method 1: Local Installation

```bash
# Clone repository
git clone https://github.com/Goblin1024/openfoam_ai.git
cd openfoam_ai

# Install dependencies
pip install -r openfoam_ai/requirements.txt

# Configure environment variables (optional, for real LLM)
cp .env.example .env
# Edit .env to add your API key
```

#### Method 2: Docker Deployment (Recommended)

```bash
# Use Docker Compose
docker-compose -f openfoam_ai/docker/docker-compose.yml up -d

# View logs
docker-compose -f openfoam_ai/docker/docker-compose.yml logs -f
```

### Running

#### Interactive Mode

```bash
python openfoam_ai/main.py
```

#### Command Line Quick Case Creation

```bash
python openfoam_ai/main.py --case "Create a 2D lid-driven cavity flow, top velocity 1m/s, Reynolds number 100"
```

#### Web Interface

```bash
python interactive_gui.py
```

Then visit http://localhost:7860 in your browser

## 📖 Usage Examples

### Example 1: Lid-Driven Cavity Flow

```
👤 > Create a 2D lid-driven cavity flow, top velocity 1m/s, Reynolds number 100

🤖 I understand your request, preparing to create case: cavity_re100

Physics Type: incompressible
Solver: icoFoam
Geometry: 1.0 x 1.0 x 0.1
Mesh: 50 x 50 x 1 (approximately 2500 cells)
Time: 0 to 2.0 seconds

Execution Plan:
  1. Create case directory
  2. Generate blockMeshDict
  3. Generate controlDict
  4. Generate initial fields
  5. Run blockMesh
  6. Run checkMesh

Confirm execution? (y/n): y

Result: ✓ Success
Info: Case cavity_re100 created successfully, mesh generated
```

### Example 2: Incremental Modification

```
👤 > Refine the mesh to 80x80 based on the previous result

🤖 Received incremental modification request...

Change Detection:
  - geometry.mesh_resolution.nx: 50 → 80
  - geometry.mesh_resolution.ny: 50 → 80

Confirm modification? (y/n): y

Result: ✓ Success
Info: Case updated, mesh regenerated
```

### Example 3: Post-Processing Visualization

```
👤 > Generate velocity contour and streamline plots

🤖 Preparing post-processing...

Generated files:
  - result_U_0.png (velocity contour)
  - streamlines.png (streamlines)

Result: ✓ Success
```

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────┐
│              User Interface Layer (CLI / Web UI)         │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│              Manager Agent (Task Scheduling)            │
│  Intent Recognition → Plan Generation → Execution Coord │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────┬──────────────────┬───────────────────────┐
│ Preprocessing│    Execution     │   Postprocessing      │
│   Agent     │      Agent       │        Agent          │
│ · Mesh Gen  │  · Solver Exec   │    · Data Extract     │
│ · Dict Gen  │  · Residual Mon  │    · Visualization    │
│ · Boundary  │  · Self-Healing  │    · Report Gen       │
└─────────────┴──────────────────┴───────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                OpenFOAM Computation Engine               │
│        blockMesh / icoFoam / checkMesh / paraView       │
└─────────────────────────────────────────────────────────┘
```

## 📁 Project Structure

```
openfoam_ai/
├── openfoam_ai/              # Core package
│   ├── agents/               # Agent modules
│   │   ├── manager_agent.py       # Master Agent
│   │   ├── critic_agent.py        # Critic Agent
│   │   ├── mesh_quality_agent.py  # Mesh Quality Agent
│   │   ├── self_healing_agent.py  # Self-Healing Agent
│   │   ├── physics_validation_agent.py  # Physics Validation Agent
│   │   ├── postprocessing_agent.py    # Post-Processing Agent
│   │   └── prompt_engine.py          # LLM Interface
│   ├── core/                 # Core functions
│   │   ├── case_manager.py        # Case management
│   │   ├── openfoam_runner.py     # Command execution
│   │   ├── validators.py          # Physics validation
│   │   └── file_generator.py      # Dictionary generation
│   ├── memory/               # Memory management
│   │   ├── memory_manager.py      # Vector database
│   │   └── session_manager.py     # Session management
│   ├── ui/                   # User interface
│   │   ├── cli_interface.py       # Command line interface
│   │   └── gradio_interface.py    # Web interface
│   ├── utils/                # Utility functions
│   ├── config/               # Configuration files
│   ├── docker/               # Docker configuration
│   ├── tests/                # Unit tests
│   ├── main.py               # Main entry point
│   └── requirements.txt      # Dependencies
├── demo_cases/               # Example cases
├── gui_cases/                # Web interface cases
├── interactive_gui.py        # Web interface launcher
├── README.md                 # Project documentation
├── README_EN.md              # English documentation
├── LICENSE                   # License
└── .gitignore                # Git ignore configuration
```

## 🔒 Anti-Hallucination Mechanism

This project employs multiple mechanisms to prevent AI from generating unreasonable configurations:

1. **Pydantic Hard Constraints**: All configurations must pass type and range validation
2. **Project Constitution**: Must comply with rules in `config/system_constitution.yaml`
3. **Critic Agent**: Multi-agent review mechanism (scoring system)
4. **Physics Validation**: Mass and energy conservation validation
5. **Mesh Quality Constraints**: Automatic checking of non-orthogonality, skewness, aspect ratio
6. **Courant Number Limit**: Automatic estimation and limitation of Courant number (CFL condition)

## 🧪 Testing

```bash
# Run all tests
pytest openfoam_ai/tests/

# Run specific tests
pytest openfoam_ai/tests/test_phase1.py -v

# Generate coverage report
pytest --cov=openfoam_ai openfoam_ai/tests/
```

### Test Coverage

| Phase | Tests | Passed | Pass Rate |
|-------|-------|--------|-----------|
| Phase 1 | 17 | 17 | 100% |
| Phase 2 | 17 | 17 | 100% |
| Phase 3 | 24 | 24 | 100% |
| Phase 4 | 11 | 11 | 100% |
| **Total** | **52** | **52** | **100%** |

## 📚 API Reference

### Core Modules

#### CaseManager

```python
from openfoam_ai.core import CaseManager

case_manager = CaseManager("./cases")

# Create case
case_path = case_manager.create_case("cavity_flow", physics_type="incompressible")

# List all cases
cases = case_manager.list_cases()

# Clean up case
case_manager.cleanup("cavity_flow", keep_results=True)
```

#### OpenFOAMRunner

```python
from openfoam_ai.core import OpenFOAMRunner

runner = OpenFOAMRunner(case_path)

# Run mesh generation
success, message = runner.run_blockmesh()

# Run solver
for metrics in runner.run_solver("icoFoam"):
    print(f"Time: {metrics.time}, Courant: {metrics.courant_max}")
```

#### PromptEngine

```python
from openfoam_ai.agents import PromptEngine

# Mock mode (no API key required)
engine = PromptEngine(api_key=None)

# Real LLM mode
engine = PromptEngine(api_key="your-api-key", base_url="...")

# Parse natural language
config = engine.natural_language_to_config("Create lid-driven cavity flow")
```

## 🛣️ Roadmap

- [x] **Phase 1**: Infrastructure & MVP
  - [x] Project architecture
  - [x] CaseManager implementation
  - [x] Dictionary file generator
  - [x] OpenFOAM command wrapper
  
- [x] **Phase 2**: AI Self-Check & Self-Healing
  - [x] Automatic mesh quality repair
  - [x] Solver stability monitoring
  - [x] Divergence self-healing
  - [x] Critic Agent reviewer
  
- [x] **Phase 3**: Memory-Based Modeling & Interaction
  - [x] Vector database
  - [x] Case history management
  - [x] Incremental modification
  - [x] Web interface
  
- [x] **Phase 4**: Multimodal & Post-Processing
  - [x] Geometric image parsing
  - [x] Automatic plotting
  - [x] Result interpretation
  
- [ ] **Phase 5**: Advanced Features (Planned)
  - [ ] Multiphase flow support
  - [ ] Heat transfer coupling
  - [ ] Turbulence models
  - [ ] Design optimization

## 🤝 Contributing

We welcome code contributions, bug reports, and feature suggestions!

### Contribution Workflow

1. Fork this repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Create Pull Request

### Development Environment Setup

```bash
# Clone repository
git clone https://github.com/Goblin1024/openfoam_ai.git
cd openfoam_ai

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install development dependencies
pip install -r openfoam_ai/requirements.txt
pip install -e .

# Run tests
pytest openfoam_ai/tests/
```

### Code Style Guidelines

- Follow [PEP 8](https://pep8.org/) code style
- Use [Black](https://github.com/psf/black) for code formatting
- Add appropriate type annotations
- Write unit tests for new features

## 🔧 Troubleshooting

### Common Errors

1. **SyntaxError: source code string cannot contain null bytes**
   - **Cause**: Python file contains null bytes or UTF-16 BOM
   - **Solution**: Run `python clean.py` or manually convert file encoding to UTF-8

2. **ModuleNotFoundError: No module named 'openai'**
   - **Cause**: openai package not installed
   - **Solution**: Install openai (`pip install openai`) or use Mock mode (set `api_key=None`)

3. **FileNotFoundError: [Errno 2] No such file or directory: 'blockMesh'**
   - **Cause**: OpenFOAM environment not properly loaded
   - **Solution**: Ensure OpenFOAM is installed and `blockMesh` can run directly in terminal, or use Docker container

4. **PydanticValidationError**
   - **Cause**: Configuration doesn't meet validation rules
   - **Solution**: Check configuration parameters against constitution rules (see `config/system_constitution.yaml`)

5. **UnicodeEncodeError: 'gbk' codec can't encode character**
   - **Cause**: Windows console default encoding is GBK
   - **Solution**: Set environment variable `PYTHONIOENCODING=utf-8`

### Debugging Tips

- Enable verbose logging: Set environment variable `LOG_LEVEL=DEBUG`
- Test configuration generation with Mock mode: `PromptEngine(api_key=None)`
- Run unit tests: `pytest openfoam_ai/tests/`
- Check case directory structure: Ensure `0/`, `constant/`, `system/` directories exist

## 📄 License

This project is licensed under the [MIT License](LICENSE) - see LICENSE file for details

## 🙏 Acknowledgments

- [OpenFOAM](https://www.openfoam.com/) - Open source CFD tool
- [LangChain](https://python.langchain.com/) - LLM application framework
- [PyVista](https://docs.pyvista.org/) - Visualization library
- [Gradio](https://gradio.app/) - Web interface library

## 📧 Contact

For questions or suggestions, please contact:

- Submit [GitHub Issue](https://github.com/Goblin1024/openfoam_ai/issues)
- Email: your.email@example.com

## 📝 Citation

If you use this project in your research, please cite:

```bibtex
@software{openfoam_ai_agent2026,
  author = {Goblin1024},
  title = {OpenFOAM AI Agent: LLM-Driven Automated CFD Simulation},
  year = {2026},
  url = {https://github.com/Goblin1024/openfoam_ai}
}
```

---

**Disclaimer**: This tool is for academic research and engineering assistance. Simulation results must be verified by professionals before being used for actual engineering decisions.