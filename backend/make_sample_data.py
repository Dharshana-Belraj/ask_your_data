"""Generates sample_sales.csv (e-commerce orders) so you can try the app immediately."""
import numpy as np
import pandas as pd

rng = np.random.default_rng(7)
n = 6000
cats = {
    "Electronics": [("Laptop", 900), ("Headphones", 120), ("Smartwatch", 220), ("Tablet", 450)],
    "Home": [("Air Fryer", 110), ("Desk Lamp", 45), ("Vacuum", 260), ("Coffee Maker", 90)],
    "Fashion": [("Sneakers", 85), ("Jacket", 140), ("Backpack", 60), ("Sunglasses", 75)],
    "Sports": [("Yoga Mat", 35), ("Dumbbells", 80), ("Cycle Helmet", 55), ("Tent", 190)],
}
regions = {"North": 1.0, "South": 0.8, "East": 1.2, "West": 1.1}
dates = pd.to_datetime("2023-01-01") + pd.to_timedelta(rng.integers(0, 730, n), unit="D")
rows = []
for i, d in enumerate(dates):
    cat = rng.choice(list(cats))
    prod, price = cats[cat][rng.integers(0, 4)]
    reg = rng.choice(list(regions), p=[.25, .2, .30, .25])
    season = 1 + 0.35 * np.sin((d.month - 3) / 12 * 2 * np.pi) + (0.2 if d.year == 2024 else 0)
    qty = max(1, int(rng.poisson(2 * season * regions[reg])))
    disc = float(rng.choice([0, 0, 0.05, 0.1, 0.2]))
    rows.append((f"ORD{100000 + i}", d.date(), f"CUST{rng.integers(1, 1500):04d}", reg, cat, prod,
                 qty, price, disc, round(qty * price * (1 - disc), 2)))
cols = ["order_id", "order_date", "customer_id", "region", "category", "product",
        "quantity", "unit_price", "discount", "revenue"]
pd.DataFrame(rows, columns=cols).sort_values("order_date").to_csv("sample_sales.csv", index=False)
print("Wrote sample_sales.csv")
