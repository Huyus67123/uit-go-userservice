# main.py
from fastapi import FastAPI, Depends, HTTPException, status, Security
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

# --- 1. Import các tệp cho CSDL User ---
import crud
import models
import schemas
from database import SessionLocal, engine, get_db
from auth import verify_firebase_token, get_current_user_uid  # <-- THÊM IMPORT

# --- 2. Tạo các bảng CSDL (User, DriverProfile, Vehicle) ---
# Nó sẽ đọc các class trong 'models.py' và tạo bảng trong file .db hoặc PostgreSQL
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# --- 3. API Endpoints cho USER (with Firebase Auth) ---

@app.post("/users/", response_model=schemas.User, status_code=status.HTTP_201_CREATED)
def create_new_user(
    user: schemas.UserCreate, 
    db: Session = Depends(get_db),
    firebase_user: dict = Security(verify_firebase_token)  # <-- THÊM AUTHENTICATION
):
    """
    Tạo một user mới (với Firebase authentication).
    """
    # Verify firebase_uid matches token
    if user.firebase_uid != firebase_user.get("uid"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Firebase UID does not match authenticated user"
        )
    
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    return crud.create_user(db=db, user=user)


@app.get("/users/", response_model=List[schemas.User])
def read_all_users(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    current_user_uid: str = Security(get_current_user_uid)  # <-- THÊM AUTHENTICATION
):
    """
    Lấy danh sách tất cả user (requires authentication).
    """
    users = crud.get_users(db, skip=skip, limit=limit)
    return users


@app.get("/users/{user_id}", response_model=schemas.User)
def read_one_user(
    user_id: UUID, 
    db: Session = Depends(get_db),
    current_user_uid: str = Security(get_current_user_uid)  # <-- THÊM AUTHENTICATION
):
    """
    Lấy thông tin một user (requires authentication).
    """
    db_user = crud.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Optional: Check if user can only access their own data
    # if db_user.firebase_uid != current_user_uid:
    #     raise HTTPException(status_code=403, detail="Access denied")
    
    return db_user

@app.get("/users/?firebase_uid={firebase_uid}/", response_model=schemas.User)
def read_one_user_by_firebase_uid(
        firebase_uid: str,
        db: Session = Depends(get_db),
        current_user_uid: str = Security(get_current_user_uid)
):
    """
    Lấy thông tin một user bằng firebase uid (requires authentication).
    """
    if firebase_uid != current_user_uid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access other user's data"
        )

    db_user = crud.get_user_by_firebase_uid(db, firebase_uid=firebase_uid)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user


@app.put("/users/{user_id}", response_model=schemas.User)
def update_existing_user(
    user_id: UUID, 
    user_in: schemas.UserUpdate, 
    db: Session = Depends(get_db),
    current_user_uid: str = Security(get_current_user_uid)  # <-- THÊM AUTHENTICATION
):
    """
    Cập nhật thông tin một user (requires authentication).
    """
    db_user = crud.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Verify user can only update their own data
    if db_user.firebase_uid != current_user_uid:
        raise HTTPException(status_code=403, detail="Cannot update other user's data")
    
    db_user = crud.update_user(db, user_id=user_id, user_in=user_in)
    return db_user


@app.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_existing_user(
    user_id: UUID, 
    db: Session = Depends(get_db),
    current_user_uid: str = Security(get_current_user_uid)  # <-- THÊM AUTHENTICATION
):
    """
    Xóa một user (requires authentication).
    """
    db_user = crud.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Verify user can only delete their own account
    if db_user.firebase_uid != current_user_uid:
        raise HTTPException(status_code=403, detail="Cannot delete other user's account")
    
    crud.delete_user(db, user_id=user_id)
    return

#----- Driver Profile Endpoints -----
@app.post("/users/{user_id}/driver-profile/", response_model=schemas.DriverProfile, status_code=status.HTTP_201_CREATED)
def create_driver_profile_for_user(
    user_id: UUID, 
    profile: schemas.DriverProfileCreate, 
    db: Session = Depends(get_db),
    current_user_uid: str = Security(get_current_user_uid)  # <-- THÊM AUTHENTICATION
):
    """
    Tạo một hồ sơ tài xế cho một user đã tồn tại (requires authentication).
    """
    db_user = crud.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Verify user can only create profile for themselves
    if db_user.firebase_uid != current_user_uid:
        raise HTTPException(status_code=403, detail="Cannot create profile for other users")
    
    return crud.create_driver_profile(db=db, profile=profile, user_id=user_id)

@app.get("/users/{user_id}/driver-profile/", response_model=schemas.DriverProfile)
def read_driver_profile_by_user(
    user_id: UUID, 
    db: Session = Depends(get_db),
    current_user_uid: str = Security(get_current_user_uid)  # <-- THÊM AUTHENTICATION
):
    """
    Lấy hồ sơ tài xế bằng ID của user (requires authentication).
    """
    db_profile = crud.get_driver_profile_by_user_id(db, user_id=user_id)
    if db_profile is None:
        raise HTTPException(status_code=404, detail="Driver profile not found for this user")
    return db_profile

@app.get("/driver-profiles/{profile_id}", response_model=schemas.DriverProfile)
def read_driver_profile(profile_id: UUID, db: Session = Depends(get_db)):
    """
    Lấy hồ sơ tài xế bằng ID của chính hồ sơ đó (driver_id).
    """
    db_profile = crud.get_driver_profile(db, profile_id=profile_id)
    if db_profile is None:
        raise HTTPException(status_code=404, detail="Driver profile not found")
    return db_profile

@app.put("/driver-profiles/{profile_id}", response_model=schemas.DriverProfile)
def update_existing_driver_profile(
    profile_id: UUID, 
    profile_in: schemas.DriverProfileUpdate, 
    db: Session = Depends(get_db)
):
    """
    Cập nhật hồ sơ tài xế.
    """
    db_profile = crud.update_driver_profile(db, profile_id=profile_id, profile_in=profile_in)
    if db_profile is None:
        raise HTTPException(status_code=404, detail="Driver profile not found")
    return db_profile

@app.delete("/driver-profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_existing_driver_profile(profile_id: UUID, db: Session = Depends(get_db)):
    """
    Xóa hồ sơ tài xế.
    """
    db_profile = crud.delete_driver_profile(db, profile_id=profile_id)
    if db_profile is None:
        raise HTTPException(status_code=404, detail="Driver profile not found")
    return


# --- VEHICLE  ---

@app.post("/driver-profiles/{driver_id}/vehicles/", response_model=schemas.Vehicle, status_code=status.HTTP_201_CREATED)
def create_new_vehicle_for_driver(
    driver_id: UUID, 
    vehicle_in: schemas.VehicleCreate, 
    db: Session = Depends(get_db)
):
    """
    Tạo một xe mới cho một tài xế.
    """
    # Kiểm tra xem tài xế có tồn tại không
    db_driver = crud.get_driver_profile(db, profile_id=driver_id)
    if db_driver is None:
        raise HTTPException(status_code=404, detail="Driver not found")
        
    return crud.create_vehicle(db=db, vehicle=vehicle_in, driver_id=driver_id)

@app.get("/driver-profiles/{driver_id}/vehicles/", response_model=List[schemas.Vehicle])
def read_vehicles_for_driver(
    driver_id: UUID, 
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    """
    Lấy danh sách xe của một tài xế cụ thể.
    """
    # Kiểm tra xem tài xế có tồn tại không
    db_driver = crud.get_driver_profile(db, profile_id=driver_id)
    if db_driver is None:
        raise HTTPException(status_code=404, detail="Driver not found")
        
    vehicles = crud.get_vehicles_by_driver(db, driver_id=driver_id, skip=skip, limit=limit)
    return vehicles

@app.get("/vehicles/{vehicle_id}", response_model=schemas.Vehicle)
def read_one_vehicle(vehicle_id: UUID, db: Session = Depends(get_db)):
    """
    Lấy thông tin một xe cụ thể bằng ID của xe.
    """
    db_vehicle = crud.get_vehicle(db, vehicle_id=vehicle_id)
    if db_vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return db_vehicle

@app.put("/vehicles/{vehicle_id}", response_model=schemas.Vehicle)
def update_existing_vehicle(
    vehicle_id: UUID, 
    vehicle_in: schemas.VehicleUpdate, 
    db: Session = Depends(get_db)
):
    """
    Cập nhật thông tin một xe.
    """
    db_vehicle = crud.update_vehicle(db, vehicle_id=vehicle_id, vehicle_in=vehicle_in)
    if db_vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return db_vehicle

@app.delete("/vehicles/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_existing_vehicle(vehicle_id: UUID, db: Session = Depends(get_db)):
    """
    Xóa một xe.
    """
    db_vehicle = crud.delete_vehicle(db, vehicle_id=vehicle_id)
    if db_vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return
