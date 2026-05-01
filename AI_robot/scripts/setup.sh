#!/bin/bash
# Setup AI Robot development environment

echo "Setting up AI Robot environment..."

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

echo ""
echo "✓ Setup complete!"
echo ""
echo "To activate the environment, run:"
echo "  source venv/bin/activate"
echo ""
echo "To run the robot:"
echo "  python src/main.py"
