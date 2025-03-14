from fastapi import FastAPI, HTTPException, Depends, Header
from firebase_admin import auth, credentials, firestore, initialize_app
from pydantic import BaseModel
import uvicorn
from typing import Optional
import requests
import gunicorn

# Initialize Firebase
cred = credentials.Certificate("firebase-service-account.json")
initialize_app(cred)
db = firestore.client()

app = FastAPI()

# User Models
class UserSignup(BaseModel):
    email: str
    password: str
    name: str
    role: str  # student or professor
    research_interests: list[str] = []

# Research Listing Model
class ResearchListing(BaseModel):
    title: str
    description: str
    professor_id: str
    eligibility: list[str]
    tags: list[str]

# Research Listing update   
class ResearchListingUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    professor_id: Optional[str] = None
    eligibility: Optional[list[str]] = None
    tags: Optional[list[str]] = None

# Authentication Route
@app.post("/signup")
def signup(user: UserSignup):
    try:
        user_record = auth.create_user(email=user.email, password=user.password)
        user_data = {
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "research_interests": user.research_interests
        }
        db.collection("users").document(user_record.uid).set(user_data)
        return {"message": "User registered successfully", "uid": user_record.uid}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Research Listing CRUD Operations (Create, Read, Update, Delete)
@app.post("/listings")
def create_listing(listing: ResearchListing):
    try:
        data = listing.dict()
        print("Storing data in Firestore:", data)  # Debugging print statement
        doc_ref = db.collection("research_listings").add(data)[1]
        return {"message": "Research listing created", "listing_id": doc_ref.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) 

@app.get("/listings")
def get_all_listings():
    try:
        listings = db.collection("research_listings").stream()
        data = [{"id": doc.id, **doc.to_dict()} for doc in listings]
        print("Retrieved listings:", data)  # Debugging print statement
        return data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/listings/{listing_id}")
def get_listing(listing_id: str):
    doc = db.collection("research_listings").document(listing_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Listing not found")
    return {"id": doc.id, **doc.to_dict()}

@app.patch("/listings/{listing_id}")
def update_listing(listing_id: str, listing: ResearchListingUpdate):
    doc_ref = db.collection("research_listings").document(listing_id)
    
    if not doc_ref.get().exists:
        raise HTTPException(status_code=404, detail="Listing not found")

    update_data = {k: v for k, v in listing.dict(exclude_unset=True).items() if v is not None}
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No valid fields provided for update")

    doc_ref.update(update_data)
    print(f"Listing updated: {update_data}")  # Debugging print statement
    
    return {"message": "Listing updated successfully"}

@app.delete("/listings/{listing_id}")
def delete_listing(
    listing_id: str, 
    user_id: str = Header(None, convert_underscores=False)
):
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID missing in request headers")

    # Retrieve user details from Firestore
    user_doc = db.collection("users").document(user_id).get()
    
    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="User not found")

    user_data = user_doc.to_dict()
    
    # Check if the user is a professor
    if user_data.get("role") != "professor":
        raise HTTPException(status_code=403, detail="Only professors can delete listings")

    # Retrieve the research listing
    doc_ref = db.collection("research_listings").document(listing_id)
    
    if not doc_ref.get().exists:
        raise HTTPException(status_code=404, detail="Listing not found")

    # Delete the listing
    doc_ref.delete()
    print(f"Listing deleted: {listing_id}")  # Debugging print statement
    
    return {"message": "Listing deleted successfully"}


# NEW SECTION
'''Student Application Model'''

class ResearchApplication(BaseModel):
    student_id: str
    listing_id: str
    student_name: str
    student_email: str
    statement_of_purpose: str

# Apply to a Research Listing
@app.post("/applications")
def apply_to_listing(application: ResearchApplication):
    try:
        data = application.dict()
        doc_ref = db.collection("applications").add(data)[1]
        print(f"Application submitted: {data}")  # Debug log
        return {"message": "Application submitted successfully", "application_id": doc_ref.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Get all applications for a specific listing
@app.get("/applications/{listing_id}")
def get_applications_for_listing(listing_id: str):
    try:
        applications = db.collection("applications").where("listing_id", "==", listing_id).stream()
        data = [{"id": doc.id, **doc.to_dict()} for doc in applications]
        print(f"Applications for listing {listing_id}: {data}")  # Debug log
        return data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Get all applications by a specific student
@app.get("/applications/student/{student_id}")
def get_student_applications(student_id: str):
    try:
        applications = db.collection("applications").where("student_id", "==", student_id).stream()
        data = [{"id": doc.id, **doc.to_dict()} for doc in applications]
        print(f"Applications by student {student_id}: {data}")  # Debug log
        return data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Delete an application
@app.delete("/applications/{application_id}")
def delete_application(application_id: str):
    doc_ref = db.collection("applications").document(application_id)
    if not doc_ref.get().exists:
        raise HTTPException(status_code=404, detail="Application not found")
    doc_ref.delete()
    print(f"Application deleted: {application_id}")  # Debug log
    return {"message": "Application deleted successfully"}

# Running the server
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)