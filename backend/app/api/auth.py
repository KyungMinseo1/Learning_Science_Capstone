from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import jwt, JWTError
from ..core.config import settings
from ..core.security import verify_password, get_password_hash, create_access_token
from ..core.database import neo4j_client
from pydantic import BaseModel, EmailStr

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    with neo4j_client.get_session() as session:
        result = session.run("MATCH (u:User {username: $username}) RETURN u", username=username)
        record = result.single()
        if record is None:
            raise credentials_exception
        user_node = record["u"]
        return {"id": user_node.element_id, "username": user_node["username"], "email": user_node["email"]}

@router.post("/register", response_model=Token)
async def register(user_in: UserCreate):
    with neo4j_client.get_session() as session:
        # Check if user exists
        exists = session.run("MATCH (u:User) WHERE u.username = $u OR u.email = $e RETURN u", 
                             u=user_in.username, e=user_in.email).single()
        if exists:
            raise HTTPException(status_code=400, detail="User already exists")
        
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
        
    access_token = create_access_token(subject=user_in.username)
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    with neo4j_client.get_session() as session:
        result = session.run("MATCH (u:User {username: $username}) RETURN u", username=form_data.username)
        record = result.single()
        if not record or not verify_password(form_data.password, record["u"]["password"]):
            raise HTTPException(status_code=400, detail="Incorrect username or password")
            
    access_token = create_access_token(subject=form_data.username)
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me")
async def read_users_me(current_user: dict = Depends(get_current_user)):
    return current_user
