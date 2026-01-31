import requests
import json
from sqlalchemy import create_engine, text
import pandas as pd
import re
class JobRAG:
    def __init__(self, db_url, ollama_url="http://localhost:11434"):
        self.engine = create_engine(db_url)
        self.ollama_url = ollama_url
        self.skill_patterns = {
            "spark": r"\b(py)?spark\b",
            "power bi": r"\bpower\s*bi\b",
            "machine learning": r"\b(machine\s*learning|ml)\b",
            "deep learning": r"\b(deep\s*learning|dl)\b",
            "javascript": r"\b(java\s*script|javascript|js)\b",
            "typescript": r"\b(type\s*script|typescript|ts)\b",
            "postgresql": r"\b(postgres|postgresql)\b",
            "mysql": r"\b(my\s*sql|mysql)\b",
            "c++": r"\b(c\+\+)\b",
            "c#": r"\b(c#|c sharp)\b",
        }
        self.tech_skills = {
            'python', 'java', 'javascript', 'typescript', 'c++', 'c#', 'go', 'rust', 'php', 'ruby', 'scala', 'kotlin', 'swift', 'dart', 'r', 'julia',
            'react', 'angular', 'vue', 'svelte', 'next.js', 'nuxt.js', 'node', 'express', 'nestjs', 'django', 'flask', 'fastapi', 'spring', 'asp.net', 'laravel', 'rails',
            'sql', 'mysql', 'postgresql', 'mongodb', 'redis', 'elasticsearch', 'cassandra', 'dynamodb', 'mariadb', 'sqlite', 'neo4j', 'couchbase',
            'aws', 'azure', 'gcp', 'digitalocean', 'firebase', 'devops', 'docker', 'kubernetes', 'jenkins', 'terraform', 'ansible', 'helm', 'istio', 'github actions', 'circleci',
            'machine learning', 'deep learning', 'nlp', 'computer vision', 'pytorch', 'tensorflow', 'keras', 'scikit-learn', 'pandas', 'numpy', 'matplotlib', 'seaborn', 'opencv', 'huggingface', 'llm', 'langchain', 'vector database',
            'git', 'github', 'gitlab', 'bitbucket', 'jira', 'confluence', 'agile', 'scrum', 'kanban',
            'html', 'css', 'sass', 'less', 'bootstrap', 'tailwind', 'material-ui', 'figma', 'adobe xd',
            'linux', 'unix', 'bash', 'shell', 'powershell',
            'data analysis', 'data engineering', 'data visualization', 'tableau', 'power bi', 'looker', 'metabase',
            'big data', 'hadoop', 'hive', 'hbase', 'pig', 'spark', 'pyspark', 'airflow', 'sqoop', 'kafka', 'flink', 'snowflake', 'databricks', 'presto', 'trino', 'redshift', 'bigquery', 'dbt', 'clickhouse', 'druid', 'iceberg', 'delta lake',
            'selenium', 'cypress', 'playwright', 'jest', 'mocha', 'junit', 'pytest',
            'rest api', 'graphql', 'grpc', 'microservices', 'serverless', 'web3', 'solidity', 'ethereum', 'smart contracts',
            'cybersecurity', 'penetration testing', 'iam', 'oauth', 'jwt', 'flutter', 'react native', 'ionic'
        }

    def get_embedding(self, text): 
        try:
            response = requests.post(f"{self.ollama_url}/api/embeddings", 
                                   json={"model": "nomic-embed-text:v1.5", "prompt": text},
                                   timeout=30)
            response.raise_for_status()
            return response.json()["embedding"]
        except Exception as e:
            print(f"Embedding error: {e}")
            raise Exception(f"Embedding failed: {str(e)}")

    def extract_skills(self, text):
        if not text:
            return set()

        text = text.lower()
        found_skills = set()

        for skill, pattern in self.skill_patterns.items():
            if re.search(pattern, text):
                found_skills.add(skill)

        for skill in self.tech_skills:
            if skill in found_skills:
                continue
            pattern = r"\b" + re.escape(skill) + r"\b"
            if re.search(pattern, text):
                found_skills.add(skill)

        return found_skills

    def calculate_skill_match(self, job_desc, user_skills):
        if not user_skills:
            return 0.0, set(), set()
        job_skills = self.extract_skills(job_desc)
        if not job_skills:
            return 0.0, set(), set()
        common_skills = user_skills.intersection(job_skills)
        if not common_skills:
            return 0.0, set(), job_skills

        score = len(common_skills) / len(user_skills)
        return min(score, 1.0), common_skills, job_skills

    def search_jobs(self, query, filters=None, limit=20):
        filters = filters or {}
        query_embedding = self.get_embedding(query)
        where_clauses = ["embedding IS NOT NULL"]
        params = {
            "query_embedding": str(query_embedding),
            "limit": limit * 2  
        }
        
        if filters.get('location'):
            
            loc = filters['location'].lower()
            where_clauses.append("LOWER(location) LIKE :location")
            params['location'] = f"%{loc}%"

        if filters.get('experience') and filters['experience'] != 'Any':
             exp = filters['experience'].lower()
             if 'fresher' in exp:
                 where_clauses.append("(LOWER(experience) LIKE '%fresher%' OR LOWER(experience) LIKE '%0%')")
             else:
                 where_clauses.append("LOWER(experience) LIKE :experience")
                 params['experience'] = f"%{exp}%"

        if filters.get('role_type'):
             params['role_type'] = f"%{filters['role_type'].lower()}%"
            
        where_str = " AND ".join(where_clauses)
        
        
        with self.engine.connect() as conn:
            stmt = text(f"""
                SELECT id, title, role, location, experience, description, 
                       listing_url, apply_url, posted_date,
                       1 - (embedding <=> :query_embedding) as vector_score
                FROM jobs 
                WHERE {where_str}
                ORDER BY vector_score DESC
                LIMIT :limit
            """)
            
            result = conn.execute(stmt, params)
            jobs_df = pd.DataFrame(result.fetchall(), columns=result.keys())
            
        if jobs_df.empty:
            return pd.DataFrame()

        
        user_skills = filters.get('resume_skills', set())
        
        
        if not user_skills:
            user_skills = self.extract_skills(query)

        if user_skills:
            
            skill_scores = []
            matched_skills_list = []
            
            for desc in jobs_df['description']:
                score, matched = self.calculate_skill_match(desc, user_skills)
                skill_scores.append(score)
                matched_skills_list.append(list(matched))
            
            jobs_df['skill_score'] = skill_scores
            jobs_df['matched_skills'] = matched_skills_list
            jobs_df['final_score'] = (jobs_df['vector_score'] * 0.7) + (jobs_df['skill_score'] * 0.3)
            if filters.get('role_type'):
                 jobs_df['final_score'] += 0.15
            matches_skills = jobs_df['skill_score'] > 0.5
            jobs_df.loc[matches_skills, 'final_score'] += 0.1
            has_any_skill = jobs_df['skill_score'] > 0
            jobs_df.loc[has_any_skill, 'final_score'] += 0.05

        else:
            
            jobs_df['final_score'] = jobs_df['vector_score'] * 1.2
            jobs_df['matched_skills'] = [[] for _ in range(len(jobs_df))]

        
        jobs_df['final_score'] = jobs_df['final_score'].clip(upper=1.0)

        
        jobs_df = jobs_df.sort_values('final_score', ascending=False).head(limit)
        
        return jobs_df
    
    def generate_response(self, query, jobs_df, user_skills=None):
        if not user_skills:
            user_skills = set()
            
        if jobs_df.empty:
            return "No jobs found matching your criteria."
        
        user_skills_str = ", ".join(sorted(user_skills)) if user_skills else "None provided"
        top_jobs = jobs_df.head(5)
        
        context = "\n".join([
            f"- {row['title']} at {row['location']} (Score: {row['final_score']:.2f}). Matched skills: {', '.join(row['matched_skills'])}"
            for _, row in top_jobs.iterrows()
        ])

        prompt = f"""User currently has these skills: {user_skills_str}

Analyze ONLY these top jobs:
{context}

Generate a concise response in this exact format:

**Match Analysis**
[Brief explanation matching jobs to user skills]

**Recommended Skills**
[Suggest 2-3 standard industry skills that bridge the gap between user's current skills and the target role]

**Alternative Roles**
[List 2-3 career paths strictly based on user's existing skills]

Be direct. Use bullet points."""
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": "llama3.2:3b",
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": 250,
                        "temperature": 0.3,
                        "num_threads": 4
                    }
                },
                timeout=200
            )
            response.raise_for_status()
            return response.json().get("response", "Analysis unavailable.")
        except Exception as e:
            print(f"LLM Error: {e}")
            # Fallback response
            total_jobs = len(jobs_df)
            top_job = jobs_df.iloc[0]
            top_matched = top_job.get('matched_skills', []) if not jobs_df.empty else []
            top_missing = top_job.get('missing_skills', []) if not jobs_df.empty else []
            
            response = f"Found {total_jobs} relevant positions. "
            response += f"Best match: '{top_job['title']}' with {top_job['final_score']*100:.0f}% compatibility. "
            if top_matched:
                response += f"Strong skills match: {', '.join(top_matched[:4])}. "
            if top_missing:
                 response += f"Consider developing: {', '.join(top_missing[:3])}."
            else:
                 response += "Consider developing: related technologies."

            return response

    def chat(self, query, filters=None):
        """Unified chat interface"""
        try:
            filters = filters or {}
            jobs = self.search_jobs(query, filters)
            
            if jobs.empty:
                return {"response": "No relevant jobs found matching your criteria.", "jobs": []}
            
            # Get user skills for analysis
            user_skills = filters.get('resume_skills', set())
            if not user_skills:
                user_skills = self.extract_skills(query)
            
            response = self.generate_response(query, jobs, user_skills)
            return {
                "response": response,
                "jobs": jobs.to_dict('records')
            }
        except Exception as e:
            return {"response": f"Error: {str(e)}", "jobs": []}

if __name__ == "__main__":
    DB_URL = "postgresql+psycopg2://postgres:dbda123@localhost:35432/postgres"
    rag = JobRAG(DB_URL)
    
    print("Testing Hybrid Search...")
    filters = {
        'location': 'Bangalore',
        'resume_skills': {'python', 'django', 'sql'}
    }
    result = rag.chat("Looking for python developer jobs", filters)
    print("Response:", result["response"])
    print(f"\nFound {len(result['jobs'])} jobs")