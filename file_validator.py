import csv

EXPECTED_HEADER = ["batch_id","timestamp"] + [f"reading{i}" for i in range(1,11)]

def validate_csv(file_like):
    reader = csv.reader(file_like)
    seen, errors = set(), []
    
    try:
        header = next(reader)
        if header != EXPECTED_HEADER:
            return False, ["Header mismatch"]
    except StopIteration:
        return False, ["Empty file"]
    
    for i, row in enumerate(reader, start=2):
        if len(row) != len(EXPECTED_HEADER):
            errors.append(f"Row {i}: Wrong number of fields")
            continue
        batch_id = row[0]
        if batch_id in seen:
            errors.append(f"Row {i}: Duplicate batch_id")
        else:
            seen.add(batch_id)
        for j, val in enumerate(row[2:], start=1):
            try:
                float(val)
            except ValueError:
                errors.append(f"Row {i}: reading{j} not numeric")
                
    return len(errors)==0, errors
