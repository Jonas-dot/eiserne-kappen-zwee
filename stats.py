import re
from collections import Counter

with open("logs/statistics.log") as f:
    lines = f.readlines()

counter = Counter()
for line in lines:
    m = re.search(r"Sektor=(.*?) \| QR=(True|False)", line)
    if m:
        sector, qr = m.groups()
        counter[(sector, qr)] += 1

print("\n--- Statistik ---")
total = sum(counter.values())
for sector in sorted(set(s for (s, _) in counter.keys())):
    total_sector = sum(v for (s, q), v in counter.items() if s == sector)
    qr_sector = sum(v for (s, q), v in counter.items() if s == sector and q == "True")
    print(f"{sector}: {total_sector} Tickets (davon {qr_sector} mit QR)")
print(f"Gesamt: {total} Tickets")
