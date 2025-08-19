from pathlib import Path
import csv


def test_synthetic_csv_header():
    """Test that generated CSV has expected header format."""
    p = Path("data/demo.csv")
    if not p.exists():
        # Generate it if needed
        from neurorelay.scripts.synthetic_ssvep import make_session
        make_session(p, seed=1)
    
    with p.open() as f:
        r = csv.reader(f)
        header = next(r)
    assert header[:5] == ["t", "O1", "Oz", "O2", "label"]


def test_synthetic_csv_data_format():
    """Test that CSV data rows have expected numeric format."""
    p = Path("data/demo.csv")
    if not p.exists():
        from neurorelay.scripts.synthetic_ssvep import make_session
        make_session(p, seed=1)
    
    with p.open() as f:
        r = csv.DictReader(f)
        first_row = next(r)
    
    # Check that numeric columns are parseable
    assert float(first_row["t"]) >= 0.0
    assert isinstance(float(first_row["O1"]), float)
    assert isinstance(float(first_row["Oz"]), float) 
    assert isinstance(float(first_row["O2"]), float)
    assert first_row["label"] in ["SUMMARIZE", "TODOS", "DEADLINES", "EMAIL", ""]