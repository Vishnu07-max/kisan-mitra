# Crop Doctor v2: check on unsupported photos

Date: 2026-10-18. Rule tested (set BEFORE the photos were collected):
disease result needs confidence >= 0.90, Healthy result needs >= 0.95, rice classes withheld.

| Folder | Photos | Wrongly answered | Notes |
|---|---|---|---|
| scenery | 37 | 2 | Strawberry Leaf Scorch 0.93, Bell Pepper Healthy 0.95 |
| other-plant leaves | 13 | 0 | |
| relatives (brinjal, chilli) | 6 | 0 | all predicted as rice classes, which are withheld |
| other (hands, soil, etc.) | 5 | 1 | Tomato Healthy 0.96 |
| all | 61 | 3 | about 2% to 13% plausible true rate (Wilson 95%) |

Limits: very small sample; 0 of 19 leaf photos wrong still allows a true rate near 17%;
collection method and species not recorded; NOT field-validated; photos are not stored in the repo.
If rice is ever supported, this test must be repeated: rice classes currently absorb many unknown leaves.
