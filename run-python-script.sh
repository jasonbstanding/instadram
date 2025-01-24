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
if [ ! -d "venv" ]; then
    echo "Creating venv..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install requirements (if you have a requirements.txt)
pip install -r requirements.txt

# Run the Python script
python app/instadram.py

# Deactivate virtual environment
deactivate
