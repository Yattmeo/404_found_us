# ML Pipeline

This folder contains all machine learning related code including:

## Structure

- **notebooks/**: Jupyter notebooks for Exploratory Data Analysis (EDA) and experimentation
- **training scripts**: Python scripts for model training and evaluation
- **models/**: Saved model artifacts (add to .gitignore for large files)

## Usage

1. Perform EDA in the `notebooks/` directory
2. Create training scripts for reproducible model training
3. Use Weights & Biases (wandb) for experiment tracking
4. Export trained models for deployment in the backend

## Getting Started

```bash
# Create a virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install jupyter scikit-learn pandas numpy seaborn wandb matplotlib

# Launch Jupyter
jupyter notebook
```
