import uuid

from fastapi_users import schemas


class UserRead(schemas.BaseUser[uuid.UUID]):
    role: str
    username: str | None = None


class UserCreate(schemas.BaseUserCreate):
    role: str = "lawyer"
    username: str | None = None


class UserUpdate(schemas.BaseUserUpdate):
    role: str | None = None
    username: str | None = None
