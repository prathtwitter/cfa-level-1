import streamlit as st
import google.generativeai as genai
import json
import random
import time
import pandas as pd
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

# --- CONFIGURATION ---
st.set_page_config(page_title="CFA Level 1 Drill", page_icon="📚", layout="wide")

# --- AUTHENTICATION ---
def check_password():
    """Returns `True` if the user had the correct password."""
    def password_entered():
        if st.session_state["password"] == st.secrets["APP_PASSWORD"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" in st.session_state and st.session_state["password_correct"]:
        return True

    st.title("🔒 CFA Prep Access")
    st.text_input("Enter Pass Key:", type="password", on_change=password_entered, key="password")
    
    if "password_correct" in st.session_state and not st.session_state["password_correct"]:
        st.error("😕 Incorrect pass key")
    return False

if not check_password():
    st.stop()

# --- API SETUP ---
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except Exception as e:
    st.error(f"Configuration Error: {e}")
    st.stop()

generation_config = genai.types.GenerationConfig(temperature=1.0)
try:
    model = genai.GenerativeModel('gemini-2.5-flash', generation_config=generation_config)
except Exception as e:
    st.error(f"Model Error: {e}")
    st.stop()

# --- TOPIC DATA ---
RAW_TOPICS = {
    "Quantitative Methods": "Rate of Return, Time Value of Money, Statistical Measures, Probability, Portfolio Mathematics, Simulation, Estimation & Inference, Hypothesis Testing, Parametric & Non-Parametric Tests, Simple Linear Regression, Big Data Techniques",
    "Economics": "Firm & Market Structure, Understanding Business Cycles, Fiscal Policy, Monetary Policy, Introduction to Geopolitics, International Trade, Capital Flows & Foreign Exchange Markets, Exchange Rate Calculations",
    "Corporate Issuers": "Organizational Forms, Corporate Issuance, Features & Ownership, Investors & Other Stakeholders, Corporate Governance & Conflict Mechanisms, Working Capital & Liquidity, Capital Investment & Allocation, Capital Structure, Business Models",
    "Financial Statement Analysis": "Income Statement Analysis, Balance Sheet Analysis, Cash Flow Statement Analysis (I & II), Inventory, Long-Term Assets, Long-Term Liabilities & Equity, Income Taxes, Financial Reporting Quality, Financial Analysis Techniques, Financial Statement Modelling",
    "Equity Investments": "Market Organization & Structure, Security Market Indices, Market Efficiency, Equity Securities Overview, Company Analysis, Industry & Competitive Analysis, Company Analysis & Forecasting, Equity Valuation",
    "Fixed Income": "Instrument Features, Cash Flows & Types, Issuance & Trading, Markets for Corporate & Government Issuers, Bond Valuation, Yield & Spreads (Fixed & Floating), Spot, Par & Forward Curves, Interest Rate Risk, Yield-Based Duration & Convexity, Curve-Based & Empirical Risk Measures, Credit Risk, Credit Analysis, Securitization, Asset-Backed Securities, Mortgage-Backed Securities",
    "Derivatives": "Instrument & Market Features, Forward Commitments & Contingent Claims, Benefits & Risks, Arbitrage, Replication & Cost of Carry, Pricing & Valuation of Forward & Futures Contracts, Swaps, Options Pricing & Valuation, Option Replication, One-Period Binomial Model",
    "Alternative Investments": "Features, Methods & Structure, Performance & Returns, Private Capital (Equity & Debt), Real Estate & Infrastructure, Natural Resources, Hedge Funds, Introduction to Digital Assets",
    "Portfolio Management": "Risk & Return (I & II), Portfolio Construction Basics, Behavioral Biases, Portfolio Management Overview",
    "Ethics (General)": "Ethics & Trust in the Profession, Code of Ethics, Standards of Professional Conduct, Global Investment Performance Standards (GIPS)",
    "Standards & GIPS (Deep Dive)": "Professionalism, Integrity of Capital Markets, Duties to Clients, Duties to Employers, Investment Analysis, Conflicts of Interest, Responsibilities of CFA Members & Candidates, GIPS Composites, GIPS Compliance"
}

# --- SESSION STATE INITIALIZATION ---
if 'executor' not in st.session_state:
    st.session_state.executor = ThreadPoolExecutor(max_workers=1)
if 'future_batch' not in st.session_state:
    st.session_state.future_batch = None
if 'quiz_data' not in st.session_state:
    st.session_state.quiz_data = []  # List of questions
if 'user_answers' not in st.session_state:
    st.session_state.user_answers = {} 
if 'start_time' not in st.session_state:
    st.session_state.start_time = None
if 'end_time' not in st.session_state:
    st.session_state.end_time = None
if 'current_page' not in st.session_state:
    st.session_state.current_page = 0
if 'quiz_active' not in st.session_state:
    st.session_state.quiz_active = False
if 'quiz_submitted' not in st.session_state:
    st.session_state.quiz_submitted = False
if 'mode' not in st.session_state:
    st.session_state.mode = "Drill" # "Drill" or "Mock"

# --- LOGIC & GENERATION ---

def get_random_subtopic(category):
    raw_text = RAW_TOPICS[category]
    clean_text = raw_text.replace("specifically:", "").replace("specifically", "")
    subtopics = [x.strip() for x in clean_text.split(',')]
    return random.choice(subtopics)

def generate_batch(category=None, count=10, mixed_mode=False):
    """Generates a batch of questions."""
    if mixed_mode:
        selected_topics = random.choices(list(RAW_TOPICS.keys()), k=count)
        topic_str = f"A mix of CFA Level 1 topics: {', '.join(selected_topics[:3])} etc."
        focus_str = "Mixed Topics (Full Mock Exam Style)"
    else:
        topic_str = f"Category: {category}, Subtopic: {get_random_subtopic(category)}"
        focus_str = topic_str

    prompt = f"""
    You are a Senior CFA Level 1 Exam Writer. 
    Generate a JSON list of {count} UNIQUE multiple-choice questions.
    
    FOCUS: {focus_str}
    
    INSTRUCTIONS:
    - Create vignette/scenario-based questions.
    - Require calculation or judgment (No simple definitions).
    - Randomize company names and numbers.
    - IMPORTANT: Ensure exactly {count} questions.
    
    OUTPUT FORMAT: Return ONLY a raw JSON LIST of objects.
    [
        {{
            "id": "unique_id_1",
            "category": "Topic Name",
            "question": "Scenario text...",
            "options": ["A) ...", "B) ...", "C) ..."],
            "answer": "The correct option text (e.g. 'A) 10.5%')",
            "explanation": "Detailed explanation of why the answer is correct and others are wrong."
        }},
        ...
    ]
    """
    
    try:
        response = model.generate_content(prompt)
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_text)
        # Ensure category is present
        for q in data:
            if 'category' not in q:
                q['category'] = category if category else "General"
        return data
    except Exception as e:
        st.error(f"Batch Gen Error: {e}")
        return []

def start_background_fetch(is_mixed=False):
    """Used only for Mock Mode pagination."""
    if st.session_state.future_batch is None:
        st.session_state.future_batch = st.session_state.executor.submit(
            generate_batch, None, 10, is_mixed
        )

def get_background_result():
    if st.session_state.future_batch:
        try:
            result = st.session_state.future_batch.result()
            st.session_state.future_batch = None
            return result
        except Exception:
            return []
    return []

def format_duration(timedelta_obj):
    total_seconds = int(timedelta_obj.total_seconds())
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}m {seconds}s"

def reset_session():
    st.session_state.quiz_data = []
    st.session_state.user_answers = {}
    st.session_state.current_page = 0
    st.session_state.quiz_active = True
    st.session_state.quiz_submitted = False
    st.session_state.start_time = datetime.now()
    st.session_state.end_time = None
    st.session_state.future_batch = None

# --- UI LAYOUT ---
st.title("📚 CFA Level 1: Master Suite")

with st.sidebar:
    st.header("Mode Selection")
    
    # Mode Switcher
    selected_mode = st.radio("Choose Mode:", ["Topic Drill (10 Qs)", "Full Mock Quiz (90 Qs)"])
    
    if selected_mode == "Topic Drill (10 Qs)":
        st.session_state.mode = "Drill"
        selected_category = st.selectbox("Select Chapter:", list(RAW_TOPICS.keys()))
        
        st.info("Generates 10 hard questions on the selected topic. Timed.")
        
        if st.button("Start 10-Question Drill ▶"):
            reset_session()
            with st.spinner("Generating drill questions..."):
                # Drill mode: Generate all 10 at once, no background fetching needed
                batch = generate_batch(selected_category, 10, False)
                st.session_state.quiz_data = batch
            st.rerun()

    else:
        st.session_state.mode = "Mock"
        st.info("90 Questions | 135 Minutes\nCovers all topics.")
        
        if st.button("Start Full Mock ▶"):
            reset_session()
            with st.spinner("Preparing exam paper..."):
                initial_batch = generate_batch(count=10, mixed_mode=True)
                st.session_state.quiz_data = initial_batch
                start_background_fetch(is_mixed=True)
            st.rerun()

# --- MAIN CONTENT ---

if not st.session_state.quiz_active:
    st.info("👈 Select a mode and click 'Start' to begin.")
    st.stop()

# --- TIMER LOGIC ---
if st.session_state.start_time and not st.session_state.quiz_submitted:
    elapsed = datetime.now() - st.session_state.start_time
    
    if st.session_state.mode == "Mock":
        # Countdown Timer for Mock
        limit_secs = 135 * 60 
        remaining_secs = max(0, limit_secs - elapsed.total_seconds())
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Time Elapsed", str(timedelta(seconds=int(elapsed.total_seconds()))))
        c2.metric("Time Remaining", str(timedelta(seconds=int(remaining_secs))), delta_color="inverse")
        c3.metric("Questions", f"{len(st.session_state.quiz_data)} loaded")
        
        if remaining_secs <= 0:
            st.session_state.end_time = datetime.now()
            st.session_state.quiz_submitted = True
            st.rerun()
    else:
        # Count-up Timer for Drill
        st.metric("⏱ Time Elapsed", str(timedelta(seconds=int(elapsed.total_seconds()))))

# --- SUBMITTED VIEW (RESULTS) ---
if st.session_state.quiz_submitted:
    st.divider()
    st.header("🏁 Results Summary")
    
    # Calculate Stats
    questions = st.session_state.quiz_data
    answers = st.session_state.user_answers
    score = 0
    for i, q in enumerate(questions):
        if answers.get(i) == q['answer']:
            score += 1
            
    # Calculate Duration
    if st.session_state.end_time and st.session_state.start_time:
        duration = st.session_state.end_time - st.session_state.start_time
        duration_str = format_duration(duration)
    else:
        duration_str = "N/A"

    # Metrics Row
    m1, m2, m3 = st.columns(3)
    m1.metric("Final Score", f"{score} / {len(questions)}")
    m2.metric("Accuracy", f"{(score/len(questions))*100:.1f}%")
    m3.metric("Time Taken", duration_str)
    
    st.divider()
    st.subheader("📝 Detailed Review")
    st.caption("Reviewing all questions, including correct answers.")

    for i, q in enumerate(questions):
        user_ans = answers.get(i, "No Answer Selected")
        correct_ans = q['answer']
        is_correct = (user_ans == correct_ans)
        
        # Color coding the header
        header_color = "green" if is_correct else "red"
        icon = "✅" if is_correct else "❌"
        
        with st.container():
            st.markdown(f":{header_color}[**Q{i+1} {icon}:**] {q['question']}")
            
            c_left, c_right = st.columns([1, 1])
            with c_left:
                if is_correct:
                    st.success(f"**Your Answer:** {user_ans}")
                else:
                    st.error(f"**Your Answer:** {user_ans}")
            with c_right:
                st.info(f"**Correct Answer:** {correct_ans}")
            
            # Always show explanation
            st.markdown(f"**💡 Explanation:** {q['explanation']}")
            st.divider()
            
    if st.button("Start New Drill 🔄"):
        st.session_state.quiz_active = False
        st.rerun()

# --- ACTIVE QUIZ VIEW ---
else:
    # --- DRILL MODE (Single Page, 10 Qs) ---
    if st.session_state.mode == "Drill":
        with st.form("drill_form"):
            for i, q in enumerate(st.session_state.quiz_data):
                st.markdown(f"**{i+1}. {q['question']}**")
                
                # Use key to auto-save to session_state on rerun, 
                # but we need to manually map form output to st.session_state on submit
                st.radio(
                    "Select:", 
                    q['options'], 
                    key=f"q_drill_{i}", 
                    index=None,
                    label_visibility="collapsed"
                )
                st.divider()
            
            submitted = st.form_submit_button("Submit & Review 🏁")
            if submitted:
                # Harvest answers from keys
                for i in range(len(st.session_state.quiz_data)):
                    st.session_state.user_answers[i] = st.session_state.get(f"q_drill_{i}")
                
                st.session_state.end_time = datetime.now()
                st.session_state.quiz_submitted = True
                st.rerun()

    # --- MOCK MODE (Paginated, 90 Qs) ---
    else:
        questions_per_page = 10
        start_idx = st.session_state.current_page * questions_per_page
        end_idx = start_idx + questions_per_page
        
        # Auto-fetch logic for mock
        if len(st.session_state.quiz_data) < end_idx and len(st.session_state.quiz_data) < 90:
             if not st.session_state.future_batch:
                 start_background_fetch(is_mixed=True)
             new_batch = get_background_result()
             st.session_state.quiz_data.extend(new_batch)
             
        current_batch = st.session_state.quiz_data[start_idx:end_idx]
        
        with st.form(key=f"page_{st.session_state.current_page}"):
            st.subheader(f"Page {st.session_state.current_page + 1}")
            
            for i, q in enumerate(current_batch):
                abs_index = start_idx + i
                st.markdown(f"**{abs_index + 1}. {q['question']}**")
                
                existing = st.session_state.user_answers.get(abs_index, None)
                st.radio(
                    "Select Option:", 
                    q['options'], 
                    key=f"q_mock_{abs_index}",
                    index=q['options'].index(existing) if existing in q['options'] else None,
                    label_visibility="collapsed"
                )
                st.divider()
            
            c_prev, c_next = st.columns([1, 1])
            with c_prev:
                if st.session_state.current_page > 0:
                    if st.form_submit_button("⬅ Previous"):
                        # Save current page state
                        for i in range(len(current_batch)):
                            abs_index = start_idx + i
                            st.session_state.user_answers[abs_index] = st.session_state.get(f"q_mock_{abs_index}")
                        st.session_state.current_page -= 1
                        st.rerun()
            
            with c_next:
                if end_idx >= 90:
                    if st.form_submit_button("Submit Mock Exam 🏁"):
                         # Save final page
                        for i in range(len(current_batch)):
                            abs_index = start_idx + i
                            st.session_state.user_answers[abs_index] = st.session_state.get(f"q_mock_{abs_index}")
                        st.session_state.end_time = datetime.now()
                        st.session_state.quiz_submitted = True
                        st.rerun()
                else:
                    if st.form_submit_button("Next ➡"):
                        # Save current page
                        for i in range(len(current_batch)):
                            abs_index = start_idx + i
                            st.session_state.user_answers[abs_index] = st.session_state.get(f"q_mock_{abs_index}")
                        
                        # Background fetch trigger
                        if len(st.session_state.quiz_data) < 90:
                             start_background_fetch(is_mixed=True)
                        
                        st.session_state.current_page += 1
                        st.rerun()