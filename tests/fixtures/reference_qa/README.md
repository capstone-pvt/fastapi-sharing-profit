# Reference-object QA set

Drop real-world photos here grouped by reference type. The `run_reference_qa.py`
script in `scripts/` reads `ground_truth.csv` and runs each image through
`detect_reference_object`, printing a pass/fail table.

## Directory layout

```
tests/fixtures/reference_qa/
├── README.md
├── ground_truth.csv
└── images/
    ├── coin_php_1/
    ├── coin_php_5/
    ├── coin_php_10/
    ├── id_card/
    ├── bill_php/
    ├── aruco_4cm/
    └── aruco_10cm/
```

## `ground_truth.csv` format

```
filename,reference_type,ground_truth_pixels_per_cm
images/coin_php_5/IMG_001.jpg,coin_php_5,42.3
...
```

Measure `ground_truth_pixels_per_cm` manually: pick a ruler visible in the photo,
count pixels-per-cm in an image viewer.

## Target: ≤10% pixels-per-cm error on ≥80% of images per reference type.
