from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from .db import engine, Base, get_db
from .models import User
from .schemas import SignIn, Token
from .auth import verify_password, create_access_token

Base.metadata.create_all(bind=engine)

app = FastAPI()

@app.post("/signin", response_model=Token)
def sign_in(credentials: SignIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == credentials.email).first()
    
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}
