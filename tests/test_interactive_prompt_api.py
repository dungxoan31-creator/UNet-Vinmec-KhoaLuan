import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from backend.schemas.schemas import InteractivePromptRequest, InteractivePromptResponse


def test_interactive_prompt_request_validation():
    req = InteractivePromptRequest(
        image_id="test-img-001",
        box=[100, 100, 300, 300],
        pixel_spacing_mm=0.15,
    )
    assert req.box == [100, 100, 300, 300]
    assert req.pixel_spacing_mm == 0.15

    # Invalid box: x2 <= x1
    with pytest.raises(ValidationError):
        InteractivePromptRequest(image_id="test", box=[300, 100, 100, 300])

    # Out of 512 bounds
    with pytest.raises(ValidationError):
        InteractivePromptRequest(image_id="test", box=[0, 0, 600, 500])

    with pytest.raises(ValidationError, match="Box width and height must each be at least 8 pixels"):
        InteractivePromptRequest(image_id="test", box=[100, 100, 107, 108])

    with pytest.raises(ValidationError, match="Box width and height must each be at least 8 pixels"):
        InteractivePromptRequest(image_id="test", box=[100, 100, 108, 107])

    valid_minimum_box = InteractivePromptRequest(image_id="test", box=[100, 100, 108, 108])
    assert valid_minimum_box.box == [100, 100, 108, 108]


def test_interactive_prompt_response_schema():
    res = InteractivePromptResponse(
        image_id="test-img-001",
        box=[100, 100, 300, 300],
        mask_rle={"shape": [512, 512], "counts": [262144], "first_val": 0},
        measurements={"max_diameter_mm": 25.0, "ortho_diameter_mm": 20.0},
    )
    assert res.success is True
    assert res.measurements["max_diameter_mm"] == 25.0


def test_interactive_prompt_api_fails_closed_until_validated_workflow_exists():
    from backend.app.routers import inference

    request = InteractivePromptRequest(image_id="missing-image", box=[100, 100, 200, 200])
    with pytest.raises(HTTPException) as error:
        inference.run_interactive_prompt_segmentation(request)

    assert error.value.status_code == 501
    assert error.value.detail == (
        "Interactive prompt segmentation is disabled in this RUO build because no validated model implementation is available."
    )
