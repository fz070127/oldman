from typing import Annotated

from fastapi import APIRouter
from pydantic import AfterValidator, BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.core.deps import AccessToken, Auth, CurrentUser, DbSession
from app.core.response import R
from app.services.auth_service import user_profile

router = APIRouter(prefix="/auth", tags=["认证"])


def bcrypt_password(value: str) -> str:
    if len(value.encode()) > 72:
        raise ValueError("bcrypt 密码最多 72 字节")
    return value


Password = Annotated[str, Field(min_length=1, max_length=72), AfterValidator(bcrypt_password)]


class AuthBody(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel)


class LoginBody(AuthBody):
    username: str = Field(min_length=1, max_length=64, pattern=r"^[^\x00]+$")
    password: Password


class RefreshBody(AuthBody):
    refresh_token: str = Field(min_length=1, max_length=4096)


class PasswordBody(AuthBody):
    old_password: Password
    new_password: Password


@router.post("/login")
async def login(body: LoginBody, auth: Auth, db: DbSession) -> dict:
    return R.ok(await auth.login(db, body.username, body.password))


@router.post("/refresh")
async def refresh(body: RefreshBody, auth: Auth, db: DbSession) -> dict:
    return R.ok(await auth.refresh(db, body.refresh_token))


@router.post("/logout")
async def logout(user: CurrentUser, token: AccessToken, auth: Auth) -> dict:
    await auth.logout(user, token)
    return R.ok()


@router.get("/me")
async def me(user: CurrentUser) -> dict:
    return R.ok(user_profile(user))


@router.put("/password")
async def change_password(body: PasswordBody, user: CurrentUser, auth: Auth, db: DbSession) -> dict:
    await auth.change_password(db, user, body.old_password, body.new_password)
    return R.ok()
