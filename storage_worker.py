import time, os

DISK_BASE = "/var/data"

paths = [
    os.path.join(DISK_BASE, "subservience"),
    os.path.join(DISK_BASE, "Sophy_MasterLog"),
    os.path.join(DISK_BASE, "Sophy_HistoricalTopics"),
]

for p in paths:
    os.makedirs(p, exist_ok=True)

print("Sophy Storage Worker running. Shared disk mounted at /var/data")

while True:
    time.sleep(3600)
