#!/bin/bash
# Setup script for Resume Tailor application

echo "🚀 Resume Tailor Setup"
echo "====================="
echo ""

# Check if .env exists
if [ -f .env ]; then
    echo "✓ .env file already exists"
else
    echo "Creating .env file..."
    cp .env.example .env
    echo "⚠️  Please edit .env and add your Anthropic API key"
    echo "   Get your key from: https://console.anthropic.com/"
fi

echo ""

# Check if virtual environment exists
if [ -d venv ]; then
    echo "✓ Virtual environment exists"
else
    echo "Creating virtual environment..."
    /usr/bin/python3 -m venv venv
    echo "✓ Virtual environment created"
fi

echo ""

# Activate and install dependencies
echo "Installing dependencies..."
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q

echo ""
echo "✓ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env and add your API key (if you haven't already)"
echo "2. Run: source venv/bin/activate"
echo "3. Run: python -m src.main check"
echo "4. Edit data/resume_source.yaml with your resume"
echo "5. Install LaTeX: brew install --cask mactex"
