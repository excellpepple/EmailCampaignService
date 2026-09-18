from pydantic import BaseModel, EmailStr


class Campaign(BaseModel):
    id: str
    title: str
    body: str
    tags: list[str]

class Contact(BaseModel):
    id: str
    email: EmailStr
    name: str | None
    subscribed: bool
    shouldDelete: bool
    tags: list[str]

class UnsubscribeRequest(BaseModel):
    email: EmailStr

class UnsubscribeResponse(BaseModel):
    token: str

class DeletionRequest(UnsubscribeRequest):
    delegated: bool = False

class DeletionResponse(UnsubscribeResponse):
    pass