"""Tables + figure for the scarce-data experiment. Usage: analyze.py RUNS_DIR OUT_PNG"""
import json, sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

runs, out = Path(sys.argv[1]), sys.argv[2]
ARMS = [  # fixed categorical order (validated palette slots 1-4)
    ('A_bp_wd0.1', 'Backprop', '#2a78d6'),
    ('A_bp_wd1.0', 'Backprop, heavy wd', '#eb6834'),
    ('A_bpnoise_wd0.1', 'Backprop + noise', '#1baf7a'),
    ('A_dust_wd0.1', 'Dust', '#eda100'),
]
data = {}
for key, label, color in ARMS:
    path = runs / key / 'metrics.jsonl'
    if path.exists() and len(path.read_text().splitlines()) > 1:
        rows = [json.loads(l) for l in path.read_text().splitlines()][1:]  # drop the step-0 init row
        data[key] = rows

print(f"{'arm':22} {'epochs':>6} {'best val':>9} {'@epoch':>6} {'final train':>11} {'final val':>9} {'gap':>6} {'test(final)':>11}")
for key, label, _ in ARMS:
    if key not in data:
        continue
    rows = data[key]
    best = min(rows, key=lambda r: r['val_bpb'])
    f = rows[-1]
    res = runs / key / 'result.json'
    test = json.loads(res.read_text())['test_bpb_final'] if res.exists() else float('nan')
    print(f"{label:22} {f['epoch']:6.1f} {best['val_bpb']:9.3f} {best['epoch']:6.1f} {f['train_bpb']:11.3f} "
          f"{f['val_bpb']:9.3f} {f['val_bpb'] - f['train_bpb']:6.3f} {test:11.3f}")

print('\nGeneralization gap (val - train, bpb) at matched training fit:')
levels = [3.0, 2.6, 2.3, 2.1, 2.0, 1.9, 1.8, 1.7]
print(f"{'train bpb':22}" + ''.join(f'{l:>7}' for l in levels))
for key, label, _ in ARMS:
    if key not in data:
        continue
    tr = np.array([r['train_bpb'] for r in data[key]]); va = np.array([r['val_bpb'] for r in data[key]])
    cells = []
    for l in levels:  # first crossing of this training-loss level, linear interpolation
        idx = np.where(tr <= l)[0]
        if len(idx) == 0 or idx[0] == 0:
            cells.append('     -'); continue
        i = idx[0]; w = (tr[i - 1] - l) / (tr[i - 1] - tr[i])
        cells.append(f'{(va[i - 1] + w * (va[i] - va[i - 1])) - l:7.3f}')
    print(f'{label:22}' + ''.join(cells))
if 'A_dust_wd0.1' in data:
    cos = [(r['epoch'], r['grad_cos']) for r in data['A_dust_wd0.1'] if 'grad_cos' in r]
    print('\nDust estimate vs exact gradient, cosine by epoch:', ', '.join(f'{e:g}:{c:.2f}' for e, c in cos[::4]))

ink, muted, grid = '#1f1f1e', '#6b6a64', '#e6e5e0'
plt.rcParams.update({'font.size': 10, 'axes.edgecolor': grid, 'axes.labelcolor': muted, 'xtick.color': muted,
                     'ytick.color': muted, 'axes.spines.top': False, 'axes.spines.right': False})
fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.4), facecolor='#fcfcfb')
for ax in (a1, a2):
    ax.set_facecolor('#fcfcfb'); ax.grid(color=grid, linewidth=0.8); ax.set_axisbelow(True)
lo = 1.4
for key, label, color in ARMS:
    if key not in data:
        continue
    rows = data[key]
    ep = [r['epoch'] for r in rows]; tr = [r['train_bpb'] for r in rows]; va = [r['val_bpb'] for r in rows]
    a1.plot(ep, va, color=color, lw=2, label=label)
    a1.annotate(label, (ep[-1], va[-1]), xytext=(4, 0), textcoords='offset points', color=ink, fontsize=8.5, va='center')
    a2.plot(tr, va, color=color, lw=2, label=label)
a1.set(xlabel='epoch (125k training bytes, repeated)', ylabel='validation bits per byte', ylim=(lo, 3.6))
a1.set_title('Validation loss by epoch', loc='left', color=ink, fontsize=11)
a2.plot([0.8, 3.6], [0.8, 3.6], color=muted, lw=1, ls=(0, (3, 3)))
a2.annotate('val = train (no gap)', (1.75, 1.3), color=muted, fontsize=8.5, ha='center', va='top')
if 'A_dust_wd0.1' in data:
    end = data['A_dust_wd0.1'][-1]
    a2.plot([end['train_bpb']], [end['val_bpb']], 'o', ms=8, color='#eda100', mec='#fcfcfb', mew=2, zorder=5)
    a2.annotate('Dust stops here', (end['train_bpb'], end['val_bpb']), xytext=(8, 8), textcoords='offset points',
                color=ink, fontsize=8.5)
a2.set(xlabel='training bits per byte (lower = fits training data better)', ylabel='validation bits per byte',
       xlim=(3.6, 0.8), ylim=(0.8, 3.6))
a2.set_title('Validation loss at matched training fit', loc='left', color=ink, fontsize=11)
a2.legend(frameon=False, loc='upper right', fontsize=9, labelcolor=ink)
fig.text(0.01, 0.005, '0.92M-param byte-level transformer (qlabs-eng/dust model + estimator), TinyStories, AdamW, '
         'seed 0, one run per arm. Right panel: a lower curve at the same x generalizes better at equal fit.',
         color=muted, fontsize=8)
fig.tight_layout(rect=(0, 0.03, 1, 1))
fig.savefig(out, dpi=150, facecolor=fig.get_facecolor())
print('wrote', out)
