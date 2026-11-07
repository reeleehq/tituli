"""Credits.from_dict refuses keys it does not read, so no credit is dropped silently."""

import pytest

from tituli import Credits


def test_known_keys_build_the_roll():
    cr = Credits.from_dict(
        {
            "title": "T",
            "sections": [
                {"heading": "Images", "entries": ["A, CC BY 4.0", {"role": "r", "name": "n"}]}
            ],
            "closing": "thanks",
        }
    )
    assert cr.line_count >= 2


@pytest.mark.parametrize(
    "spec, where",
    [
        ({"sections": [{"heading": "Images", "lines": ["A, CC BY 4.0"]}]}, "section"),
        ({"title": "T", "credits": []}, "credits"),
        ({"sections": [{"entries": [{"name": "A", "licence": "CC BY"}]}]}, "entry"),
    ],
)
def test_unknown_keys_raise_instead_of_dropping_credits(spec, where):
    with pytest.raises(ValueError, match="unknown key"):
        Credits.from_dict(spec)
