from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi_zero.database import get_session
from fastapi_zero.models import User
from fastapi_zero.schemas import FilterPage, UserList, UserPublic, UserSchema
from fastapi_zero.security import get_current_user, get_password_hash

router = APIRouter(prefix='/users', tags=['users'])

Session = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post('/', status_code=HTTPStatus.CREATED, response_model=UserPublic)
async def create_user(user: UserSchema, session: Session):
    db_user: User | None = await session.scalar(
        select(User).where(
            (User.username == user.username) | (User.email == user.email)
        )
    )

    if db_user:
        if db_user.username == user.username:
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                detail='Username already exists',
            )
        elif db_user.email == user.email:
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT, detail='Email already exists'
            )

    db_user = User(
        username=user.username,
        email=user.email,
        password=get_password_hash(user.password),
    )
    session.add(db_user)
    await session.commit()
    await session.refresh(db_user)
    return db_user


@router.get(
    '/',
    status_code=HTTPStatus.OK,
    response_model=UserList,
)
async def get_list_users(
    session: Session,
    current_user: CurrentUser,
    filter_user: Annotated[FilterPage, Query()],
):
    users = await session.scalars(
        select(User).offset(filter_user.offset).limit(filter_user.limit)
    )

    return {'users': users}


@router.put('/{user_id}', status_code=HTTPStatus.OK, response_model=UserPublic)
async def update_user(
    user_id: int,
    user: UserSchema,
    session: Session,
    current_user: CurrentUser,
):
    user_db = current_user

    if user_db.id != user_id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail='Not enough permissions'
        )
    for field, value in user.model_dump().items():
        if hasattr(user_db, field):
            if field == 'password':
                setattr(user_db, field, get_password_hash(value))
            setattr(user_db, field, value)
    try:
        await session.commit()
        await session.refresh(user_db)
        return user_db
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail='Username or Email already exists',
        )


@router.delete('/{user_id}', status_code=HTTPStatus.OK)
async def delete_user(
    user_id: int,
    session: Session,
    current_user: CurrentUser,
):
    user_db = current_user
    if user_db.id != user_id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail='Not enough permissions'
        )

    await session.delete(user_db)
    await session.commit()

    return {'message': 'User deleted'}
