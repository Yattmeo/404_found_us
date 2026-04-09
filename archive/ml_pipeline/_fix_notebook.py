import json

path = r'c:\Users\justi\Documents\GitHub\404_found_us\ml_pipeline\train_tpv_v2_production.ipynb'
with open(path) as f:
    nb = json.load(f)

cell = nb['cells'][9]
src = cell['source']

# Fix 1: _adaptive_q — insert guard after 'n = len(residuals)'
for i, line in enumerate(src):
    if line == '    n = len(residuals)\n' and i > 0 and 'adaptive_q' in src[i-2]:
        if src[i+1] != '    if not residuals:\n':
            src.insert(i+1, '    if not residuals:\n')
            src.insert(i+2, '        return None\n')
            print('Fixed _adaptive_q')
        else:
            print('_adaptive_q already fixed')
        break

# Fix 2: _make_percentile_bins — insert empty guard after the def line
for i, line in enumerate(src):
    if line == 'def _make_percentile_bins(ref_vals, apply_vals, pct_edges, min_count=MIN_POOL):\n':
        if src[i+1] != '    if len(ref_vals) == 0 or len(apply_vals) == 0:\n':
            src.insert(i+1, '    if len(ref_vals) == 0 or len(apply_vals) == 0:\n')
            src.insert(i+2, '        return None\n')
            print('Fixed _make_percentile_bins')
        else:
            print('_make_percentile_bins already fixed')
        break

# Fix 3: Training loop cell (#VSC-219faeb4, index 13) — add skip-existing at top of MCC loop
train_cell = nb['cells'][13]
tsrc = train_cell['source']

# Find the line after 'for mcc in TRAIN_MCCS:' and the MCC print lines
skip_block = [
    '    # Skip MCCs that already have complete artifacts from a prior run\n',
    '    if all(\n',
    '        (ARTIFACTS_OUTPUT_PATH / str(mcc) / str(ctx_len) / "config_snapshot.json").exists()\n',
    '        for ctx_len in SUPPORTED_CONTEXT_LENS\n',
    '    ):\n',
    '        print(f"  SKIP MCC {mcc}: all artifacts already exist")\n',
    '        continue\n',
    '\n',
]

insert_after = "    print(f\"  Training MCC {mcc}\")\n"
for i, line in enumerate(tsrc):
    if line == insert_after:
        # Check if skip block already inserted
        if tsrc[i+1] != '    # Skip MCCs that already have complete artifacts from a prior run\n':
            for j, block_line in enumerate(skip_block):
                tsrc.insert(i+1+j, block_line)
            print('Added skip-existing block to training loop')
        else:
            print('Skip-existing already present')
        break

with open(path, 'w') as f:
    json.dump(nb, f, indent=1)
print('Saved notebook')
