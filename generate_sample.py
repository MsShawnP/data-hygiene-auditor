"""Generate a messy sample Excel file for testing the Data Hygiene Auditor."""
from pathlib import Path

from openpyxl import Workbook


def build_workbook():
    wb = Workbook()
    ws = wb.active
    ws.title = "Customers"

    headers = [
        "CustomerID", "FirstName", "LastName", "Email", "Phone",
        "JoinDate", "AccountBalance", "Status", "ZipCode", "Notes"
    ]
    ws.append(headers)

    # --- Row data with intentional problems ---
    rows = [
        # Clean-ish rows
        ["CUST-001", "Alice", "Johnson", "alice@example.com", "(555) 123-4567", "2023-01-15", "$1,250.00", "Active", "30301", "Preferred customer"],
        ["CUST-002", "Bob", "Smith", "bob.smith@example.com", "555-234-5678", "01/15/2023", "1250.00", "Active", "30302", ""],
        ["CUST-003", "Charlie", "Williams", "charlie.w@example.com", "5553456789", "Jan 15, 2023", "$2,500", "active", "30303", "VIP"],
        # Mixed date formats
        ["CUST-004", "Diana", "Brown", "diana.b@example.com", "(555) 456-7890", "2023-02-20", "$3,100.50", "Active", "30304", "Referred by Alice"],
        ["CUST-005", "Edward", "Davis", "edward@example.com", "555.567.8901", "02/20/2023", "3100.50", "Inactive", "30305", ""],
        ["CUST-006", "Fiona", "Garcia", "fiona.g@example.com", "+1-555-678-9012", "Feb 20, 2023", "$4,200.00", "ACTIVE", "30306", "Corporate account"],
        # Phantom duplicates (whitespace/case variations)
        ["CUST-007", "alice", "johnson", "alice@example.com", "(555) 123-4567", "2023-01-15", "$1,250.00", "Active", "30301", "Preferred customer"],
        ["CUST-008", " Alice ", " Johnson", "ALICE@EXAMPLE.COM", "(555) 123-4567", "2023-01-15", "$1,250.00", "Active", "30301", "Preferred customer"],
        ["CUST-009", "Bob", "Smith ", "bob.smith@example.com ", "555-234-5678", "01/15/2023", "1250.00", "Active", "30302", ""],
        # Suspiciously uniform / placeholder data
        ["CUST-010", "Test", "User", "test@test.com", "000-000-0000", "2023-01-01", "$0.00", "Active", "00000", "TEST"],
        ["CUST-011", "Test", "User", "test@test.com", "000-000-0000", "2023-01-01", "$0.00", "Active", "00000", "TEST"],
        ["CUST-012", "Test", "User", "test@test.com", "000-000-0000", "2023-01-01", "$0.00", "Active", "00000", "TEST"],
        ["CUST-013", "N/A", "N/A", "n/a", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A"],
        ["CUST-014", "TBD", "TBD", "tbd@tbd.com", "TBD", "TBD", "TBD", "TBD", "TBD", "TBD"],
        # Numbers stored as text, codes in name fields
        ["CUST-015", "REF-4421", "Martinez", "martinez@example.com", "(555) 789-0123", "2023-03-10", "five thousand", "1", "303-07", ""],
        ["CUST-016", "Grace", "ABC-CORP-2023", "grace@example.com", "not available", "March 10 2023", "$5,000", "Active", "30308", "See ticket #4421"],
        ["CUST-017", "Henry", "Lee", "henrylee", "(555) 890-1234", "2023/03/15", "$6,100.00", "Active", "30309", ""],
        # Missing data flood
        ["CUST-018", "", "", "", "", "", "", "", "", ""],
        ["CUST-019", None, None, None, None, None, None, None, None, None],
        ["CUST-020", "  ", "  ", "  ", "  ", "  ", "  ", "  ", "  ", "  "],
        # More mixed formats
        ["CUST-021", "Irene", "Wilson", "irene.w@example.com", "555 012 3456", "3/15/2023", "$7200", "Suspended", "30310", "Payment issue"],
        ["CUST-022", "Jack", "Taylor", "jack.t@example.com", "(555)0123456", "15-Mar-2023", "7,200.00", "Active", "30311", ""],
        ["CUST-023", "Karen", "Anderson", "karen.a@example.com", "1-555-123-4567", "2023.03.15", "$8,500.00", "active", "30312-1234", "Extended zip"],
        # More suspicious uniformity
        ["CUST-024", "John", "Doe", "john@doe.com", "555-555-5555", "2023-01-01", "$0.00", "Active", "12345", ""],
        ["CUST-025", "Jane", "Doe", "jane@doe.com", "555-555-5555", "2023-01-01", "$0.00", "Active", "12345", ""],
        ["CUST-026", "John", "Doe", "john@doe.com", "555-555-5555", "2023-01-01", "$0.00", "Active", "12345", ""],
        # Wrong-purpose fields
        ["1027", "Lisa", "Thomas", "lisa.t@example.com", "(555) 234-5678", "2023-04-01", "$9,100.00", "Active", "30313", ""],
        ["CUST-028", "Mike", "Jackson", "mike.j@example.com", "(555) 345-6789", "2023-04-05", "$10,250.00 USD", "Y", "30314", "Balance includes pending"],
        ["CUST-029", "Nancy", "White", "nancy w@example.com", "(555) 456 7890", "04-05-2023", "$-500.00", "Active", "3031", "Credit balance"],
        ["CUST-030", "Oscar", "Harris", "oscar@example.com", "(555) 567-8901", "2023-04-10", "$11,000.00", "Active", "30316", ""],
    ]

    for row in rows:
        ws.append(row)

    # Sheet 2: Orders (smaller, to show multi-sheet support)
    ws2 = wb.create_sheet("Orders")
    order_headers = ["OrderID", "CustomerID", "OrderDate", "Amount", "ShipDate", "Status"]
    ws2.append(order_headers)
    order_rows = [
        ["ORD-001", "CUST-001", "2023-06-01", "$150.00", "2023-06-03", "Shipped"],
        ["ORD-002", "CUST-001", "06/15/2023", "200", "06/17/2023", "Shipped"],
        ["ORD-003", "CUST-002", "Jun 20, 2023", "$175.50", "Jun 22 2023", "shipped"],
        ["ORD-004", "CUST-003", "2023-07-01", "$300.00", "2023-07-03", "Delivered"],
        ["ORD-005", "CUST-003", "2023-07-01", "$300.00", "2023-07-03", "Delivered"],
        ["ORD-006", "CUST-010", "2023-01-01", "$0.00", "2023-01-01", "Test"],
        ["ORD-007", "CUST-010", "2023-01-01", "$0.00", "2023-01-01", "Test"],
        ["ORD-008", "cust-003", "7/1/2023", "300", "7/3/2023", "delivered"],
        ["ORD-009", "CUST-004", "2023-08-10", "$450.00", "", "Pending"],
        ["ORD-010", "CUST-004", "2023/08/10", "$450", None, "PENDING"],
    ]
    for row in order_rows:
        ws2.append(row)

    return wb


def main():
    output_path = Path(__file__).parent / "samples" / "input" / "sample_messy_data.xlsx"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb = build_workbook()
    wb.save(output_path)
    print(f"Sample file generated: {output_path}")


if __name__ == "__main__":
    main()
