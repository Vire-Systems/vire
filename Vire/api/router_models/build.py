from pydantic import BaseModel

class BuildReqResponse(BaseModel):
    success: bool
    reason: str

class CancelBuildResponse(BaseModel):
    success: bool