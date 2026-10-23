"""Byte-level TinyStories splits for the scarce-data experiment: disjoint, deduplicated stories.

Writes train/val/test as [N, SEQ+1] uint8 tensors of bytes. Stories are deduplicated on normalized
text before splitting, so no story appears in two splits; the overlap check is printed.
"""
import hashlib, random, sys, torch

SEQ = 256
src, out = sys.argv[1], sys.argv[2]
TRAIN_BYTES, EVAL_SEQS = int(sys.argv[3]), 256

raw = open(src, encoding='utf-8').read().split('<|endoftext|>')
stories = [s.strip() for s in raw if len(s.strip()) > 100]
key = lambda s: hashlib.sha1(' '.join(s.lower().split()).encode()).hexdigest()
seen, unique = set(), []
for s in stories:
    if key(s) not in seen:
        seen.add(key(s)); unique.append(s)
print(f'{len(stories)} stories, {len(unique)} after dedup')
random.Random(0).shuffle(unique)


def pack(story_iter, n_bytes):
    buf = bytearray()
    for s in story_iter:
        buf += s.encode('utf-8') + b'\n\n'
        if len(buf) >= n_bytes:
            break
    rows = len(buf) // (SEQ + 1)
    return torch.frombuffer(bytes(buf[:rows * (SEQ + 1)]), dtype=torch.uint8).view(rows, SEQ + 1).clone()


third = len(unique) // 3
splits = {'val': unique[:third], 'test': unique[third:2 * third], 'train': unique[2 * third:]}
data = {
    'val': pack(splits['val'], EVAL_SEQS * (SEQ + 1)),
    'test': pack(splits['test'], EVAL_SEQS * (SEQ + 1)),
    'train': pack(splits['train'], TRAIN_BYTES),
}
keys = {k: {key(s) for s in v} for k, v in splits.items()}
print('story overlap train/val, train/test, val/test:',
      len(keys['train'] & keys['val']), len(keys['train'] & keys['test']), len(keys['val'] & keys['test']))
for k, v in data.items():
    torch.save(v, f'{out}/{k}.pt')
    print(k, tuple(v.shape), f'{v.numel() / 1e3:.0f}k bytes')
