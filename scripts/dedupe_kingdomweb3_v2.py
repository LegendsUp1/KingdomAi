#!/usr/bin/env python3
"""
Deduplicate keys in COMPLETE_BLOCKCHAIN_NETWORKS in kingdomweb3_v2.py

- Preserves the FIRST occurrence of each key (earliest definition wins)
- Removes ONLY later duplicate entries
- Creates a timestamped backup before writing changes (when --inplace is set)
- Supports dry-run to list duplicates without modifying the file

Usage:
  python scripts/dedupe_kingdomweb3_v2.py --file kingdomweb3_v2.py --list
  python scripts/dedupe_kingdomweb3_v2.py --file kingdomweb3_v2.py --inplace
  python scripts/dedupe_kingdomweb3_v2.py --file kingdomweb3_v2.py --output kingdomweb3_v2_dedup.py
"""

import argparse
import os
import sys
import time
from typing import List, Tuple, Dict


def find_matching_brace(s: str, start_idx: int) -> int:
    """Given s[start_idx] == '{', return index of matching closing '}' (inclusive)."""
    assert s[start_idx] == '{', 'find_matching_brace must start at a {'
    depth = 0
    i = start_idx
    in_string = False
    string_quote = ''
    escape = False
    while i < len(s):
        ch = s[i]
        if in_string:
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == string_quote:
                in_string = False
        else:
            if ch in ('"', "'"):
                in_string = True
                string_quote = ch
            elif ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    raise ValueError('No matching closing brace found')


def find_dict_block(s: str, anchor: str) -> Tuple[int, int]:
    """Find the start '{' and matching '}' for dict assigned after anchor.
    Returns (dict_start_idx, dict_end_idx_inclusive)
    """
    pos = s.find(anchor)
    if pos == -1:
        raise ValueError(f'Anchor not found: {anchor}')
    # Find first '{' after '='
    eq = s.find('=', pos)
    if eq == -1:
        raise ValueError('Could not find = after anchor')
    brace = s.find('{', eq)
    if brace == -1:
        raise ValueError('Could not find opening { for dict')
    end = find_matching_brace(s, brace)
    return brace, end


def parse_top_level_entries(s: str, dict_start: int, dict_end: int) -> List[Dict[str, int]]:
    """Parse top-level entries within s[dict_start:dict_end+1].
    Returns a list of dicts: {'key': str, 'start': int, 'end': int}
    where [start, end) slice covers the entire entry including trailing comma if present.
    """
    entries: List[Dict[str, int]] = []
    i = dict_start + 1  # position after '{'
    in_string = False
    string_quote = ''
    escape = False
    depth = 1  # we are inside the outer dict
    while i < dict_end:
        ch = s[i]
        if in_string:
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == string_quote:
                in_string = False
            i += 1
            continue

        # Not in string
        if ch in ('"', "'") and depth == 1:
            # Potential dict key
            key_quote = ch
            key_start_quote = i
            i += 1
            key_chars = []
            esc = False
            while i < dict_end:
                ch2 = s[i]
                if esc:
                    key_chars.append(ch2)
                    esc = False
                elif ch2 == '\\':
                    esc = True
                elif ch2 == key_quote:
                    break
                else:
                    key_chars.append(ch2)
                i += 1
            if i >= dict_end:
                break
            key_end_quote = i
            key_str = ''.join(key_chars)
            i += 1  # move past closing quote
            # Skip whitespace
            while i < dict_end and s[i].isspace():
                i += 1
            if i >= dict_end or s[i] != ':':
                # Not a key (unlikely), continue scanning
                continue
            i += 1  # skip ':'
            # Skip whitespace
            while i < dict_end and s[i].isspace():
                i += 1
            if i >= dict_end:
                break
            # Expect value to start with '{' for our network entries
            if s[i] != '{':
                # If value is not a dict, try to skip sensibly to next comma/newline
                j = i
                while j < dict_end and s[j] not in ['\n', ',']:
                    j += 1
                entry_line_start = s.rfind('\n', dict_start, key_start_quote)
                if entry_line_start == -1:
                    entry_line_start = dict_start + 1
                entry_end = j + (1 if j < dict_end and s[j] == ',' else 0)
                entries.append({'key': key_str, 'start': entry_line_start + 1, 'end': entry_end})
                i = entry_end
                continue
            # It's a dict value
            value_start = i
            value_end = find_matching_brace(s, value_start)
            j = value_end + 1
            # consume optional trailing comma
            while j < dict_end and s[j].isspace():
                j += 1
            if j < dict_end and s[j] == ',':
                j += 1
            # include the entire line start for clean removal
            entry_line_start = s.rfind('\n', dict_start, key_start_quote)
            if entry_line_start == -1:
                entry_line_start = dict_start
            entries.append({'key': key_str, 'start': entry_line_start + 1, 'end': j})
            i = j
            continue
        elif ch in ('"', "'"):
            in_string = True
            string_quote = ch
        elif ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth <= 0:
                break
        i += 1
    return entries


def dedupe_entries(s: str, entries: List[Dict[str, int]]):
    seen = {}
    dups = []
    for e in entries:
        k = e['key']
        if k in seen:
            dups.append(e)
        else:
            seen[k] = e
    return seen, dups


def apply_deletions(s: str, deletions: List[Tuple[int, int]]):
    # Apply from the end to preserve indices
    deletions_sorted = sorted(deletions, key=lambda x: x[0], reverse=True)
    out = s
    for a, b in deletions_sorted:
        out = out[:a] + out[b:]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--file', default='kingdomweb3_v2.py', help='Path to kingdomweb3_v2.py')
    ap.add_argument('--list', action='store_true', help='List duplicates only (dry run)')
    ap.add_argument('--inplace', action='store_true', help='Write changes back to the same file (makes backup)')
    ap.add_argument('--output', default='', help='Write deduped content to this path (no backup)')
    args = ap.parse_args()

    path = args.file
    if not os.path.isfile(path):
        print(f'ERROR: File not found: {path}')
        sys.exit(1)

    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    anchor = 'COMPLETE_BLOCKCHAIN_NETWORKS'
    dict_start, dict_end = find_dict_block(content, anchor)

    entries = parse_top_level_entries(content, dict_start, dict_end)
    seen, dups = dedupe_entries(content, entries)

    print(f'Total entries parsed: {len(entries)}')
    print(f'Unique keys: {len(seen)}')
    print(f'Duplicates found: {len(dups)}')

    if dups:
        print('\nDuplicate keys (later definitions to remove):')
        from collections import Counter
        ctr = Counter([e['key'] for e in dups])
        for k, cnt in ctr.most_common():
            print(f'  - {k} (remove {cnt} later occurrence(s))')
    else:
        print('No duplicates detected.')

    if args.list:
        return

    if not dups:
        if args.inplace or args.output:
            print('No changes necessary.')
        return

    deletions = [(e['start'], e['end']) for e in dups]
    new_content = apply_deletions(content, deletions)

    if args.inplace:
        # Make backup
        ts = time.strftime('%Y%m%d_%H%M%S')
        backup = f"{path}.bak.{ts}"
        with open(backup, 'w', encoding='utf-8') as bf:
            bf.write(content)
        with open(path, 'w', encoding='utf-8') as wf:
            wf.write(new_content)
        print(f"\n✅ Deduplication complete. Backup saved to: {backup}")
        # Recount after write
        _, _, = dict_start, dict_end
        print('Wrote changes in-place.')
    elif args.output:
        with open(args.output, 'w', encoding='utf-8') as wf:
            wf.write(new_content)
        print(f"\n✅ Deduplication complete. Wrote to: {args.output}")
    else:
        # Default to stdout if no output flags given
        sys.stdout.write(new_content)


if __name__ == '__main__':
    main()
