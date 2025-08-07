# python -m uvicorn main:app --reload

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi import BackgroundTasks
from supabase import create_client, Client
from pydantic import BaseModel
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()
app = FastAPI()
app.mount("/estilos", StaticFiles(directory="estilos"), name="estilos")
app.mount("/paginas", StaticFiles(directory="paginas"), name="paginas")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SUPABASE_URL = "https://otaedzxedjzadltjtvzu.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im90YWVkenhlZGp6YWRsdGp0dnp1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3MzkwNTA1NDUsImV4cCI6MjA1NDYyNjU0NX0.mPZLDBWtfzcq-rEatzAlzWGrwggABZlmLP4EyL1VfZ4"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    is_admin: bool = False

class FeedbackRequest(BaseModel):
    id_booking: int
    id_property: int
    comments: str
    rating: int
    
class LoginRequest(BaseModel):
    email: str
    password: str

class ReservationRequest(BaseModel):
    property_id: int
    user_id: int
    in_time: str
    out_time: str


class PropertyStatusRequest(BaseModel):
    property_id: int
    admin_id: int
    is_active: bool

@app.get("/")
def home():
    return FileResponse("paginas/page.html")

@app.post("/register")
async def register(user: RegisterRequest):
    try:
        existing_user = supabase.table("Users").select("*").eq("email", user.email).execute()
        if existing_user.data:
            return JSONResponse(content={"message": "El usuario ya existe"}, status_code=400)

        new_user = {
            "name": user.name,
            "email": user.email,
            "password": user.password,
            "is_admin": user.is_admin
        }
        response = supabase.table("Users").insert(new_user).execute()
        if response.status_code != 201:
            return JSONResponse(content={"message": "Error al registrar el usuario"}, status_code=500)
        
        return JSONResponse(content={"message": "Usuario registrado con éxito"}, status_code=201)
    except Exception as e:
        print(f"Error al registrar el usuario: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al registrar el usuario: {str(e)}")

@app.post("/login")
async def login(user: LoginRequest):
    try:
        result = supabase.table("Users").select("*").eq("email", user.email).eq("password", user.password).execute()
        if not result.data:
            return JSONResponse(content={"message": "Correo o contraseña incorrectos"}, status_code=400)
        return JSONResponse(content={"message": "Inicio de sesión exitoso", "user_id": result.data[0]['id']}, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/property/status")
async def update_property_status(request: PropertyStatusRequest):
    try:
        admin = (
            supabase.table("Users")
            .select("is_admin")
            .eq("id", request.admin_id)
            .execute()
        )
        if not admin.data or not admin.data[0].get("is_admin"):
            return JSONResponse(content={"message": "No autorizado"}, status_code=403)

        response = (
            supabase.table("Property")
            .update({"is_active": request.is_active})
            .eq("id", request.property_id)
            .execute()
        )
        if not response.data:
            return JSONResponse(content={"message": "Propiedad no encontrada"}, status_code=404)

        status_msg = "activada" if request.is_active else "inactivada"
        return JSONResponse(content={"message": f"Propiedad {status_msg} con éxito"}, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/reserved-dates/{property_id}")
async def get_reserved_dates(property_id: int):
    try:
        response = supabase.table("Bookings").select("in_time, out_time").eq("property_id", property_id).execute()
        reserved_dates = []
        for booking in response.data:
            in_time = datetime.fromisoformat(booking["in_time"])
            out_time = datetime.fromisoformat(booking["out_time"])
            
            current_date = in_time
            while current_date <= out_time:
                reserved_dates.append(current_date.strftime("%Y-%m-%d"))
                current_date += timedelta(days=1)
        
        return JSONResponse(content={"reserved_dates": reserved_dates}, status_code=200)
    except Exception as e:
        print(f"Error al obtener las fechas reservadas: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/reserve")
async def reserve(reservation: ReservationRequest):
    try:
        user = supabase.table("Users").select("*").eq("id", reservation.user_id).execute()
        if not user.data:
            return JSONResponse(content={"message": "Usuario no encontrado"}, status_code=404)

        property_info = (
            supabase.table("Property")
            .select("is_active")
            .eq("id", reservation.property_id)
            .execute()
        )
        if not property_info.data or not property_info.data[0].get("is_active"):
            return JSONResponse(content={"message": "La propiedad no está disponible"}, status_code=400)

        try:
            in_time = datetime.strptime(reservation.in_time, "%Y-%m-%d")
            out_time = datetime.strptime(reservation.out_time, "%Y-%m-%d")
        except ValueError as e:
            return JSONResponse(content={"message": "Formato de fecha inválido. Use YYYY-MM-DD"}, status_code=400)

        if in_time < datetime.now() or out_time < datetime.now():
            return JSONResponse(content={"message": "No puedes reservar fechas pasadas"}, status_code=400)

        existing_reservation = supabase.table("Bookings").select("*").eq("property_id", reservation.property_id).gte("in_time", in_time.isoformat()).lte("out_time", out_time.isoformat()).execute()
        if existing_reservation.data:
            return JSONResponse(content={"message": "La propiedad ya está reservada en esas fechas"}, status_code=400)

        new_reservation = {
            "property_id": reservation.property_id,
            "user_id": reservation.user_id,
            "in_time": in_time.isoformat(),
            "out_time": out_time.isoformat(),
            "status": "activo"  
        }

        response = supabase.table("Bookings").insert(new_reservation).execute()
        if not response.data:
            return JSONResponse(content={"message": "Error al realizar la reserva", "details": str(response)}, status_code=500)

        return JSONResponse(content={"message": "Reserva realizada con éxito"}, status_code=201)
    except Exception as e:
        print(f"Error al realizar la reserva: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al realizar la reserva: {str(e)}")
    

@app.get("/active-reservations/{user_id}")
async def get_active_reservations(user_id: int):
    try:
        now = datetime.now().isoformat()
        reservations = supabase.table("Bookings").select("id, property_id, user_id, in_time, out_time, status").eq("user_id", user_id).gte("out_time", now).execute()

        if not reservations.data:
            return JSONResponse(content={"reservations": []}, status_code=200)

        active_reservations = []
        for reservation in reservations.data:
            property_details = (
                supabase.table("Property")
                .select("id, name")
                .eq("id", reservation["property_id"])
                .execute()
            )

            if property_details.data:
                property = property_details.data[0]
                active_reservations.append({
                    "id": reservation["id"],
                    "property_id": reservation["property_id"],
                    "property_name": property["name"],
                    "in_time": reservation["in_time"],
                    "out_time": reservation["out_time"],
                    "status": reservation["status"]
                })

        return JSONResponse(content={"reservations": active_reservations}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)
    

async def update_expired_reservations():
    try:
        now = datetime.now().isoformat()
        expired_reservations = supabase.table("Bookings").select("*").eq("status", "activo").lt("out_time", now).execute()

        for reservation in expired_reservations.data:
            supabase.table("Bookings").update({"status": "terminado"}).eq("id", reservation["id"]).execute()

    except Exception as e:
        print(f"Error al actualizar las reservas caducadas: {str(e)}")

@app.get("/update-reservations")
async def trigger_update_reservations(background_tasks: BackgroundTasks):
    background_tasks.add_task(update_expired_reservations)
    return {"message": "Actualización de reservas caducadas iniciada"}

@app.get("/past-reservations/{user_id}")
async def get_past_reservations(user_id: int):
    try:
        now = datetime.now().isoformat()
        reservations = supabase.table("Bookings").select("*").eq("user_id", user_id).lt("out_time", now).execute()

        if not reservations.data:
            return JSONResponse(content={"reservations": []}, status_code=200)

        past_reservations = []
        for reservation in reservations.data:
            property_details = (
                supabase.table("Property")
                .select("id, name")
                .eq("id", reservation["property_id"])
                .execute()
            )

            if property_details.data:
                property = property_details.data[0]
                past_reservations.append({
                    "id": reservation["id"],
                    "property_id": reservation["property_id"],
                    "property_name": property["name"],
                    "in_time": reservation["in_time"],
                    "out_time": reservation["out_time"],
                    "status": reservation["status"]
                })

        return JSONResponse(content={"reservations": past_reservations}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.post("/feedback")
async def submit_feedback(feedback: FeedbackRequest):
    try:
        response = supabase.table("Feedback").insert({
            "id_booking": feedback.id_booking,
            "id_property": feedback.id_property,
            "comments": feedback.comments,
            "rating": feedback.rating
        }).execute()

        return JSONResponse(content={"message": "Feedback guardado"}, status_code=201)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/feedback/{property_id}")
async def get_feedback(property_id: int):
    try:
        response = supabase.table("Feedback").select("*").eq("id_property", property_id).execute()
        feedback_list = response.data
        return JSONResponse(content={"feedback": feedback_list}, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))