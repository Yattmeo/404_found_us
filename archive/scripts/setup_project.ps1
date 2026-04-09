# PowerShell Script to initialize ML Web Application Project Structure
# This script checks if files exist before creating them

$ErrorActionPreference = "Stop"

Write-Host "Creating ML Web Application Project Structure..." -ForegroundColor Cyan
Write-Host ""

# Create directories
$directories = @(
    "ml_pipeline",
    "ml_pipeline\notebooks",
    "backend",
    "frontend",
    "frontend\src"
)

foreach ($dir in $directories) {
    if (Test-Path $dir) {
        Write-Host "  Directory exists: $dir" -ForegroundColor Yellow
    } else {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "  Created: $dir" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "Creating backend files..." -ForegroundColor Cyan

# Backend: requirements.txt
$reqPath = "backend\requirements.txt"
if (Test-Path $reqPath) {
    Write-Host "  File exists: $reqPath" -ForegroundColor Yellow
} else {
    @"
flask==3.0.0
scikit-learn==1.4.0
seaborn==0.13.1
wandb==0.16.2
pandas==2.1.4
numpy==1.26.3
"@ | Out-File -FilePath $reqPath -Encoding UTF8
    Write-Host "  Created: $reqPath" -ForegroundColor Green
}

# Backend: app.py
$appPath = "backend\app.py"
if (Test-Path $appPath) {
    Write-Host "  File exists: $appPath" -ForegroundColor Yellow
} else {
    @"
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def hello_world():
    return jsonify({
        'message': 'Hello World from ML Backend!',
        'status': 'success'
    })

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'service': 'ml-backend'
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
"@ | Out-File -FilePath $appPath -Encoding UTF8
    Write-Host "  Created: $appPath" -ForegroundColor Green
}

# Backend: Dockerfile
$backDockerPath = "backend\Dockerfile"
if (Test-Path $backDockerPath) {
    Write-Host "  File exists: $backDockerPath" -ForegroundColor Yellow
} else {
    @"
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "app.py"]
"@ | Out-File -FilePath $backDockerPath -Encoding UTF8
    Write-Host "  Created: $backDockerPath" -ForegroundColor Green
}

Write-Host ""
Write-Host "Creating frontend files..." -ForegroundColor Cyan

# Frontend: package.json
$pkgPath = "frontend\package.json"
if (Test-Path $pkgPath) {
    Write-Host "  File exists: $pkgPath" -ForegroundColor Yellow
} else {
    @"
{
  "name": "ml-frontend",
  "version": "0.1.0",
  "private": true,
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-scripts": "5.0.1",
    "axios": "^1.6.5"
  },
  "scripts": {
    "start": "react-scripts start",
    "build": "react-scripts build",
    "test": "react-scripts test",
    "eject": "react-scripts eject"
  },
  "eslintConfig": {
    "extends": ["react-app"]
  },
  "browserslist": {
    "production": [">0.2%", "not dead", "not op_mini all"],
    "development": ["last 1 chrome version", "last 1 firefox version", "last 1 safari version"]
  }
}
"@ | Out-File -FilePath $pkgPath -Encoding UTF8
    Write-Host "  Created: $pkgPath" -ForegroundColor Green
}

# Frontend: App.js
$appJsPath = "frontend\src\App.js"
if (Test-Path $appJsPath) {
    Write-Host "  File exists: $appJsPath" -ForegroundColor Yellow
} else {
    @"
import React, { useState, useEffect } from 'react';
import './App.css';

function App() {
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('http://localhost:5000/')
      .then(response => response.json())
      .then(data => {
        setMessage(data.message);
        setLoading(false);
      })
      .catch(error => {
        console.error('Error:', error);
        setMessage('Error connecting to backend');
        setLoading(false);
      });
  }, []);

  return (
    <div className="App">
      <header className="App-header">
        <h1>ML Web Application</h1>
        {loading ? <p>Loading...</p> : <p>{message}</p>}
      </header>
    </div>
  );
}

export default App;
"@ | Out-File -FilePath $appJsPath -Encoding UTF8
    Write-Host "  Created: $appJsPath" -ForegroundColor Green
}

# Frontend: App.css
$appCssPath = "frontend\src\App.css"
if (Test-Path $appCssPath) {
    Write-Host "  File exists: $appCssPath" -ForegroundColor Yellow
} else {
    @"
.App {
  text-align: center;
}

.App-header {
  background-color: #282c34;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  font-size: calc(10px + 2vmin);
  color: white;
}

h1 {
  color: #61dafb;
}

p {
  margin: 20px;
}
"@ | Out-File -FilePath $appCssPath -Encoding UTF8
    Write-Host "  Created: $appCssPath" -ForegroundColor Green
}

# Frontend: Dockerfile
$frontDockerPath = "frontend\Dockerfile"
if (Test-Path $frontDockerPath) {
    Write-Host "  File exists: $frontDockerPath" -ForegroundColor Yellow
} else {
    @"
FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

EXPOSE 3000

CMD ["npm", "start"]
"@ | Out-File -FilePath $frontDockerPath -Encoding UTF8
    Write-Host "  Created: $frontDockerPath" -ForegroundColor Green
}

Write-Host ""
Write-Host "Creating ML pipeline files..." -ForegroundColor Cyan

# ML Pipeline: README.md
$mlReadmePath = "ml_pipeline\README.md"
if (Test-Path $mlReadmePath) {
    Write-Host "  File exists: $mlReadmePath" -ForegroundColor Yellow
} else {
    @"
# ML Pipeline

This folder contains all machine learning related code.

## Structure

- **notebooks/**: Jupyter notebooks for EDA and experimentation
- **training scripts**: Python scripts for model training
- **models/**: Saved model artifacts

## Getting Started

````powershell
# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install jupyter scikit-learn pandas numpy seaborn wandb matplotlib

# Launch Jupyter
jupyter notebook
````
"@ | Out-File -FilePath $mlReadmePath -Encoding UTF8
    Write-Host "  Created: $mlReadmePath" -ForegroundColor Green
}

Write-Host ""
Write-Host "Creating root configuration files..." -ForegroundColor Cyan

# docker-compose.yml
$composePath = "docker-compose.yml"
if (Test-Path $composePath) {
    Write-Host "  File exists: $composePath" -ForegroundColor Yellow
} else {
    @"
version: '3.8'

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: ml-backend
    ports:
      - "5000:5000"
    environment:
      - FLASK_ENV=development
      - FLASK_APP=app.py
    volumes:
      - ./backend:/app
    restart: unless-stopped
    networks:
      - ml-network

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: ml-frontend
    ports:
      - "3000:3000"
    environment:
      - REACT_APP_BACKEND_URL=http://localhost:5000
    volumes:
      - ./frontend:/app
      - /app/node_modules
    depends_on:
      - backend
    restart: unless-stopped
    networks:
      - ml-network

networks:
  ml-network:
    driver: bridge
"@ | Out-File -FilePath $composePath -Encoding UTF8
    Write-Host "  Created: $composePath" -ForegroundColor Green
}

# .gitignore
$gitignorePath = ".gitignore"
if (Test-Path $gitignorePath) {
    Write-Host "  File exists: $gitignorePath" -ForegroundColor Yellow
} else {
    @"
# Python
__pycache__/
*.py[cod]
*.so
.Python
build/
dist/
*.egg-info/
venv/
env/
.venv

# Node
node_modules/
npm-debug.log*
package-lock.json

# Data Science
*.csv
*.h5
*.pkl
*.joblib
*.model
*.weights
wandb/
.ipynb_checkpoints/

# OS
.DS_Store
Thumbs.db

# Environment
.env
.env.local

# IDE
.vscode/
.idea/
*.swp

# Logs
*.log

# Build outputs
/frontend/build
"@ | Out-File -FilePath $gitignorePath -Encoding UTF8
    Write-Host "  Created: $gitignorePath" -ForegroundColor Green
}

Write-Host ""
Write-Host "Project initialization complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. docker-compose up --build"
Write-Host "  2. Frontend: http://localhost:3000"
Write-Host "  3. Backend: http://localhost:5000"
Write-Host ""
