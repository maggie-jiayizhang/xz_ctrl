def make_script_from_csv_rows(rows):
    """
    Given a list of rows (each a list of strings),
    return a single string with each row joined by '|',
    expanding loops as needed.
    Assumes the code is already validated.
    """
    output = []
    i = 0
    n = len(rows)
    while i < n:
        row = rows[i]
        line = row[0].strip() if row else ''
        if line.lower().startswith('loop '):
            # Get n_iter
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                n_iter = int(parts[1])
            else:
                n_iter = 1
            # Find loop block
            loop_block = []
            i += 1
            while i < n and not (rows[i][0].strip().lower() == 'endloop'):
                loop_block.append(rows[i][0].strip())
                i += 1
            # Expand loop
            for _ in range(n_iter):
                output.extend(loop_block)
            # Skip 'endloop'
            i += 1
        else:
            if line and line.lower() != 'endloop':
                output.append(line)
            i += 1
    return ' | '.join(output)
