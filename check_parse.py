with open('app.py') as f:
    content = f.read()
    # Try to parse it
    import ast
    try:
        ast.parse(content)
        print("File parses successfully!")
    except SyntaxError as e:
        print(f"Syntax Error at line {e.lineno}: {e.msg}")
        lines = content.split('\n')
        start = max(0, e.lineno - 5)
        end = min(len(lines), e.lineno + 3)
        for i in range(start, end):
            marker = ">>>" if i == e.lineno - 1 else "   "
            print(f"{marker} {i+1:4d}: {lines[i]}")
