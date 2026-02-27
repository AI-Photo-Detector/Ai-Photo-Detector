def forensic_result_template(test_name: str) -> dict:
    """
    Standard return structure for all forensic modules.
    Every forensic test MUST use this template.
    """

    return {
        "test_name": test_name,
        "score": 0.0,              # float between 0.0 and 1.0
        "confidence": 0.0,         # float between 0.0 and 1.0
        "verdict": "inconclusive", # "clean" | "suspicious" | "inconclusive"
        "details": {}              # dictionary containing structured evidence
    }
