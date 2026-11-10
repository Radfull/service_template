import pandas as pd
import pandera.pandas as pa
import pytest
from market.data import EXPORT, ROWS


@pytest.fixture()
def frame():
    return pd.DataFrame({
        "age": [22, 38, 49, 67], "work_experience": [1.0, 5.0, 10.0, 14.0],
        "family_size": [1, 2, 3, 4], "gender": [0, 1, 0, 1],
        "ever_married": [0, 1, 1, 1], "graduated": [0, 1, 1, 1],
        "spending_score": [0, 1, 2, 0], "segmentation": list("ABCD"),
    })


def test_good_rows(frame):
    ROWS.validate(frame, lazy=True)


def test_bad_value(frame):
    frame.loc[0, "age"] = 264
    with pytest.raises(pa.errors.SchemaErrors) as exc:
        ROWS.validate(frame, lazy=True)
    assert "age" in set(exc.value.failure_cases["column"])


def test_small_export(frame):
    with pytest.raises(pa.errors.SchemaErrors) as exc:
        EXPORT.validate(frame, lazy=True)
    assert "too_few_rows" in set(exc.value.failure_cases["check"])