import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'scrapers'))
from scrapers.jobsnet_scraper import scrape_jobsnet
from scrapers.freshersnow_scraper import scrape_freshersnow
from scrapers.freshersrecruitment_scraper import scrape_freshersrecruitment
from job_processor import JobProcessor
import threading
from concurrent.futures import ThreadPoolExecutor

DB_URL = "postgresql+psycopg2://postgres:dbda123@localhost:35432/postgres"
def run_all_scrapers():
    """Run all scrapers in parallel"""
    print("=" * 60)
    print("STARTING JOB SCRAPING PIPELINE (PARALLEL)")
    print("=" * 60)
    
    scrapers = [
        ("JobsNet", scrape_jobsnet),
        ("FreshersNow", scrape_freshersnow),
        ("FreshersRecruitment", scrape_freshersrecruitment)
    ]
    
    total_jobs = 0
    results = []
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(scraper_func): name for name, scraper_func in scrapers}
        
        for future in futures:
            name = futures[future]
            print(f"\n{'='*20} {name} {'='*20}")
            try:
                df = future.result()
                if df is not None:
                    jobs_count = len(df)
                    total_jobs += jobs_count
                    print(f"OK {name}: {jobs_count} jobs scraped")
                else:
                    print(f"FAIL {name}: Failed to scrape")
            except Exception as e:
                print(f"ERROR {name}: {e}")
    
    print(f"\n{'='*60}")
    print(f"SCRAPING COMPLETE: {total_jobs} total jobs")
    print(f"{'='*60}")
    
    return total_jobs
def process_embeddings_and_roles():
    """Process embeddings and extract roles for all jobs with parallel processing"""
    print("\n" + "=" * 60)
    print("PROCESSING EMBEDDINGS AND ROLES (PARALLEL)")
    print("=" * 60)
    try:
        processor = JobProcessor(DB_URL)
        processor.process_jobs_parallel(max_workers=8)  # Process 8 jobs at once
        print("OK Embeddings and roles processed successfully")
    except Exception as e:
        print(f"ERROR processing embeddings and roles: {e}")
def main():
    """Main pipeline execution"""
    # Step 1: Run all scrapers
    total_jobs = run_all_scrapers()
    if total_jobs > 0:
        # Step 2: Process embeddings and roles
        process_embeddings_and_roles()
        print("\n" + "=" * 60)
        print("PIPELINE COMPLETE!")
        print("Data is ready for RAG system")
        print("Run 'python job_rag.py' to test search")
        print("Run 'python web_interface.py' for web interface")
        print("=" * 60)
    else:
        print("\nNo jobs scraped. Pipeline stopped.")
if __name__ == "__main__":
    main()