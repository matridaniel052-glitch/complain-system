import re

# Read the file
with open('app.py') as f:
    content = f.read()

# Undo the em-dash replacement: we need to convert '-' back to '—' 
# in docstrings/comments only, not in code

lines = content.split('\n')
fixed_lines = []
in_docstring = False

for line in lines:
    # Check if line contains docstring markers
    if '"""' in line:
        in_docstring = not in_docstring
    
    # If we're in a docstring or comment, convert - back to —
    if in_docstring or line.strip().startswith('#'):
        # Only fix specific patterns that should have em-dash
        line = re.sub(r'(FIGURE|Figure|Section|Appendix|PAGE|PAGE|FEEDBACK|DEPARTMENTS|SETTINGS|DASHBOARD|ACCESS|LOGIN|STUDENT|COMPLAINT|ADMIN) - ', 
                      r'\1 — ', line)
    
    fixed_lines.append(line)

# Write back
with open('app.py', 'w') as f:
    f.write('\n'.join(fixed_lines))

print("Fixed em-dashes in docstrings/comments only")
