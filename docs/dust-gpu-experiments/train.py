"""Scarce-data generalization: DUST (forward-only) vs. backprop on a tiny byte-level transformer.

Uses qlabs-eng/dust's own model.py and DUST estimator unchanged (point --dust-src at a clone), at a CPU-sized config.
Every arm: same model, init (seed), data, batch order, epochs. Only the gradient source / optimizer differs.

  bp        exact gradient (backprop)
  bp_noise  backprop, but the training forward jitters the MLP/attention projections (sigma) -> "is it just noise?"
  dust      DUST estimator
--opt adamw (default) or sgd (the Dust repo's tuned SGD parameter groups for each gradient source).
"""
import argparse, json, math, sys, time
from pathlib import Path

import torch

_src = sys.argv[sys.argv.index('--dust-src') + 1] if '--dust-src' in sys.argv else 'dust'
sys.path.insert(0, str(Path(_src).resolve()))
from dust import DUST, Recipe, make_model, make_optimizer as dust_optimizer  # noqa: E402
from model import GPTConfig  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument('--method', required=True, choices=['bp', 'bp_noise', 'dust'])
p.add_argument('--opt', default='adamw', choices=['sgd', 'adamw'])
p.add_argument('--data', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--epochs', type=int, default=20)
p.add_argument('--batch', type=int, default=8)
p.add_argument('--lr', type=float)
p.add_argument('--wd', type=float, default=0.0)
p.add_argument('--sigma', type=float, default=0.2)
p.add_argument('--seed', type=int, default=0)
p.add_argument('--evals_per_epoch', type=int, default=2)
p.add_argument('--threads', type=int, default=4)
p.add_argument('--max_minutes', type=float, default=1e9)
p.add_argument('--dust-src', default='dust', help='path to a clone of github.com/qlabs-eng/dust')
p.add_argument('--device', default='cuda' if torch.cuda.is_available() else 'cpu')
args = p.parse_args()
torch.set_num_threads(args.threads)

LOG2E = 1 / math.log(2)
config = GPTConfig(sequence_len=256, vocab_size=256, n_layer=4, n_head=4, n_kv_head=4, n_embd=128)
device = torch.device(args.device)
train, val, test = (torch.load(args.data / f'{s}.pt').long().to(device) for s in ('train', 'val', 'test'))
train_probe = train[torch.randperm(len(train), generator=torch.Generator().manual_seed(123))[:len(val)].to(device)]

model = make_model(config, device, args.seed)
n_params = sum(q.numel() for q in model.parameters())

# Draw counts per block: about half the repo's 256-population recipe, first 4 blocks, rounded to the chunk size.
# Head: the byte vocab is one 256-column slab, so 64 draws matches the repo's per-slab rate (1024 / 16 slabs).
recipe = Recipe(writers=[20, 16, 8, 8], hidden=[20, 16, 8, 8], hubs=[4, 4, 4, 4], embedding=8,
                head=64, local=dict(q=4, v=12, gate=4, k=8, ve=4), nrep=4,
                lr=args.lr or 0.25, momentum=0.95)

if args.method == 'dust':
    estimator = DUST(model, recipe, seed=args.seed)
else:
    model.requires_grad_(True)
if args.opt == 'adamw':
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr or 3e-3, weight_decay=args.wd, betas=(0.9, 0.95))
elif args.method == 'dust':  # the Dust repo's SGD parameter groups
    optimizer = dust_optimizer(model, recipe)
else:  # the Dust repo's backprop baseline groups (baselines/backprop.py), 1M-token setting
    optimizer = torch.optim.SGD([
        {'params': [q for n, q in model.named_parameters() if n != 'transformer.wte.weight'], 'lr': args.lr or 0.175},
        {'params': [model.transformer.wte.weight], 'lr': 1000.0}], momentum=0.98)
if args.method == 'bp_noise':
    gen = torch.Generator(device).manual_seed(args.seed + 99)
    def jitter(module, inputs, output):
        if module.training:
            return output + args.sigma * torch.randn(output.shape, generator=gen, device=output.device, dtype=output.dtype)
    for n, m in model.named_modules():
        if n.endswith(('c_proj', 'c_fc')):
            m.register_forward_hook(jitter)


@torch.no_grad()
def bpb(rows):
    model.eval()
    total = sum(model(r[:, :-1].contiguous(), r[:, 1:].contiguous()).item() * r[:, 1:].numel() for r in rows.split(64))
    model.train()
    return total / rows[:, 1:].numel() * LOG2E


def true_grad_cosine(x, y, estimate):
    """Diagnostic only (dust arm): cosine of the DUST estimate with the exact gradient on the same batch."""
    with torch.enable_grad():
        model.requires_grad_(True)
        model.zero_grad(set_to_none=True)
        model(x, y).backward()
        exact = torch.cat([q.grad.flatten() for q in model.parameters()])
        model.zero_grad(set_to_none=True)
        model.requires_grad_(False)
    return torch.nn.functional.cosine_similarity(exact, estimate, dim=0).item()


args.out.mkdir(parents=True, exist_ok=False)
meta = dict(vars(args), data=str(args.data), out=str(args.out), params=n_params, config=config.__dict__,
            train_bytes=train.numel(), torch=torch.__version__)
(args.out / 'config.json').write_text(json.dumps(meta, indent=1, default=str))
log = (args.out / 'metrics.jsonl').open('a')
steps_per_epoch = len(train) // args.batch
eval_every = max(1, steps_per_epoch // args.evals_per_epoch)
print(f'{args.method}: {n_params/1e6:.2f}M params, {train.numel()/1e3:.0f}k train bytes, '
      f'{steps_per_epoch} steps/epoch', flush=True)

start, step, cos = time.monotonic(), 0, None
record = dict(step=0, epoch=0, train_bpb=bpb(train_probe), val_bpb=bpb(val), seconds=0)
log.write(json.dumps(record) + '\n'); log.flush(); print(record, flush=True)
for epoch in range(args.epochs):
    order = torch.randperm(len(train), generator=torch.Generator().manual_seed(args.seed * 1000 + epoch))
    for i in range(steps_per_epoch):
        batch = train[order[i * args.batch:(i + 1) * args.batch].to(device)]
        x, y = batch[:, :-1].contiguous(), batch[:, 1:].contiguous()
        if args.method == 'dust':
            estimator.step(x, y, optimizer)
            if (step + 1) % eval_every == 0:  # the step just applied used these grads
                cos = true_grad_cosine(x, y, torch.cat([q.grad.flatten() for q in model.parameters()]))
        else:
            optimizer.zero_grad(set_to_none=True)
            model(x, y).backward()
            optimizer.step()
        step += 1
        if step % eval_every == 0:
            record = dict(step=step, epoch=round(step / steps_per_epoch, 3), train_bpb=bpb(train_probe),
                          val_bpb=bpb(val), seconds=round(time.monotonic() - start, 1))
            if cos is not None:
                record['grad_cos'] = round(cos, 4)
            if not math.isfinite(record['val_bpb']):
                raise FloatingPointError('diverged')
            log.write(json.dumps(record) + '\n'); log.flush(); print(record, flush=True)
            if record['seconds'] > args.max_minutes * 60:
                break
    else:
        continue
    print('stopped on time budget', flush=True)
    break

rows = [json.loads(l) for l in (args.out / 'metrics.jsonl').read_text().splitlines()]
best = min(rows, key=lambda r: r['val_bpb'])
final = rows[-1]
# Test is read once per run, at the final weights (no checkpoint selection on test).
result = dict(best_val_bpb=best['val_bpb'], best_val_epoch=best['epoch'], final=final, test_bpb_final=bpb(test))
(args.out / 'result.json').write_text(json.dumps(result, indent=1))
print('RESULT', json.dumps(result), flush=True)
