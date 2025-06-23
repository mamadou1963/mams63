from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime, date
from enum import Enum


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# Enums
class InvoiceStatus(str, Enum):
    DRAFT = "brouillon"
    SENT = "envoyée"
    PAID = "payée"
    OVERDUE = "en_retard"


# Models
class Client(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    nom: str
    email: Optional[str] = None
    telephone: Optional[str] = None
    adresse: Optional[str] = None
    ville: Optional[str] = None
    code_postal: Optional[str] = None
    pays: Optional[str] = "France"
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ClientCreate(BaseModel):
    nom: str
    email: Optional[str] = None
    telephone: Optional[str] = None
    adresse: Optional[str] = None
    ville: Optional[str] = None
    code_postal: Optional[str] = None
    pays: Optional[str] = "France"

class ClientUpdate(BaseModel):
    nom: Optional[str] = None
    email: Optional[str] = None
    telephone: Optional[str] = None
    adresse: Optional[str] = None
    ville: Optional[str] = None
    code_postal: Optional[str] = None
    pays: Optional[str] = None

class InvoiceItem(BaseModel):
    description: str
    quantite: float
    prix_unitaire: float
    total: float = 0.0

class Invoice(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    numero: str
    date_creation: date = Field(default_factory=date.today)
    date_echeance: Optional[date] = None
    client_id: str
    client_nom: str = ""
    items: List[InvoiceItem] = []
    sous_total: float = 0.0
    taux_tva: float = 20.0
    montant_tva: float = 0.0
    total: float = 0.0
    statut: InvoiceStatus = InvoiceStatus.DRAFT
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class InvoiceCreate(BaseModel):
    client_id: str
    date_echeance: Optional[date] = None
    items: List[InvoiceItem]
    taux_tva: float = 20.0
    notes: Optional[str] = None

class InvoiceUpdate(BaseModel):
    client_id: Optional[str] = None
    date_echeance: Optional[date] = None
    items: Optional[List[InvoiceItem]] = None
    taux_tva: Optional[float] = None
    statut: Optional[InvoiceStatus] = None
    notes: Optional[str] = None


# Helper functions
async def get_next_invoice_number():
    """Generate the next invoice number"""
    last_invoice = await db.invoices.find_one(sort=[("numero", -1)])
    if last_invoice:
        try:
            last_number = int(last_invoice["numero"].replace("FAC-", ""))
            return f"FAC-{last_number + 1:06d}"
        except:
            pass
    return "FAC-000001"

def calculate_invoice_totals(items: List[InvoiceItem], taux_tva: float):
    """Calculate invoice totals"""
    sous_total = sum(item.quantite * item.prix_unitaire for item in items)
    montant_tva = sous_total * (taux_tva / 100)
    total = sous_total + montant_tva
    
    # Update item totals
    for item in items:
        item.total = item.quantite * item.prix_unitaire
    
    return sous_total, montant_tva, total

async def get_client_name(client_id: str):
    """Get client name by ID"""
    client = await db.clients.find_one({"id": client_id})
    return client["nom"] if client else "Client inconnu"


# Client routes
@api_router.post("/clients", response_model=Client)
async def create_client(client: ClientCreate):
    client_dict = client.dict()
    client_obj = Client(**client_dict)
    await db.clients.insert_one(client_obj.dict())
    return client_obj

@api_router.get("/clients", response_model=List[Client])
async def get_clients():
    clients = await db.clients.find().sort("nom", 1).to_list(1000)
    return [Client(**client) for client in clients]

@api_router.get("/clients/{client_id}", response_model=Client)
async def get_client(client_id: str):
    client = await db.clients.find_one({"id": client_id})
    if not client:
        raise HTTPException(status_code=404, detail="Client non trouvé")
    return Client(**client)

@api_router.put("/clients/{client_id}", response_model=Client)
async def update_client(client_id: str, client_update: ClientUpdate):
    update_data = {k: v for k, v in client_update.dict().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="Aucune donnée à mettre à jour")
    
    result = await db.clients.update_one({"id": client_id}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Client non trouvé")
    
    updated_client = await db.clients.find_one({"id": client_id})
    return Client(**updated_client)

@api_router.delete("/clients/{client_id}")
async def delete_client(client_id: str):
    # Check if client has invoices
    invoice_count = await db.invoices.count_documents({"client_id": client_id})
    if invoice_count > 0:
        raise HTTPException(status_code=400, detail="Impossible de supprimer un client avec des factures")
    
    result = await db.clients.delete_one({"id": client_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Client non trouvé")
    return {"message": "Client supprimé avec succès"}


# Invoice routes
@api_router.post("/invoices", response_model=Invoice)
async def create_invoice(invoice: InvoiceCreate):
    invoice_dict = invoice.dict()
    
    # Generate invoice number
    invoice_dict["numero"] = await get_next_invoice_number()
    
    # Get client name
    invoice_dict["client_nom"] = await get_client_name(invoice.client_id)
    
    # Calculate totals
    sous_total, montant_tva, total = calculate_invoice_totals(invoice.items, invoice.taux_tva)
    invoice_dict["sous_total"] = sous_total
    invoice_dict["montant_tva"] = montant_tva
    invoice_dict["total"] = total
    
    # Convert date objects to datetime for MongoDB compatibility
    if invoice_dict.get("date_echeance") and isinstance(invoice_dict["date_echeance"], date):
        invoice_dict["date_echeance"] = datetime.combine(invoice_dict["date_echeance"], datetime.min.time())
    
    invoice_obj = Invoice(**invoice_dict)
    # Convert to dict and handle date objects for MongoDB
    invoice_data = invoice_obj.dict()
    if isinstance(invoice_data.get("date_echeance"), date):
        invoice_data["date_echeance"] = datetime.combine(invoice_data["date_echeance"], datetime.min.time())
    if isinstance(invoice_data.get("date_creation"), date):
        invoice_data["date_creation"] = datetime.combine(invoice_data["date_creation"], datetime.min.time())
    
    await db.invoices.insert_one(invoice_data)
    return invoice_obj

@api_router.get("/invoices", response_model=List[Invoice])
async def get_invoices():
    invoices = await db.invoices.find().sort("created_at", -1).to_list(1000)
    return [Invoice(**invoice) for invoice in invoices]

@api_router.get("/invoices/{invoice_id}", response_model=Invoice)
async def get_invoice(invoice_id: str):
    invoice = await db.invoices.find_one({"id": invoice_id})
    if not invoice:
        raise HTTPException(status_code=404, detail="Facture non trouvée")
    return Invoice(**invoice)

@api_router.put("/invoices/{invoice_id}", response_model=Invoice)
async def update_invoice(invoice_id: str, invoice_update: InvoiceUpdate):
    update_data = {k: v for k, v in invoice_update.dict().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="Aucune donnée à mettre à jour")
    
    # Convert date objects to datetime for MongoDB compatibility
    if update_data.get("date_echeance") and isinstance(update_data["date_echeance"], date):
        update_data["date_echeance"] = datetime.combine(update_data["date_echeance"], datetime.min.time())
    
    # If items are updated, recalculate totals
    if "items" in update_data:
        taux_tva = update_data.get("taux_tva", 20.0)
        current_invoice = await db.invoices.find_one({"id": invoice_id})
        if current_invoice and "taux_tva" not in update_data:
            taux_tva = current_invoice.get("taux_tva", 20.0)
        
        sous_total, montant_tva, total = calculate_invoice_totals(update_data["items"], taux_tva)
        update_data["sous_total"] = sous_total
        update_data["montant_tva"] = montant_tva
        update_data["total"] = total
    
    # Update client name if client_id changed
    if "client_id" in update_data:
        update_data["client_nom"] = await get_client_name(update_data["client_id"])
    
    update_data["updated_at"] = datetime.utcnow()
    
    result = await db.invoices.update_one({"id": invoice_id}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Facture non trouvée")
    
    updated_invoice = await db.invoices.find_one({"id": invoice_id})
    return Invoice(**updated_invoice)

@api_router.delete("/invoices/{invoice_id}")
async def delete_invoice(invoice_id: str):
    result = await db.invoices.delete_one({"id": invoice_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Facture non trouvée")
    return {"message": "Facture supprimée avec succès"}

@api_router.get("/dashboard/stats")
async def get_dashboard_stats():
    """Get dashboard statistics"""
    total_invoices = await db.invoices.count_documents({})
    total_clients = await db.clients.count_documents({})
    
    # Calculate totals by status
    pipeline = [
        {"$group": {
            "_id": "$statut",
            "count": {"$sum": 1},
            "total_amount": {"$sum": "$total"}
        }}
    ]
    
    status_stats = await db.invoices.aggregate(pipeline).to_list(100)
    
    # Calculate total revenue
    total_revenue = await db.invoices.aggregate([
        {"$match": {"statut": "payée"}},
        {"$group": {"_id": None, "total": {"$sum": "$total"}}}
    ]).to_list(1)
    
    revenue = total_revenue[0]["total"] if total_revenue else 0.0
    
    return {
        "total_invoices": total_invoices,
        "total_clients": total_clients,
        "total_revenue": revenue,
        "status_breakdown": status_stats
    }


# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()