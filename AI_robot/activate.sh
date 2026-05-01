#!/bin/bash
# Activation script for the trading system virtual environment

# Activate virtual environment
source venv/bin/activate

echo "✓ Virtual environment activated"
echo "Python version: $(python --version)"
echo "Pip version: $(pip --version)"
echo ""
echo "To deactivate, run: deactivate"
