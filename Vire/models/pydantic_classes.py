from pydantic import BaseModel

class BuildRequestModel(BaseModel):
    """
    A data model for POST /build/build_request API using pydantic's BaseModel for data validation.
    
    Attributes - 
        user_uuid,
        job_uuid,
        
    """
    job_uuid: str
    user_uuid: str
    remote_link: str
    commit_id: str
    provider: str
    remote_user: str
    remote_reponame: str
    branch: str

class BuildCancelModel(BaseModel):
    job_uuids: list[str]
    user_uuid: str
