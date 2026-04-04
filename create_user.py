from app.db import SessionLocal
from app.models import User
from app.auth import get_password_hash

db = SessionLocal()

# Create test user
user = User(
    email="utopia@example.com",
    hashed_password=get_password_hash("password123")
)

db.add(user)
db.commit()
db.close()

print("✓ User created successfully!")
print("Email: utopia@example.com")
print("Password: password123")
