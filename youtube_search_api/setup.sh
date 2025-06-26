#!/bin/bash

# YouTube Search API Setup Script

set -e

echo "🚀 Setting up YouTube Search API"
echo "================================"

# Check if Python 3.11+ is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.11 or higher."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "✅ Python version: $PYTHON_VERSION"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "⚠️  Docker is not installed. You'll need it for deployment."
else
    echo "✅ Docker is installed"
fi

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "⚠️  Google Cloud SDK is not installed. You'll need it for deployment."
else
    echo "✅ Google Cloud SDK is installed"
fi

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp env.example .env
    echo "✅ Created .env file. Please edit it with your credentials."
else
    echo "✅ .env file already exists"
fi

# Make scripts executable
chmod +x deploy.sh
chmod +x test_api.py

echo ""
echo "🎉 Setup completed successfully!"
echo ""
echo "📋 Next steps:"
echo "1. Edit .env file with your credentials:"
echo "   - GCP_PROJECT_ID"
echo "   - OXYLABS_USERNAME"
echo "   - OXYLABS_PASSWORD"
echo ""
echo "2. Create GCS bucket:"
echo "   gsutil mb gs://youtube-search-data-bucket"
echo ""
echo "3. Test locally:"
echo "   source venv/bin/activate"
echo "   python main.py"
echo ""
echo "4. Run tests:"
echo "   python test_api.py"
echo ""
echo "5. Deploy to Cloud Run:"
echo "   ./deploy.sh" 