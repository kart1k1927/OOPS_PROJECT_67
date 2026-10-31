from fastapi import APIRouter

#ADD your own endpoints here, this is just a template for auth endpoints

#v1 as prefix, for scalability, but it doesnt lowkey matter
router = APIRouter(prefix="/api/v1", tags=["auth"])

#for logging
@router.post("/login")
def login():
    return {"message": "Login endpoint"}

@router.post("/register")
def register():
    return {"message": "Register endpoint"}

@router.post("/logout")
def logout():
    return {"message": "Logout endpoint"}

#pwd 
@router.post("/reset-password")
def reset_password():
    return {"message": "Reset password endpoint"}

@router.post("/change-password")
def change_password():
    return {"message": "Change password endpoint"}

#emails
@router.post("/verify-email")
def verify_email():
    return {"message": "Verify email endpoint"}

@router.post("/resend-verification-email")
def resend_verification_email():
    return {"message": "Resend verification email endpoint"}

