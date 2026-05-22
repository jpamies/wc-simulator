import gzip, json
from collections import Counter

with gzip.open('data/raw/players.json.gz', 'rt', encoding='utf-8') as f:
    data = json.load(f)

# Positions
all_pos = []
for p in data:
    for pos in p['player_positions'].split(', '):
        all_pos.append(pos.strip())
pos_counts = Counter(all_pos)
print('=== POSITIONS ===')
for pos, cnt in pos_counts.most_common(30):
    print(f'  {pos:6s} {cnt:5d}')

# Stats ranges
print('\n=== STATS RANGES ===')
for field in ['overall', 'potential', 'value_eur', 'pace', 'shooting', 'passing', 'dribbling', 'defending', 'physic']:
    vals = [p[field] for p in data if p[field] is not None]
    print(f'  {field:15s}  min={min(vals):>12}  max={max(vals):>12}  avg={sum(vals)/len(vals):>12.1f}')

# GKs
gks = [p for p in data if 'GK' in p['player_positions']]
print(f'\nGKs: {len(gks)}')
print(f'  Sample: {json.dumps(gks[0], ensure_ascii=False, indent=2)}')

# Check null fields
nulls = {}
for k in data[0].keys():
    null_count = sum(1 for p in data if p[k] is None)
    if null_count > 0:
        nulls[k] = null_count
print(f'\n=== NULL FIELDS ===')
for k, v in nulls.items():
    print(f'  {k}: {v} nulls ({v*100/len(data):.1f}%)')
