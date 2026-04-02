# Attempt 4: Bayesian Shrinkage — blend context_mean towards global_mean
# pred = (1 - alpha) * context_mean + alpha * global_mean
# Find optimal alpha via 80/20 cross-validation on valid_test_scenarios_6

import numpy as np
import pandas as pd
import sys
import os

# Load the data
sys.path.append('/Users/yattmeo/Desktop/SMU/Code/404_found_us/ml_pipeline/Matt_EDA/Supervised learning')

# Import the required variables from loaded kernel
# These should be available from the notebook kernel context
# For now, we'll execute this directly in the notebook

print("This script should be run directly in the notebook kernel")
print("Use edit_notebook_file and run_notebook_cell tools instead")
