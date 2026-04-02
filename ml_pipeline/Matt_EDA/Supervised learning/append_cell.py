import json
import sys

notebook_path = sys.argv[1]
code = sys.argv[2]

# Load notebook
with open(notebook_path, 'r') as f:
    nb = json.load(f)

# Create new code cell
new_cell = {
    "cell_type": "code",
    "execution_count": None,
    "metadata": {},
    "outputs": [],
    "source": [line + '\n' for line in code.split('\n')]
}

# Append cell
nb['cells'].append(new_cell)

# Save notebook
with open(notebook_path, 'w') as f:
    json.dump(nb, f, indent=1)

# Print the cell index
print(f"Cell appended at index {len(nb['cells']) - 1}")
