import csv              

def write_to_csv(rows, fileName, alphabetical=False):
    with open(fileName, mode="w", newline="") as file:
        if alphabetical:
            rows = sorted(rows, key=lambda x: x.get('product_name', ''))
        fieldnames = rows[0].keys() if rows else []
        dict_writer = csv.DictWriter(file, fieldnames=fieldnames)
        dict_writer.writeheader()
        dict_writer.writerows(rows)

def read_from_csv(fileName):
    with open(fileName, mode="r") as file:
        dict_reader = csv.DictReader(file)
        return [row for row in dict_reader]
                