import json
import tempfile
import os
import asyncio
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from ai.ai_process import Ai_process
from ai.docling import exract_markdown
from vectordb.functions import EstimateVectorDB

# Pydantic Structure
from structure import Summary_calculation

app = FastAPI(title="AI Estimator", version="0.0.1")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create an instance of the Ai_process class
ai_process = Ai_process()
estimate_vector_db = EstimateVectorDB()

@app.get("/")
async def root():
    return {"Server": "Running"}


# Available models
@app.get("/available_models")
async def available_models():
    openai_models = ["gpt-4.1", "gpt-5-mini", "gpt-5"]
    gemini_models = ["gemini-flash-latest", "gemini-2.5-flash", "gemini-3-pro-preview"]
    playload = {
        "status": 0,
        "message": "All list fetched sucessfully",
        "data" : {
            "openai_models": openai_models,
            "gemini_models": gemini_models
        }
    }
    return playload

# Front ui
@app.get("/ui", response_class=HTMLResponse)
async def serve_ui():
    try:
        # Make sure this path points to your actual HTML file
        with open("front/front.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>Error: HTML file not found.</h1>"


# USer query
@app.post("/submit")
async def submit_input(
    details: Optional[str] = Form(None),
    files: Optional[list[UploadFile]] = File(None),
    openai_models: Optional[list[str]] = Form(None),
    gemini_models: Optional[list[str]] = Form(None),
):
    async def event_generator():
        try:
            # ========================
            # PHASE 0 — VALIDATION
            # ========================
            yield json.dumps({"status": "progress","percent":5,"message":"Validating request..."}) + "\n"

            if not openai_models and not gemini_models:
                yield json.dumps({"status":"error","message":"Select at least one model"}) + "\n"
                return

            # ========================
            # PHASE 1 — File Read
            # ========================
            yield json.dumps({"status":"progress","percent":10,"message":"Collecting files..."}) + "\n"
            
            file_list = []
            if files:
                for f in files:
                    content = await f.read()
                    file_list.append({
                        "name": f.filename,
                        "mime": f.content_type,
                        "data": content
                    })

            if not details and not file_list:
                yield json.dumps({"status":"error","message":"No input provided"}) + "\n"
                return

            # ========================
            # PHASE 2 — PARALLEL TASKS
            # Feature Extraction + Project Type Prediction
            # ========================
            yield json.dumps({"status":"progress","percent":18,"message":"Extracting features & detecting project type..."}) + "\n"

            features_task = ai_process.feature_list(user_query=details, file_list=file_list)
            project_type_task = ai_process.predict_project_type(user_query=details, file_list=file_list)

            # ⚡ Both run concurrently
            features_res, project_type_res = await asyncio.gather(features_task, project_type_task)

            if features_res.get("status") == -1:
                yield json.dumps({"status": "error","message": features_res.get("message")}) + "\n"
                return

            if project_type_res.get("status") == -1:
                yield json.dumps({"status": "error","message": project_type_res.get("message")}) + "\n"
                return

            feature_list = features_res.get("data", {}).get("features", [])
            yield json.dumps({"status":"progress","percent":28,"message":"Features extracted"}) + "\n"
            yield json.dumps({"status":"progress","percent":32,"message":"Project type detected"}) + "\n"

            # ========================
            # PHASE 3 — Fetch Similar Past Estimates
            # ========================
            yield json.dumps({"status":"progress","percent":45,"message":"Searching historical database..."} ) + "\n"

            prev_estimates_res = await estimate_vector_db.query_estimates(
                query=project_type_res.get("response", {}).get("project_summary"),
                search_string=project_type_res.get("response", {}).get("technologies_used")
            )

            if prev_estimates_res.get("status") == -1:
                yield json.dumps({"status":"error","message":prev_estimates_res.get("message")}) + "\n"
                return

            previos_estimations = prev_estimates_res.get("data", {}).get("documents", [])
            yield json.dumps({"status":"progress","percent":55,"message":"Historical context added"}) + "\n"

            # ========================
            # PHASE 4 — Brainstorm Stage
            # ========================
            yield json.dumps({"status":"progress","percent":65,"message":"Brainstorming AI-based solutions..."}) + "\n"

            await ai_process.brainstorm_stage(
                user_query=details,
                file_list=file_list,
                previos_estimations=previos_estimations,
                openai_model_list=openai_models,
                gemini_model_list=gemini_models,
                feature_list=feature_list
            )

            yield json.dumps({"status":"progress","percent":72,"message":"Brainstorming completed"}) + "\n"

            # ========================
            # PHASE 5 — Ranking Final Solutions
            # ========================
            yield json.dumps({"status":"progress","percent":80,"message":"Ranking best approaches..."}) + "\n"

            await ai_process.ranking_stage(
                file_list=file_list,
                previos_estimations=previos_estimations,
                openai_model_list=openai_models,
                gemini_model_list=gemini_models
            )

            yield json.dumps({"status":"progress","percent":87,"message":"Ranking completed"}) + "\n"

            # ========================
            # PHASE 6 — Final Stage
            # ========================
            yield json.dumps({"status":"progress","percent":94,"message":"Generating final report..."}) + "\n"

            res = await ai_process.final_stage(
                user_query=details,
                file_list=file_list,
                previos_estimations=previos_estimations
            )

            # ========================
            # COMPLETE
            # ========================
            yield json.dumps({
                "status":"complete",
                "percent":100,
                "message":"Completed Successfully",
                "data":{"response":res.get("response")}
            }) + "\n"

        except Exception as e:
            yield json.dumps({"status":"error","message":str(e)}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")


# Add Additional estiamte or save the gebeated estimate
@app.post("/add_estimate")
async def add_estimate(files: Optional[list[UploadFile]] = File(None), filename: Optional[str] = Form(None)):
    results = []
    if not files:
        return {"error": "No files provided."}
    for f in files:
        # Save to temp file
        content = await f.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(f.filename)[1]) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            # Run through docling
            markdown = await exract_markdown(tmp_path)

            # LLM call to fetch metadatass
            metadata_res = await ai_process.extract_metadata(markdown)
            meratadata_json = metadata_res.get("response")

            # Chage file name if given my the user or take f.filename
            if filename:
                f.filename = filename
            # Change the tile in json
            meratadata_json["title"] = f.filename

            # Save in db
            db_res = await estimate_vector_db.add_estimate(document_markdown=markdown, json_metadata=meratadata_json)
            if db_res.get("status") != 0:
                raise Exception(db_res.get("message"))

            results.append({"filename": f.filename, "db_response": db_res})
        except Exception as e:
            results.append({"filename": f.filename, "error": str(e)})
        finally:
            # Delete temp file
            os.remove(tmp_path)
    return {"status": 0, "message": "Estimate added successfully", "data": results}


# Get stores estimates
@app.get("/get_estimates")
async def get_estimates(limit: int = Query(10, description="Max number of estimates to return")):
    try:
        estiamte_list = await estimate_vector_db.get_list_of_estimates(limit=limit)
        if estiamte_list.get("status") != 0:
            raise Exception(estiamte_list.get("message"))
        return{"status": 0, "message": "All list fetched sucessfully", "data": estiamte_list.get("data")}
    except Exception as e:
        return{"status": -1, "message": str(e)}

# devete estimate
@app.delete("/delete_estimate/{id}")
async def delete_estimate(id: str):
    try:
        delete_res = await estimate_vector_db.delete_estimate(id=id)
        if delete_res.get("status") != 0:
            raise Exception(delete_res.get("message"))
        
        return delete_res
    except Exception as e:
        return{"status": -1, "message": str(e)}


# Summary calculate
@app.post("/calculate_summary")
async def calculate_summary( data: Summary_calculation ):
    try:

        # Extract the values
        optimestics = data.total_optimistic
        pessimistics = data.total_pessimistic
        most_likely = data.total_most_likely

        # Run the summary calculation
        pert = (optimestics+4*most_likely+pessimistics)/6

        # QA
        qa = pert*data.qa_percentage/100

        # UAT
        uat = pert*data.uat_percentage/100

        # DevOps
        devops = pert*data.devops_percentage/100

        # Critical
        critical = pert*data.critical_percentage/100

        # Total summary
        total = qa+uat+devops+critical+pert

        playlaod = {
            "status": 0,
            "message": "Summary calculated successfully",
            "data": {
                "qa": qa,
                "uat": uat,
                "devops": devops,
                "critical": critical,
                "total": total
            }
        }

        return playlaod
    except Exception as e:
        return{"status": -1, "message": str(e)}
    

# List features
@app.post("/list_features")
async def list_features( details: Optional[str] = Form(None), files: Optional[list[UploadFile]] = File(None),):
    try:
        # 1. Collect files
        file_list = []
        if files:
            for f in files:
                content = await f.read()
                file_list.append({
                    "name": f.filename,
                    "mime": f.content_type,
                    "data": content 
                })
        # List the features out
        features_res = await ai_process.feature_list(user_query=details, file_list=file_list)
        if features_res.get("status") == -1:
            return
        
        feature_list = features_res.get("data", {}).get("features", [])
        return {"status": 0,"message": "Feature list generated", "data": feature_list}
    except Exception as e:
        return{"status": -1, "message": str(e)}