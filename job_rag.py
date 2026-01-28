import requests
import json
from sqlalchemy import create_engine, text
import pandas as pd

class JobRAG:
    def __init__(self, db_url, ollama_url="http://localhost:11434"):
        self.engine = create_engine(db_url)
        self.ollama_url = ollama_url
    
    def get_embedding(self, text):
        """Get embedding for query"""
        try:
            response = requests.post(f"{self.ollama_url}/api/embeddings", 
                                   json={"model": "nomic-embed-text:v1.5", "prompt": text},
                                   timeout=30)
            response.raise_for_status()
            return response.json()["embedding"]
        except Exception as e:
            print(f"Embedding error: {e}")
            raise Exception(f"Embedding failed: {str(e)}")
    
    def search_jobs_with_role_boost(self, query, role_keywords=None, limit=20):
        """Enhanced search that boosts results matching role keywords"""
        query_embedding = self.get_embedding(query)
        
        # If role keywords provided, also search by role field
        role_filter = ""
        params = {"query_embedding": str(query_embedding), "limit": limit}
        
        if role_keywords:
            role_conditions = []
            for i, keyword in enumerate(role_keywords[:3]):  # Limit to 3 keywords
                role_conditions.append(f"LOWER(role) LIKE :role{i} OR LOWER(title) LIKE :role{i}")
                params[f"role{i}"] = f"%{keyword.lower()}%"
            
            if role_conditions:
                role_filter = f"AND ({' OR '.join(role_conditions)})"
        
        with self.engine.connect() as conn:
            result = conn.execute(text(f"""
                SELECT id, title, role, location, experience, description, 
                       listing_url, apply_url, posted_date,
                       1 - (embedding <=> :query_embedding) as similarity
                FROM jobs 
                WHERE embedding IS NOT NULL {role_filter}
                ORDER BY embedding <=> :query_embedding
                LIMIT :limit
            """), params)
            
            return pd.DataFrame(result.fetchall(), columns=result.keys())
    
    def generate_response(self, query, jobs_df):
        """Generate response using LLM"""
        models_to_try = ["llama3.2:3b", "llama3.2", "llama3:8b", "llama3", "llama2"]
        
        context = "\n".join([
            f"Job {i+1}: {row['title']} - {row['role']} in {row['location']} "
            f"({row['experience']}) - {row['description'][:200]}..."
            for i, (_, row) in enumerate(jobs_df.iterrows())
        ])
        
        prompt = f"""Based on these job listings, answer the user's query:

Query: {query}

Job Listings:
{context}

Answer:"""
        
        for model in models_to_try:
            try:
                response = requests.post(f"{self.ollama_url}/api/generate",
                                       json={"model": model, "prompt": prompt, "stream": False, "options": {"num_predict": 100}},
                                       timeout=60)
                response.raise_for_status()
                return response.json()["response"]
            except Exception as e:
                print(f"Model {model} failed: {e}")
                continue
        
        return f"Found {len(jobs_df)} matching jobs based on your query."
    
    def search_jobs(self, query, limit=20):
        """Search jobs using vector similarity"""
        query_embedding = self.get_embedding(query)
        
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id, title, role, location, experience, description, 
                       listing_url, apply_url, posted_date,
                       1 - (embedding <=> :query_embedding) as similarity
                FROM jobs 
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> :query_embedding
                LIMIT :limit
            """), {
                "query_embedding": str(query_embedding),
                "limit": limit
            })
            
            return pd.DataFrame(result.fetchall(), columns=result.keys())
    
    def chat(self, query):
        """Main chat interface"""
        try:
            jobs = self.search_jobs(query)
            if jobs.empty:
                return {"response": "No relevant jobs found.", "jobs": []}
            
            response = self.generate_response(query, jobs)
            return {
                "response": response,
                "jobs": jobs.to_dict('records')
            }
        except Exception as e:
            return {"response": f"Error: {str(e)}", "jobs": []}
        """Enhanced chat interface for resume-based searches"""
        try:
            # Try enhanced search first
            jobs = self.search_jobs_with_role_boost(query, role_keywords)
            
            # Fallback to regular search if no results
            if jobs.empty and role_keywords:
                jobs = self.search_jobs(query)
            
            if jobs.empty:
                return {"response": "No relevant jobs found. Try broader search terms.", "jobs": []}
            
            response = self.generate_response(query, jobs)
            return {
                "response": response,
                "jobs": jobs.to_dict('records')
            }
        except Exception as e:
            return {"response": f"Error: {str(e)}", "jobs": []}

if __name__ == "__main__":
    DB_URL = "postgresql+psycopg2://postgres:dbda123@localhost:35432/postgres"
    rag = JobRAG(DB_URL)
    
    result = rag.chat("I'm looking for software engineer jobs in Bangalore")
    print("Response:", result["response"])
    print(f"\nFound {len(result['jobs'])} relevant jobs")