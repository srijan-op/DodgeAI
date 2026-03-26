"""O2C graph analytics (integrity + structural summaries)."""

from fastapi import APIRouter, HTTPException, Query

from ..o2c_analytics import build_o2c_analytics_report

router = APIRouter()


@router.get("/analytics/o2c")
def get_o2c_analytics(
    sample_limit: int = Query(
        20,
        ge=1,
        le=50,
        description="Max sample node ids per integrity check (for highlighting).",
    ),
) -> dict:
    try:
        return build_o2c_analytics_report(sample_limit=sample_limit)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=503,
            detail=f"Analytics query failed: {e}",
        ) from e
