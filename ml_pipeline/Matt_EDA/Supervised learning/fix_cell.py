import json
with open('m8_pipeline_c1 copy.ipynb', 'r') as f:
    nb = json.load(f)
c = nb['cells'][49]
src = c['source']
new_src = []
skip = False
for line in src:
    if 'for ax_, title_, lo_list, hi_list in [' in line:
        skip = True
    if skip:
        if line.strip() == 'pass':
            skip = False
        continue
    new_src.append(line)
c['source'] = new_src
with open('m8_pipeline_c1 copy.ipynb', 'w') as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)
print(f"Done: {len(new_src)} lines remain")

