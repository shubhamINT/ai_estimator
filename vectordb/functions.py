import chromadb
import uuid


class EstimateVectorDB():
    def __init__(self):
        self.chroma_client = chromadb.PersistentClient(path = "chromadb")
        self.collection = self.chroma_client.get_or_create_collection(name = "previous_estiamtes")

    async def add_estimate(self, document_markdown, json_metadata):
        try:
            self.collection.add(
                                ids=[f"{uuid.uuid4()}"],
                                documents=[document_markdown],
                                metadatas=[json_metadata]
                                )
            return{"status": 0, "message": "Estimate added successfully"}
        except Exception as e:
            return{"status": -1, "message": str(e)}
        
    
    async def get_list_of_estimates(self, limit = None):
        try:
            self.collection.get(limit = limit)
            playload = {
                "status": 0,
                "message": "All list fetched sucessfully",
                "data": 
                {
                    "ids" : self.collection.get()["ids"],
                    "documents" : self.collection.get()["documents"],
                    "metadatas" : self.collection.get()["metadatas"]
                }
            }
            return playload
        except Exception as e:
            return{"status": -1, "message": str(e)}
        

    async def query_estimates(self, query, search_string = ""):
        try:
            self.collection.query(
                query_texts = [query],
                where_document={"$contains":search_string},
                n_results = 1
            )
            playload = {
                "status": 0,
                "message": "Query fetched sucessfully",
                "data": 
                {
                    "ids" : self.collection.get()["ids"],
                    "documents" : self.collection.get()["documents"],
                    "metadatas" : self.collection.get()["metadatas"]
                }
            }
            return playload
        except Exception as e:
            return{"status": -1, "message": str(e)}
        


    async def delete_estimate(self, id):
        try:
            self.collection.delete(ids = [id])
            return{"status": 0, "message": "Estimate deleted successfully"}
        except Exception as e:
            return{"status": -1, "message": str(e)}