## 1. File Location
Each forensic test must be placed inside: 

`src/forensics/`

Example file names:

- `ela.py`
- `noise.py`
- `copy_move.py`
- `resampling.py`

## 2. Required Return Format

Every forensic function must return a dictionary with **exactly** the following keys:

```python
{
  "test_name": str,
  "score": float,        # must be between 0.0 and 1.0
  "confidence": float,   # must be between 0.0 and 1.0
  "verdict": "clean" | "suspicious" | "inconclusive",
  "details": dict
}
```

### Rules

- score must always be between 0.0 and 1.0
- confidence must always be between 0.0 and 1.0
- verdict must be exactly one of:
  - `"clean"`
  - `"suspicious"`
  - `"inconclusive"`
- details must always be a dictionary (empty {} is acceptable)
- Do not rename keys
- Do not return a string

## 3. Use the Shared Template

All forensic modules must use the shared template function to construct their return dictionary.

Import the template:

```python
from .template import forensic_result_template

def run(image_path: str) -> dict:

    result = forensic_result_template("Error Level Analysis (ELA)")

    # ---- Your forensic logic here ----
    score = 0.75
    confidence = 0.85

    result["score"] = round(score, 3)
    result["confidence"] = confidence

    if score >= 0.6:
        result["verdict"] = "suspicious"
    elif score >= 0.3:
        result["verdict"] = "inconclusive"
    else:
        result["verdict"] = "clean"

    result["details"] = {
        "example_metric": 0.23
    }

    return result
```

### Important

- Always use the shared template.
- Do not manually construct a different dictionary structure.
- Do not remove required keys.

## 4. Official Test Names (Must Match Exactly)

The `test_name` field must match one of the following values **exactly**.

Spelling and punctuation matter.

- `EXIF Metadata Analysis`
- `Error Level Analysis (ELA)`
- `JPEG Compression Artifact Analysis`
- `Lighting & Shadow Consistency Analysis`
- `Copy–Move (Clone) Detection`
- `Noise Pattern / Texture Consistency Analysis`
- `Edge & Boundary Inconsistency Detection`
- `Resampling / Scaling Detection`

### Important

- Do **not** rename tests.
- Do **not** shorten names.
- Do **not** modify punctuation.
- If the name does not match exactly, the aggregation logic may ignore the test.

## 5. Validation Before Pushing

Before committing your forensic module, complete the following checks:

### Required Tests

Test your module on at least:

1. A normal phone photo (expected: mostly clean)
2. A screenshot (expected: often inconclusive or weak signal)
3. An AI-generated or edited image (expected: suspicious or higher score)

### Required Validation

- `score` is always between **0.0 and 1.0**
- `confidence` is always between **0.0 and 1.0**
- `verdict` correctly matches score thresholds
- The returned dictionary contains **all required keys**
- The function does **not crash**
- Errors are handled gracefully

### Final Rule

If the return structure does not match the required schema, the module will not be merged.

## 6. Integration Rule

All forensic modules will be integrated into the main analysis pipeline.

The pipeline expects every module to return the standardized result dictionary.

If a module:

- Returns a different structure
- Renames required keys
- Uses incorrect `test_name`
- Returns values outside the 0–1 range
- Crashes without handling errors

It will break the aggregation process and will not be merged into `main`.

### Important

The main pipeline will combine all forensic results automatically.  
Your responsibility is only to return a correctly formatted dictionary.

Keep your module focused, consistent, and stable.
