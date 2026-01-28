# Build Instructions for Easy PDF Translator

This guide explains how to build the `.exe` file for distribution.

## Prerequisites

1. **Python 3.9+** installed on your development machine
2. **pip** (Python package manager)

## Step-by-Step Build Process

### 1. Set Up Virtual Environment (Recommended)

```bash
# Navigate to project directory
cd /path/to/PDF_Translator_App

# Create virtual environment
python -m venv venv
# OR (if not working)
python3 -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate