import streamlit as st
import sqlite3
import docx
import re
from PyPDF2 import PdfReader
from datetime import datetime
import nltk
from nltk.stem import PorterStemmer
from nltk.tokenize import word_tokenize

# Download necessary NLTK data (run this once if you haven't already)
# nltk.download('punkt')
# nltk.download('wordnet')

# ===============================
# DATABASE SETUP
# ===============================
conn = sqlite3.connect("recruitbot.db")
c = conn.cursor()

# Create tables if not exist
c.execute('''CREATE TABLE IF NOT EXISTS candidates
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
             name TEXT, email TEXT, skills TEXT, parsed_resume TEXT)''')

c.execute('''CREATE TABLE IF NOT EXISTS interviews
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
             candidate_email TEXT, interview_date TEXT, interview_time TEXT)''')
conn.commit()

# ===============================
# HELPER FUNCTIONS
# ===============================
def parse_resume_text(text):
    """Extract candidate info from raw text and stem skills."""
    
    # Extract name, email, and a comprehensive list of potential skills
    name = re.findall(r"([A-Z][a-z]+\s[A-Z][a-z]+)", text)
    email = re.findall(r"[\w\.-]+@[\w\.-]+", text)
    
    # A more comprehensive list of tech keywords to find
    skills_keywords = re.findall(r"(Python|Java|SQL|C\+\+|Machine Learning|AI|JavaScript|React|Angular|Node\.js|HTML|CSS|Docker|Kubernetes|AWS|Azure|GCP|Cloud|Agile|Scrum|Project Management)", text, re.IGNORECASE)

    # Initialize the Porter Stemmer
    ps = PorterStemmer()
    
    # Stem each found skill and remove duplicates
    stemmed_skills = [ps.stem(skill) for skill in skills_keywords]
    unique_stemmed_skills = sorted(list(set(stemmed_skills)))

    return {
        "name": name[0] if name else "Not Found",
        "email": email[0] if email else "Not Found",
        "skills": ", ".join(unique_stemmed_skills) if unique_stemmed_skills else "Not Found",
        "parsed_resume": text[:500]  # store snippet
    }

def parse_pdf(file):
    pdf = PdfReader(file)
    text = ""
    for page in pdf.pages:
        text += page.extract_text() or ""
    return text

def parse_docx(file):
    doc = docx.Document(file)
    text = "\n".join([p.text for p in doc.paragraphs])
    return text

def add_candidate_to_db(candidate):
    c.execute("INSERT INTO candidates (name,email,skills,parsed_resume) VALUES (?,?,?,?)",
              (candidate["name"], candidate["email"], candidate["skills"], candidate["parsed_resume"]))
    conn.commit()

def schedule_interview(email, date, time):
    c.execute("INSERT INTO interviews (candidate_email, interview_date, interview_time) VALUES (?,?,?)",
              (email, date, time))
    conn.commit()

# ===============================
# FAQ MODULE
# ===============================
faq_responses = {
    "what are the roles open": "please visit https://www.iconma.com/career for open positions",
    "application status": "You can track your application status via our career portal or by contacting HR.",
    "resume shortlisted": "RecruitBot will notify you once your resume is shortlisted for the next round.",
    "skills required": "The skills vary by role, but common ones include Python, SQL, Java, and problem-solving.",
    "process timeline": "The typical hiring process takes 2–3 weeks including interviews and feedback.",
    "pay range": "Compensation is role-dependent. RecruitBot can provide details once you reach the HR round.",
    "visa": "Yes, we accept H1B and OPT candidates depending on the client’s requirements.",
    "client": "The client details will be disclosed once you progress to the next stage of hiring."
}

def get_faq_response(user_query):
    """Check if user query matches an FAQ."""
    for keyword, answer in faq_responses.items():
        if keyword in user_query.lower():
            return answer
    return None

def find_job_matches(candidate_skills, jd_text):
    """Finds matching skills between candidate and job description."""
    ps = PorterStemmer()
    
    # Extract and stem skills from the job description
    jd_skills_keywords = re.findall(r"(Python|Java|SQL|C\+\+|Machine Learning|AI||JavaScript|React|Angular|Node\.js|HTML|CSS|Docker|Kubernetes|AWS|Lambda|S3|Cloud|Agile|Scrum|Project Management)", jd_text, re.IGNORECASE)
    jd_stemmed_skills = {ps.stem(skill) for skill in jd_skills_keywords}
    
    # Get the candidate's skills, split and stem them
    candidate_list = [s.strip() for s in candidate_skills.split(",")]
    candidate_stemmed_skills = {ps.stem(skill) for skill in candidate_list}

    # Find the intersection of the two sets
    matching_skills = list(candidate_stemmed_skills.intersection(jd_stemmed_skills))
    
    return matching_skills

# ===============================
# STREAMLIT APP
# ===============================
st.set_page_config(page_title="RecruitBot", page_icon="🤖", layout="wide")

st.title("🤖 RecruitBot - ICONMA Recruiter Assistant. How can I help you?")

# Chat-style container
if "messages" not in st.session_state:
    st.session_state.messages = []
    # Add the initial greeting message
    st.session_state.messages.append({"role": "assistant", "content": "Hi there, this is ICONMA's Recruit assist. Are you looking for a job?"})

# Display previous messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# User input (Chat box)
if user_input := st.chat_input("Ask RecruitBot anything (resume, jobs, FAQs, interviews)..."):
    st.session_state.messages.append({"role": "user", "content": user_input})

    # Default response
    response = "I didn't understand that. Try uploading your resume, checking jobs, FAQs or I can schedule a call with the recruiter"

    # First check FAQs
    faq_answer = get_faq_response(user_input)
    if faq_answer:
        response = faq_answer
    else:
        # Simple rule-based fallback
        if "hello" in user_input.lower():
            response = "Hello! I’m RecruitBot 👋. I can help you parse resumes, check job matches, FAQs, and schedule intial conversations with the recruiters."
        elif "schedule" in user_input.lower():
            response = "Sure! Please provide candidate email, date, and availability in the sidebar."
        elif "job" in user_input.lower() or "jd" in user_input.lower():
            if 'jd_text' in st.session_state and st.session_state.jd_text:
                if 'candidate' in st.session_state:
                    matching_skills = find_job_matches(st.session_state.candidate['skills'], st.session_state.jd_text)
                    if matching_skills:
                        response = f"I found the following matching skills: **{', '.join(matching_skills)}**. Your profile looks like a good match! 🚀"
                    else:
                        response = "I couldn't find any matching skills between your resume and the job description. 🤔"
                else:
                    response = "Please upload your resume first to check for job matches."
            else:
                response = "Please paste the Job Description in the sidebar and I’ll compare it with your uploaded resume."
        elif "resume" in user_input.lower():
            response = "Please upload your resume (PDF or DOCX) using the sidebar."

    st.session_state.messages.append({"role": "assistant", "content": response})

    with st.chat_message("assistant"):
        st.markdown(response)

# ===============================
# SIDEBAR FEATURES
# ===============================
st.sidebar.header("📂 RecruitBot Features")

# Resume upload
resume_file = st.sidebar.file_uploader("Upload Resume (PDF/DOCX)", type=["pdf", "docx"])
if resume_file:
    if resume_file.type == "application/pdf":
        text = parse_pdf(resume_file)
    else:
        text = parse_docx(resume_file)

    candidate = parse_resume_text(text)
    add_candidate_to_db(candidate)
    st.session_state.candidate = candidate # Store candidate data in session state

    st.sidebar.success("Resume parsed and candidate data added to the database!")
    st.sidebar.write("### Candidate Profile")
    st.sidebar.json(candidate)

st.sidebar.markdown("---")

# Job Description paste area
st.sidebar.subheader("📄 Job Description")
jd_text = st.sidebar.text_area("Paste the Job Description here:", height=300, key="jd_text")

if st.sidebar.button("Check Job Match"):
    if 'candidate' in st.session_state and st.session_state.candidate:
        if jd_text:
            matching_skills = find_job_matches(st.session_state.candidate['skills'], jd_text)
            if matching_skills:
                st.sidebar.success(f"Found **{len(matching_skills)}** matching skills!")
                st.sidebar.info(f"Matching skills: {', '.join(matching_skills)}")
            else:
                st.sidebar.warning("No matching skills found.")
        else:
            st.sidebar.error("Please paste a job description to check for matches.")
    else:
        st.sidebar.error("Please upload your resume first.")