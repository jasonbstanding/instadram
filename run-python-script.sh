#!/bin/bash


# Load environment variables from .env file
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Set the project directory (can be set in .env or hardcoded)
PROJECT_DIR="${PROJECT_DIR:-/home/jbscomssh/instadram}"

# Change to project directory
cd $PROJECT_DIR

# Create virtual environment if it doesn't exist
if [ ! -f "pyvenv.cfg" ]; then
    echo "Creating venv..."
    python3 -m venv .
fi

# Activate virtual environment
source bin/activate

# Upgrade pip
pip install --upgrade pip

# Install requirements (if you have a requirements.txt)
pip install -r requirements.txt

# Run the Python script
python ./main.py

# Deactivate virtual environment
deactivate
