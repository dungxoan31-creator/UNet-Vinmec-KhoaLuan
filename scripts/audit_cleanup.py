import os
import sys

skip_dirs = {'.git', '.venv'}
ext_counts = {}
dir_counts = {}
total_files = 0

for root, dirs, files in os.walk('.', topdown=True):
    dirs[:] = [d for d in dirs if d not in skip_dirs]
    rel_root = os.path.relpath(root, '.')
    top_dir = rel_root.split(os.sep)[0]
    dir_counts[top_dir] = dir_counts.get(top_dir, 0) + len(files)
    total_files += len(files)
    for f in files:
        _, ext = os.path.splitext(f)
        ext = ext.lower()
        ext_counts[ext] = ext_counts.get(ext, 0) + 1

print(f"Total files: {total_files}")
print("\nFiles by top directory:")
for d, c in sorted(dir_counts.items(), key=lambda x: -x[1]):
    print(f"  {d}: {c}")

print("\nFiles by extension:")
for e, c in sorted(ext_counts.items(), key=lambda x: -x[1])[:25]:
    label = e if e else "[no ext]"
    print(f"  {label}: {c}")
