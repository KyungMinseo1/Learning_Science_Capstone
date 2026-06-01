import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import jwt, JWTError
from ..core.config import settings
from ..core.security import verify_password, get_password_hash, create_access_token
from ..core.database import neo4j_client
from pydantic import BaseModel, EmailStr
from neo4j.exceptions import ServiceUnavailable

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")
logger = logging.getLogger(__name__)

class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str


def build_db_error_message(prefix: str, error: Exception) -> str:
    error_type = type(error).__name__
    return f"{prefix}: {error_type}: {error}"

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username = payload.get("sub")
        if not isinstance(username, str) or not username:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    try:
        with neo4j_client.get_session() as session:
            result = session.run("MATCH (u:User {username: $username}) RETURN u", username=username)
            record = result.single()
            if record is None:
                raise credentials_exception
            user_node = record["u"]
            return {"id": user_node.element_id, "username": user_node["username"], "email": user_node["email"]}
    except ServiceUnavailable as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=build_db_error_message("Database is unavailable. Start Neo4j and try again", e),
        )
    except Exception as e:
        logger.exception("Database request failed in get_current_user")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=build_db_error_message("Database request failed. Check Neo4j connection and try again", e),
        )

@router.post("/register", response_model=Token)
async def register(user_in: UserCreate):
    try:
        with neo4j_client.get_session() as session:
            username_exists = session.run(
                "MATCH (u:User {username: $username}) RETURN u LIMIT 1",
                username=user_in.username,
            ).single()
            if username_exists:
                raise HTTPException(status_code=400, detail="Username already exists")

            email_exists = session.run(
                "MATCH (u:User {email: $email}) RETURN u LIMIT 1",
                email=user_in.email,
            ).single()
            if email_exists:
                raise HTTPException(status_code=400, detail="Email already exists")

            hashed_pw = get_password_hash(user_in.password)
            session.run("""
                CREATE (u:User {
                    username: $username,
                    email: $email,
                    password: $password,
                    ai_provider: 'openai',
                    quiz_frequency: 3,
                    createdAt: datetime()
                })
            """, username=user_in.username, email=user_in.email, password=hashed_pw)
    except ServiceUnavailable:
        logger.exception("Database is unavailable during register")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable. Start Neo4j and try again.",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Database request failed during register")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=build_db_error_message("Database request failed. Check Neo4j connection and try again", e),
        )
        
    access_token = create_access_token(subject=user_in.username)
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    try:
        with neo4j_client.get_session() as session:
            result = session.run("MATCH (u:User {username: $username}) RETURN u", username=form_data.username)
            record = result.single()
            if not record or not verify_password(form_data.password, record["u"]["password"]):
                raise HTTPException(status_code=400, detail="Incorrect username or password")
    except ServiceUnavailable:
        logger.exception("Database is unavailable during login")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable. Start Neo4j and try again.",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Database request failed during login")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=build_db_error_message("Database request failed. Check Neo4j connection and try again", e),
        )
            
    access_token = create_access_token(subject=form_data.username)
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me")
async def read_users_me(current_user: dict = Depends(get_current_user)):
    return current_user
