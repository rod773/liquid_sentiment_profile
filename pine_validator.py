import re
import sys

def fix_pine_script(content: str) -> tuple[str, list[str]]:
    lines = content.split('\n')
    fixes = []

    # Fix 1: Short title too long
    for i, line in enumerate(lines):
        m = re.match(r'(.*indicator\([^,]+,\s*)(\'[^\']{11,}\')(.*)', line)
        if m:
            short = m.group(2)
            if len(short) - 2 > 10:
                lines[i] = m.group(1) + "'LuxAlgo'" + m.group(3)
                fixes.append(f"Line {i+1}: Shortened title from {short} to 'LuxAlgo'")

    # Fix 2: ta.change without bool() in ternary (t: int, f: bool mismatch)
    pattern_change = re.compile(r'(dayofweek\s*!=\s*dayofweek\[1\])\s*\?\s*([^:]+?)\s*:\s*ta\.change\b')
    for i, line in enumerate(lines):
        m = pattern_change.search(line)
        if m:
            old = m.group(0)
            new = m.group(1) + ' ? ' + m.group(2) + ' : bool(ta.change'
            # more precise: find the exact match and replace
            idx = line.find(m.group(0))
            if idx >= 0:
                # Parse more carefully
                before = line[:idx]
                match_text = m.group(0)
                after = line[idx + len(match_text):]
                # Find the opening paren after ta.change
                rest = match_text
                # We need to capture the full ta.change(...)
                tc_match = re.search(r'ta\.change\(', rest)
                if tc_match:
                    start = tc_match.start()
                    # The part after dayofweek[1] ? ... :
                    cond_part = rest[:start].rstrip()
                    tc_call = rest[start:]
                    lines[i] = before + cond_part + ' : bool(' + tc_call + after
                    fixes.append(f"Line {i+1}: Wrapped ta.change() in bool()")
                    break

    # Fix 3: b.field[n] -> (b[n]).field for UDT fields
    for i, line in enumerate(lines):
        # Match b.h[n], b.l[n], b.i[n], b.c[n], b.o[n], b.v[n]
        new_line = re.sub(r'\bb\.(h|l|i|c|o|v)\[(\w+)\]', r'(b[\2]).\1', line)
        if new_line != line:
            fixes.append(f"Line {i+1}: Fixed UDT field history reference")
            lines[i] = new_line

    # Fix 4: field_X = b.h/l/i local vars used with [n] -> inline
    field_assign_pattern = re.compile(r'^\s*(field_\d+)\s*=\s*b\.(h|l|i)\s*$')
    field_usage_pattern = re.compile(r'\bfield_\d+\[(\w+)\]')
    
    # Track field variable names and what they map to
    field_map = {}  # field_X -> (line_idx, b_field)
    field_refs = {}  # field_X -> [(line_idx, usage)]
    
    for i, line in enumerate(lines):
        m = field_assign_pattern.match(line)
        if m:
            field_name = m.group(1)
            b_field = m.group(2)
            field_map[field_name] = (i, b_field)
        usages = [(m.start(), m.group(0), m.group(1)) for m in field_usage_pattern.finditer(line)]
        for start, full, idx_var in usages:
            if full.startswith('field_'):
                field_refs.setdefault(full.split('[')[0], []).append((i, full, idx_var))
    
    if field_map:
        for field_name, (assign_line, b_field) in field_map.items():
            # Remove the assignment line (replace with empty/comment)
            lines[assign_line] = ''  # Will clean up later
            fixes.append(f"Line {assign_line+1}: Removed {field_name} local var, using b.{b_field} directly")
        # Remove empty lines (only whitespace)
    
    # Remove blank lines that are now empty
    lines = [l for l in lines if l != '']

    # Re-run fix 3 on modified content (in case removal shifted things)
    content = '\n'.join(lines)
    lines = content.split('\n')
    for i, line in enumerate(lines):
        new_line = re.sub(r'\bb\.(h|l|i|c|o|v)\[(\w+)\]', r'(b[\2]).\1', line)
        if new_line != line:
            lines[i] = new_line

    return '\n'.join(lines), fixes


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python pine_validator.py <file.pine>")
        sys.exit(1)

    filepath = sys.argv[1]
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    fixed_content, fixes = fix_pine_script(content)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(fixed_content)

    print(f"Fixed {filepath}")
    for fix in fixes:
        print(f"  ✓ {fix}")
    if not fixes:
        print("  No issues found.")
