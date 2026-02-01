import streamlit as st
import pandas as pd
from job_rag import JobRAG
import time
import PyPDF2
import docx
import requests
from user_manager import UserManager
import config

# Page configuration
st.set_page_config(
    page_title="Job Recommender System",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 800;
        text-align: center;
        background: linear-gradient(90deg, #6366f1, #8b5cf6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# Helper functions
def extract_text_from_pdf(pdf_file):
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()
        return text
    except Exception as e:
        st.error(f"Error reading PDF: {e}")
        return ""

def extract_text_from_docx(docx_file):
    try:
        doc = docx.Document(docx_file)
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text
    except Exception as e:
        st.error(f"Error reading DOCX: {e}")
        return ""

# Initialize State
if 'rag' not in st.session_state:
    st.session_state.rag = JobRAG()
    st.session_state.user_manager = UserManager()

if 'search_history' not in st.session_state:
    st.session_state.search_history = []

if 'user' not in st.session_state:
    st.session_state.user = None

# Authentication Section
from google_auth import init_google_auth
auth = init_google_auth()

if not st.session_state.user:
    # Show login page
    st.markdown('<h1 class="main-header">🎯 Job Recommender System</h1>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### Welcome! Please sign in to continue")
        
        if auth:
            auth_url = auth.get_auth_url()
            st.markdown(f'<div style="text-align: center;"><a href="{auth_url}" target="_self" style="display: inline-block; padding: 12px 24px; background: #4285f4; color: white; text-decoration: none; border-radius: 6px; font-weight: 500;">🔐 Sign in with Google</a></div>', unsafe_allow_html=True)
        else:
            st.error("Google authentication not configured")
        
        # Handle OAuth callback
        query_params = st.query_params
        if 'code' in query_params and auth:
            with st.spinner("Signing you in..."):
                user_data, error = auth.authenticate_user(query_params['code'])
                
                if user_data:
                    user_id = st.session_state.user_manager.create_user(
                        google_id=user_data['google_id'],
                        username=user_data['name'],
                        email=user_data['email']
                    )
                    
                    st.session_state.user = {
                        'id': user_id,
                        'name': user_data['name'],
                        'email': user_data['email'],
                        'picture': user_data.get('picture')
                    }
                    
                    st.success(f"Welcome {user_data['name']}!")
                    st.rerun()
                else:
                    st.error(f"Sign in failed: {error}")
    
    st.stop()

# User is logged in - show main app
# Sidebar
with st.sidebar:
    # User profile section
    st.markdown("### 👤 Profile")
    col1, col2 = st.columns([1, 3])
    with col1:
        st.write("👤")
    with col2:
        st.write(f"**{st.session_state.user['name']}**")
        st.caption(st.session_state.user['email'])
    
    if st.button("🚪 Sign Out"):
        st.session_state.user = None
        st.rerun()
    
    st.divider()
    
    # Resume Upload
    st.subheader("📄 Resume Upload")
    uploaded_file = st.file_uploader("Upload Resume", type=['pdf', 'docx', 'txt'])
    
    # Extract skills if resume uploaded, or fetch from DB for returning users
    resume_skills = set()
    
    # Check DB for existing skills first
    user_prefs = st.session_state.user_manager.get_user_preferences(st.session_state.user['id'])
    if user_prefs and user_prefs[2]: # skills are the 3rd element (index 2)
        resume_skills = set(user_prefs[2])

    if uploaded_file:
        if uploaded_file.type == "application/pdf":
            resume_text = extract_text_from_pdf(uploaded_file)
        elif "word" in uploaded_file.type:
            resume_text = extract_text_from_docx(uploaded_file)
        else:
            resume_text = str(uploaded_file.read(), "utf-8")
        
        with st.spinner("Analyzing Resume..."):
            resume_skills = st.session_state.rag.extract_skills(resume_text)
            
            # Save resume to database
            st.session_state.user_manager.save_user_resume(
                st.session_state.user['id'],
                uploaded_file.name,
                uploaded_file.getvalue(),  # Get file as bytes for BLOB
                list(resume_skills)
            )
        
        st.success(f"Resume Saved: {len(resume_skills)} skills found")
        
        with st.expander("Detected Skills"):
            st.write(", ".join(resume_skills))
    
    st.divider()
    
    # DB Status
    try:
        with st.session_state.rag.engine.connect() as conn:
            st.success("Database: Connected")
        requests.get("http://localhost:11434", timeout=1)
        st.success("Ollama: Online")
    except Exception:
        st.error("System Status: Connection Issues")

# Main Content
st.markdown('<h1 class="main-header">🎯 Job Recommender System</h1>', unsafe_allow_html=True)

# Navigation tabs
tab1, tab2, tab3 = st.tabs(["🔍 Search Jobs", "💾 Saved Jobs", "📊 Dashboard"])

with tab1:
    # Unified Search Form
    with st.container():
        st.markdown("### 🔍 Search Criteria")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            role_val = st.text_input("Job Role", placeholder="Data Scientist, Java Dev...")
        with col2:
            loc_val = st.text_input("Location", placeholder="Bangalore, Mumbai...")
        with col3:
            exp_val = st.selectbox("Experience", ["Any", "Fresher (0-1y)", "Junior (1-3y)", "Mid (3-5y)", "Senior (5y+)"])

        # Skills Input (Pre-filled from resume)
        default_skills = ", ".join(resume_skills) if resume_skills else ""
        skills_input = st.text_area("Skills (Comma Separated)", value=default_skills, placeholder="python, sql, aws...")

        if st.button("🚀 Find Matching Jobs", type="primary"):
            # Save user preferences for notifications
            preferences = {
                'role_name': role_val,
                'location': loc_val,
                'experience_level': exp_val if exp_val != 'Any' else None,
                'skills': list(resume_skills) if resume_skills else [],
                'email_notifications': True
            }
            st.session_state.user_manager.save_user_preferences(st.session_state.user['id'], preferences)
            
            # Process inputs
            final_skills = {s.strip() for s in skills_input.split(',')} if skills_input else set()
            
            filters = {
                'location': loc_val,
                'experience': exp_val,
                'role_type': role_val,
                'resume_skills': final_skills
            }
            # Build Query
            parts = []
            if role_val: parts.append(f"{role_val} jobs")
            if loc_val: parts.append(f"in {loc_val}")
            if final_skills: parts.append(f"using {', '.join(list(final_skills)[:5])}")
            
            query_text = " ".join(parts) if parts else "Software Engineering jobs"
            
            with st.spinner(f"Searching for: {query_text}..."):
                result = st.session_state.rag.search_jobs(query_text, filters)
                st.session_state.last_results = result
                st.session_state.last_search_skills = final_skills
                st.session_state.last_query = query_text
                st.session_state.ai_analysis = None # Reset cache for new search
                
    # AI Analysis Section - show before results
    if 'last_results' in st.session_state and not st.session_state.last_results.empty:
        jobs_df = st.session_state.last_results
        
        st.divider()
        final_skills = st.session_state.get('last_search_skills', set())
        query_text = st.session_state.get('last_query', 'job search')
        
        # Only run AI if not already cached
        if st.session_state.get('ai_analysis') is None:
            with st.spinner("AI is analyzing your job matches..."):
                st.session_state.ai_analysis = st.session_state.rag.generate_response(query_text, jobs_df, final_skills)
        
        st.info(f"**🤖 AI Analysis:**\n\n{st.session_state.ai_analysis}")
        
        st.divider()
                
    # Results Display
    if 'last_results' in st.session_state and not st.session_state.last_results.empty:
        jobs_df = st.session_state.last_results
        
        st.markdown(f"### 📊 Results Found: {len(jobs_df)}")
        
        for i, (_, job) in enumerate(jobs_df.iterrows()):
            score = job.get('final_score', 0) * 100
            
            # Determine color/label based on score
            if score >= 75:
                score_label = "Excellent Match"
                delta_color = "normal" 
            elif score >= 55:
                score_label = "Good Match"
                delta_color = "off"
            elif score >= 35:
                score_label = "Fair Match"
                delta_color = "off"
            else:
                score_label = "Potential Match"
                delta_color = "inverse"
            
            with st.container():
                c1, c2 = st.columns([3, 1])
                
                with c1:
                    st.subheader(f"{i+1}. {job['title']}")
                    st.caption(f"🏢 {job.get('role', 'N/A')} •📍 {job['location']} • 💼 {job['experience']}")
                    
                with c2:
                    st.metric("Match Score", f"{score:.0f}%", score_label, delta_color=delta_color)
                
                # Match Reasoning
                if job.get('matched_skills'):
                    st.markdown("**✅ Matched Skills:**")
                    st.caption(", ".join(job['matched_skills']))
                
                # Description Expander
                with st.expander("Show Job Description"):
                    st.markdown(job['description'])
                
                # Action Buttons
                col1, col2, col3 = st.columns([1, 1, 3])
                with col1:
                    if job.get('apply_url'):
                        st.link_button("👉 Apply Now", job['apply_url'], use_container_width=True)
                with col2:
                    if st.button("💾 Save", key=f"save_{job['id']}", use_container_width=True):
                        st.session_state.user_manager.save_job(
                            st.session_state.user['id'], 
                            job['id'],
                            final_score=job.get('final_score', 0.0),
                            matched_skills=job.get('matched_skills', [])
                        )
                        st.success("Job saved!")
                
                st.divider()
    elif 'last_results' in st.session_state:
        st.warning("No jobs found matching your criteria. Try relaxing your filters.")

with tab2:
    st.markdown("### 💾 Your Saved Jobs")
    
    saved_jobs = st.session_state.user_manager.get_saved_jobs(st.session_state.user['id'])
    
    col1, col2 = st.columns([3, 1])
    with col1:
        if not saved_jobs.empty:
            st.info(f"💡 You have {len(saved_jobs)} saved jobs. You can send up to 3 as a test email.")
        else:
            st.warning("⚠️ No saved jobs yet. Save some jobs first to send a test email!")
            
    with col2:
        if st.button("📧 Send Test Email", type="secondary", use_container_width=True):
            if saved_jobs.empty:
                st.error("Please save at least one job first!")
            else:
                with st.spinner("Sending test email..."):
                    # Get user preferences
                    prefs = st.session_state.user_manager.get_user_preferences(st.session_state.user['id'])
                    
                    # Create a user dictionary for the email template
                    user_info = {
                        'username': st.session_state.user['name'],
                        'email': st.session_state.user['email'],
                        'location': prefs[0] if prefs else None,
                        'role_name': prefs[1] if prefs else None,
                        'skills': prefs[2] if prefs else []
                    }
                    
                    # Send top 3 saved jobs (1, 2, or 3)
                    top_jobs = saved_jobs.head(3)
                    test_subject = f"🧪 [TEST EMAIL] Your Top {len(top_jobs)} Saved Jobs"
                    success = st.session_state.user_manager._send_job_notification_email(
                        user_info, 
                        top_jobs.to_dict('records'),
                        subject=test_subject
                    )
                    
                    if success:
                        st.success(f"Test email sent with {len(top_jobs)} job(s)!")
                    else:
                        st.error("Failed to send email. Check SMTP settings.")
    
    st.divider()

    if not saved_jobs.empty:
        for i, job in saved_jobs.iterrows():
            score = job.get('final_score', 0) * 100
            
            with st.container():
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.subheader(f"{job['title']}")
                    st.caption(f"🏢 {job.get('role', 'N/A')} • 📍 {job['location']} • 💼 {job['experience']}")
                with c2:
                    st.metric("Match Score", f"{score:.0f}%")
                
                # Match Reasoning
                if job.get('matched_skills'):
                    st.markdown("**✅ Matched Skills:**")
                    st.caption(", ".join(job['matched_skills']))

                with st.expander("Show Description"):
                    st.markdown(job['description'])
                
                if job.get('apply_url'):
                    st.link_button("👉 Apply Now", job['apply_url'])
                
                st.divider()
    else:
        st.info("No saved jobs yet. Start searching and save jobs you're interested in!")

with tab3:
    st.markdown("### 📊 Your Job Search Dashboard")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        saved_count = len(st.session_state.user_manager.get_saved_jobs(st.session_state.user['id']))
        st.metric("Saved Jobs", saved_count)
    
    with col2:
        # Scheduler Control
        current_status = st.session_state.user_manager.notification_running
        status_text = "Active" if current_status else "Inactive"
        st.metric("Notifications", status_text)
        
        # Profile Completion Check
        is_profile_complete = len(resume_skills) > 0
        
        if is_profile_complete:
            if st.toggle("Enable Daily Emails", value=current_status):
                if not current_status:
                    st.session_state.user_manager.start_notification_scheduler()
                    st.rerun()
            else:
                if current_status:
                    st.session_state.user_manager.stop_notification_scheduler()
                    st.rerun()
        else:
            st.toggle("Enable Daily Emails", value=False, disabled=True, help="Upload resume to enable")
            st.warning("⚠️ Please complete your profile (upload resume) to enable daily notifications.")
    
    with col3:
        completion = "85%" if resume_skills else "20%"
        st.metric("Profile Completion", completion)
    
    st.info("💡 Tip: Upload your resume and search for jobs to receive personalized email notifications!")