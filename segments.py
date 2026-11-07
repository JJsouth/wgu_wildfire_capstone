SEGMENTS = {
    "all":     ("All fires",                 lambda df: df),
    "tail":    ("Tail fires (≥ 1,000 acres)", lambda df: df[df["fire_size"] >= 1000]),
    "body":    ("Body fires (< 1,000 acres)", lambda df: df[df["fire_size"] < 1000]),
    "class_A": ("Class A (≤ 0.25 acres)",     lambda df, c="A": df[df["fire_size_class"] == c]),
    "class_B": ("Class B (0.26-9.9 acres)",   lambda df, c="B": df[df["fire_size_class"] == c]),
    "class_C": ("Class C (10-99.9 acres)",    lambda df, c="C": df[df["fire_size_class"] == c]),
    "class_D": ("Class D (100-299 acres)",    lambda df, c="D": df[df["fire_size_class"] == c]),
    "class_E": ("Class E (300-999 acres)",    lambda df, c="E": df[df["fire_size_class"] == c]),
    "class_F": ("Class F (1,000-4,999 acres)", lambda df, c="F": df[df["fire_size_class"] == c]),
    "class_G": ("Class G (5,000+ acres)",     lambda df, c="G": df[df["fire_size_class"] == c]),
}