from pydantic import BaseModel, Field
from typing import Optional

class SandboxInfoResponse(BaseModel):
    sandbox_id: str = Field(..., alias="sandboxId")
    sandbox_name: str = Field(..., alias="sandboxName") 
    status: str
    connection_command: str = Field(..., alias="connectionCommand")
    opencode_session_id: Optional[str] = Field(None, alias="opencodeSessionId")
    opencode_server_url: Optional[str] = Field(None, alias="opencodeServerUrl")

    class Config:
        populate_by_name = True
        from_attributes = True
