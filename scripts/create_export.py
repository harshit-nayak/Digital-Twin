import os
import shutil
import zipfile
import argparse

EXCLUDE_DIRS = {
    '.git', 'venv', '__pycache__', '.vs',
    'app/api', 'logs', 'config'
}
EXCLUDE_PATTERNS = ('.md', '.sqlite3')


def should_exclude(path, rel_path):
    for d in EXCLUDE_DIRS:
        if rel_path.startswith(d + os.sep) or rel_path == d:
            return True
    for pat in EXCLUDE_PATTERNS:
        if rel_path.endswith(pat):
            return True
    return False


def collect_files(root):
    included = []
    excluded = []
    for dirpath, dirnames, filenames in os.walk(root):
        # compute relative dir
        rel_dir = os.path.relpath(dirpath, root)
        if rel_dir == '.':
            rel_dir = ''
        # filter out directories we don't want to descend into
        dirnames[:] = [d for d in dirnames if not should_exclude(None, os.path.join(rel_dir, d))]
        for f in filenames:
            rel_path = os.path.join(rel_dir, f) if rel_dir else f
            if should_exclude(None, rel_path):
                excluded.append(rel_path)
            else:
                included.append(rel_path)
    return included, excluded


def copy_files(root, included, out_dir):
    for rel_path in included:
        src = os.path.join(root, rel_path)
        dst = os.path.join(out_dir, rel_path)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)


def make_zip(out_dir, zip_path):
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for dirpath, dirnames, filenames in os.walk(out_dir):
            for f in filenames:
                full = os.path.join(dirpath, f)
                arcname = os.path.relpath(full, out_dir)
                zf.write(full, arcname)


def main():
    parser = argparse.ArgumentParser(description='Create sanitized export of repository')
    parser.add_argument('--root', default='.', help='Repository root to export')
    parser.add_argument('--out', default='export_for_github', help='Output folder')
    parser.add_argument('--zip', action='store_true', help='Also create a zip file')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be included/excluded')
    args = parser.parse_args()

    root = os.path.abspath(args.root)
    out_dir = os.path.abspath(args.out)

    included, excluded = collect_files(root)

    print('Included files:')
    for p in included:
        print('  ', p)
    print('\nExcluded files:')
    for p in excluded[:200]:
        print('  ', p)
    if len(excluded) > 200:
        print('  ... and {} more excluded files'.format(len(excluded) - 200))

    if args.dry_run:
        print('\nDry run complete. No files copied.')
        return

    proceed = input('\nProceed to create export in "{}"? [y/N]: '.format(out_dir))
    if proceed.lower() != 'y':
        print('Aborted by user.')
        return

    if os.path.exists(out_dir):
        print('Removing existing output directory:', out_dir)
        shutil.rmtree(out_dir)
    os.makedirs(out_dir, exist_ok=True)

    print('Copying files...')
    copy_files(root, included, out_dir)
    print('Files copied to', out_dir)

    if args.zip:
        zip_path = out_dir.rstrip(os.sep) + '.zip'
        print('Creating zip archive', zip_path)
        make_zip(out_dir, zip_path)
        print('Zip created at', zip_path)


if __name__ == '__main__':
    main()
