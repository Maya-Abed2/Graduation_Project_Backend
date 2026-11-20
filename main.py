from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


from routers import history, auth, chat, lawyer


app = FastAPI(
    title="Instant Legal Consultant System",
    description="Backend API for Legal Bot System",
    version="1.0.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth.router)
app.include_router(history.router)
app.include_router(chat.router)
app.include_router(lawyer.router)

@app.get("/", tags=["Health Check"])
def read_root():
    return {"message": "Legal Bot API is running successfully!"}
