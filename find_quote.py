with open('app.py') as f:
    lines = f.readlines()

in_triple = False
start_line = 0

for i, line in enumerate(lines, 1):
    count = line.count('"""')
    if count == 0:
        continue
    elif count % 2 == 1:
        if in_triple:
            print(f"CLOSED: Multiline string started at line {start_line}, closed at line {i}")
            in_triple = False
        else:
            start_line = i
            in_triple = True
            print(f"OPENED: Multiline string starts at line {i}")
            
if in_triple:
    print(f"ERROR: Unclosed multiline string starting at line {start_line}")
    for j in range(max(0, start_line-3), min(len(lines), start_line+5)):
        print(f"{j+1:4d}: {lines[j]}", end='')
