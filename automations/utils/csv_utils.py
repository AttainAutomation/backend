import csv              
import os

def write_to_csv(rows, fileName, alphabetical=False):
    os.makedirs(os.path.dirname(fileName), exist_ok=True)
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
                
def print_csv_column_values(filename):
    """
    Print column names and their corresponding values for each row in the CSV file,
    starting from the second row (assuming the first row contains column names).

    :param filename: Path to the CSV file.
    """
    with open(filename, mode='r', newline='') as file:
        reader = csv.DictReader(file)

        for row_number, row in enumerate(reader, start=1):  # Start counting from 1 for clarity
            print(f"Row {row_number}:")
            for column_name, value in row.items():
                print(f"    {column_name}: {value}")
            print()  # Add a blank line for separation between rows

# Example usage
filename = 'automations/utils/coremark.csv'  # Replace with your CSV file path
print_csv_column_values(filename)
