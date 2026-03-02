#!/usr/bin/env bash
# Exit on error
set -o errexit

echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "Installing Playwright browsers..."
playwright install chromium

echo "Installing OS dependencies for Playwright..."
playwright install-deps
