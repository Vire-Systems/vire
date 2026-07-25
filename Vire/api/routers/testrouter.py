from fastapi import APIRouter

router = APIRouter()


@router.post("/test-endpoint")
async def foo():
    return "Yes"
