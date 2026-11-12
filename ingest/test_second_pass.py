"""Adversarial tests for the second verification pass (run: python3 test_second_pass.py)."""
from summaries import sentence_check
C = {"c_aaaaaaaaaaaaaa": {"id": "c_aaaaaaaaaaaaaa", "status": "verified", "text": "Jane Doe was recorded as Not Voting on 12 of 400 roll calls (3.0%).", "value": [12, 400], "excerpt": "x"},
     "c_bbbbbbbbbbbbbb": {"id": "c_bbbbbbbbbbbbbb", "status": "blocked", "text": "Jane Doe voted Yea.", "value": "Yea", "excerpt": "x"}}
cases = [
    ("Jane Doe was recorded as Not Voting on 12 of 400 roll calls. [claim:c_aaaaaaaaaaaaaa]", True),
    ("Jane Doe missed 15 votes. [claim:c_aaaaaaaaaaaaaa]", False),                      # invented number
    ("Jane Doe missed votes to meet John Smith. [claim:c_aaaaaaaaaaaaaa]", False),      # invented person
    ("Jane Doe is influential. [claim:c_aaaaaaaaaaaaaa]", False),                       # loaded language
    ("Jane Doe voted Yea. [claim:c_bbbbbbbbbbbbbb]", False),                            # blocked claim
    ("Jane Doe is a senator.", False),                                                  # no claim tag
    ("Jane Doe missed 12 of 400 votes. [claim:c_aaaaaaaaaaaaaa] She is corrupt.", False),
]
fails = 0
for text, want in cases:
    ok, probs = sentence_check(text, C)
    print("PASS" if ok == want else "FAIL", want, "|", text[:70], probs[:1])
    fails += ok != want
raise SystemExit(fails)
