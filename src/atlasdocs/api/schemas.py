from pydantic import BaseModel, Field


class CreateRelationshipRequest(BaseModel):
    relationship: str = Field(..., min_length=1)
    target: str = Field(..., min_length=1)


class RelationshipResponse(BaseModel):
    type: str
    target: str
    origin: str
    status: str


class DocumentResponse(BaseModel):
    paperless_document_id: int
    relationships: list[RelationshipResponse]
