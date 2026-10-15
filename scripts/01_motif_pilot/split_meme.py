"""Split a MEME motif file into N chunk files (header copied to each).
Usage: split_meme.py <in.meme> <n_chunks> <out_prefix>"""
import sys

path, n, prefix = sys.argv[1], int(sys.argv[2]), sys.argv[3]
with open(path) as fh:
    text = fh.read()
head, *blocks = text.split("\nMOTIF ")
blocks = ["MOTIF " + b.rstrip("\n") + "\n\n" for b in blocks]
for i in range(n):
    part = blocks[i::n]
    if part:
        with open(f"{prefix}_{i:03d}.meme", "w") as out:
            out.write(head.rstrip("\n") + "\n\n" + "".join(part))
