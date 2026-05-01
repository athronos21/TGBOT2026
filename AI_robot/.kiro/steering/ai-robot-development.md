# AI Robot Development Guidelines

## Project Standards

### Code Style
- Follow PEP 8 Python style guide
- Use type hints for function signatures
- Write docstrings for all classes and functions
- Keep functions focused and modular

### Architecture
- Separate AI models from robot control logic
- Use configuration files for parameters
- Implement proper error handling and logging
- Design for modularity and reusability

### AI/ML Best Practices
- Version control your models
- Document model architecture and hyperparameters
- Use separate train/validation/test datasets
- Log training metrics and experiments
- Save model checkpoints regularly

### Robotics Best Practices
- Implement safety checks and emergency stops
- Test in simulation before hardware deployment
- Use proper sensor calibration
- Handle hardware failures gracefully
- Document hardware specifications

### Project Structure
```
AI_robot/
├── src/           # Source code
│   ├── ai/        # AI/ML models
│   ├── control/   # Robot control logic
│   ├── sensors/   # Sensor interfaces
│   └── utils/     # Utility functions
├── models/        # Trained models
├── data/          # Training/test data
├── docs/          # Documentation
├── tests/         # Unit tests
└── scripts/       # Utility scripts
```

### Testing
- Write unit tests for core functionality
- Test AI models with validation data
- Simulate robot behavior before hardware testing
- Use pytest for test framework

### Dependencies
- Use virtual environment (venv or conda)
- Keep requirements.txt updated
- Pin critical dependency versions

## Common Commands

```bash
# Setup environment
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run tests
pytest tests/

# Train model
python scripts/train_model.py

# Run robot
python src/main.py

# Format code
black src/
flake8 src/
```
