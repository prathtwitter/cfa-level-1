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

# --- API SETUP (UNCHANGED) ---
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
    st.session_state.quiz_data = []  # List of all generated questions
if 'user_answers' not in st.session_state:
    st.session_state.user_answers = {} # {question_index: selected_option}
if 'quiz_start_time' not in st.session_state:
    st.session_state.quiz_start_time = None
if 'current_page' not in st.session_state:
    st.session_state.current_page = 0
if 'quiz_active' not in st.session_state:
    st.session_state.quiz_active = False
if 'quiz_submitted' not in st.session_state:
    st.session_state.quiz_submitted = False
if 'drill_mode' not in st.session_state:
    st.session_state.drill_mode = True # True = Infinite Drill, False = Full Quiz

# --- LOGIC & GENERATION ---

def get_random_subtopic(category):
    raw_text = RAW_TOPICS[category]
    clean_text = raw_text.replace("specifically:", "").replace("specifically", "")
    subtopics = [x.strip() for x in clean_text.split(',')]
    return random.choice(subtopics)

def generate_batch(category=None, count=10, mixed_mode=False):
    """
    Generates a batch of questions.
    If mixed_mode is True, it ignores category and picks random categories for a full quiz feel.
    """
    # Prepare prompt details
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
    - IMPORTANT: If Mixed Mode, ensure variety across different chapters.
    
    OUTPUT FORMAT: Return ONLY a raw JSON LIST of objects.
    [
        {{
            "id": "unique_id_1",
            "category": "Topic Name",
            "question": "Scenario text...",
            "options": ["A) ...", "B) ...", "C) ..."],
            "answer": "The correct option text (e.g. 'A) 10.5%')",
            "explanation": "Detailed explanation."
        }},
        ...
    ]
    """
    
    try:
        response = model.generate_content(prompt)
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_text)
        # Ensure category is present for mixed batches
        for q in data:
            if 'category' not in q:
                q['category'] = category if category else "General"
        return data
    except Exception as e:
        st.error(f"Batch Gen Error: {e}")
        return []

def start_background_fetch(is_mixed=False, category=None):
    """Submits a job to the background executor."""
    if st.session_state.future_batch is None:
        st.session_state.future_batch = st.session_state.executor.submit(
            generate_batch, category, 10, is_mixed
        )

def get_background_result():
    """Retrieves result from background executor, blocking if necessary."""
    if st.session_state.future_batch:
        try:
            result = st.session_state.future_batch.result()
            st.session_state.future_batch = None # Clear future after consuming
            return result
        except Exception as e:
            st.error(f"Background Fetch Failed: {e}")
            st.session_state.future_batch = None
            return []
    return []

# --- HELPERS ---

def format_time(seconds):
    return str(timedelta(seconds=int(seconds)))

def reset_quiz():
    st.session_state.quiz_data = []
    st.session_state.user_answers = {}
    st.session_state.current_page = 0
    st.session_state.quiz_active = True
    st.session_state.quiz_submitted = False
    st.session_state.quiz_start_time = datetime.now()
    st.session_state.future_batch = None

# --- UI LAYOUT ---
st.title("📚 CFA Level 1: Master Suite")

with st.sidebar:
    st.header("Mode Selection")
    mode = st.radio("Choose Mode:", ["Infinite Drill", "Full Mock Quiz"], index=0 if st.session_state.drill_mode else 1)
    
    if mode == "Infinite Drill":
        st.session_state.drill_mode = True
        selected_category = st.selectbox("Select Chapter:", list(RAW_TOPICS.keys()))
        if st.button("Start New Drill Batch"):
            reset_quiz()
            with st.spinner("Generating first batch..."):
                initial_batch = generate_batch(selected_category, 10, False)
                st.session_state.quiz_data = initial_batch
                # Start pre-fetching next batch immediately
                start_background_fetch(is_mixed=False, category=selected_category)
            st.rerun()

    else:
        st.session_state.drill_mode = False
        st.info("90 Questions | 135 Minutes\nCovers all topics.")
        if st.button("Start Full Quiz"):
            reset_quiz()
            with st.spinner("Preparing exam paper..."):
                initial_batch = generate_batch(count=10, mixed_mode=True)
                st.session_state.quiz_data = initial_batch
                # Start pre-fetching next batch immediately
                start_background_fetch(is_mixed=True)
            st.rerun()

# --- MAIN LOGIC ---

if not st.session_state.quiz_active:
    st.info("👈 Select a mode and click Start to begin.")
    st.stop()

# --- TIMERS ---
if st.session_state.quiz_start_time and not st.session_state.quiz_submitted:
    elapsed = datetime.now() - st.session_state.quiz_start_time
    elapsed_secs = elapsed.total_seconds()
    
    limit_secs = 135 * 60 # 135 mins
    remaining_secs = max(0, limit_secs - elapsed_secs)
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Time Elapsed", format_time(elapsed_secs))
    c2.metric("Time Remaining", format_time(remaining_secs), delta_color="inverse")
    c3.metric("Progress", f"{len(st.session_state.user_answers)} / {90 if not st.session_state.drill_mode else '∞'}")

    if not st.session_state.drill_mode and remaining_secs <= 0:
        st.warning("⏰ Time is up! Auto-submitting...")
        st.session_state.quiz_submitted = True
        st.rerun()

# --- QUIZ DISPLAY OR ANALYSIS ---

if st.session_state.quiz_submitted:
    # --- ANALYSIS PAGE ---
    st.header("📊 Performance Analysis")
    
    questions = st.session_state.quiz_data
    answers = st.session_state.user_answers
    
    score = 0
    topic_stats = {} # {topic: {'correct': 0, 'total': 0}}
    
    # Calculate Scores
    for idx, q in enumerate(questions):
        user_ans = answers.get(idx, None)
        is_correct = (user_ans == q['answer'])
        if is_correct: 
            score += 1
            
        topic = q.get('category', 'General')
        if topic not in topic_stats: 
            topic_stats[topic] = {'correct': 0, 'total': 0}
        
        topic_stats[topic]['total'] += 1
        if is_correct:
            topic_stats[topic]['correct'] += 1

    # Overall Score
    percentage = (score / len(questions)) * 100 if questions else 0
    st.metric("Total Score", f"{score} / {len(questions)}", f"{percentage:.1f}%")
    
    # Topic Breakdown
    st.subheader("Topic Breakdown")
    data = []
    for topic, stats in topic_stats.items():
        acc = (stats['correct'] / stats['total']) * 100
        status = "Needs Revision 🔴" if acc < 70 else "Strong 🟢"
        data.append([topic, stats['correct'], stats['total'], f"{acc:.1f}%", status])
    
    df = pd.DataFrame(data, columns=["Topic", "Correct", "Total", "Accuracy", "Status"])
    st.dataframe(df, use_container_width=True)
    
    # Detailed Review
    with st.expander("Review Incorrect Answers"):
        for idx, q in enumerate(questions):
            user_ans = answers.get(idx, "No Answer")
            if user_ans != q['answer']:
                st.markdown(f"**Q{idx+1}: {q['question']}**")
                st.caption(f"Topic: {q.get('category')}")
                st.error(f"Your Answer: {user_ans}")
                st.success(f"Correct Answer: {q['answer']}")
                st.info(f"Explanation: {q['explanation']}")
                st.divider()

    if st.button("Start New Session"):
        st.session_state.quiz_active = False
        st.rerun()

else:
    # --- QUESTION PAGE RENDERER ---
    
    # Pagination Logic
    questions_per_page = 10
    start_idx = st.session_state.current_page * questions_per_page
    end_idx = start_idx + questions_per_page
    
    # Check if we need to load more data for the CURRENT page (Edge case)
    if len(st.session_state.quiz_data) < end_idx:
        # If we are here, it means we ran out of questions. 
        # In Drill mode, fetch immediately. In Quiz mode, cap at 90.
        if not st.session_state.drill_mode and len(st.session_state.quiz_data) >= 90:
             pass # Don't generate more than 90
        else:
             # Force fetch if future is missing
             if not st.session_state.future_batch:
                 start_background_fetch(is_mixed=not st.session_state.drill_mode)
             new_batch = get_background_result()
             st.session_state.quiz_data.extend(new_batch)
    
    current_batch = st.session_state.quiz_data[start_idx:end_idx]
    
    with st.form(key=f"page_{st.session_state.current_page}"):
        st.subheader(f"Page {st.session_state.current_page + 1}")
        
        for i, q in enumerate(current_batch):
            abs_index = start_idx + i
            st.markdown(f"**{abs_index + 1}. {q['question']}**")
            
            # Persist previous answer
            existing_ans = st.session_state.user_answers.get(abs_index, None)
            
            choice = st.radio(
                "Select Option:", 
                q['options'], 
                key=f"q_{abs_index}", 
                index=q['options'].index(existing_ans) if existing_ans in q['options'] else None,
                label_visibility="collapsed"
            )
            # Save answer to state immediately on change isn't possible in form, 
            # so we process on submit or via session state key binding logic (auto)
            if choice:
                st.session_state.user_answers[abs_index] = choice
            
            st.divider()
        
        # Navigation Buttons
        c_prev, c_next = st.columns([1, 1])
        
        with c_prev:
            if st.session_state.current_page > 0:
                if st.form_submit_button("⬅ Previous"):
                    st.session_state.current_page -= 1
                    st.rerun()
                    
        with c_next:
            # Logic for Next Button
            is_last_page = False
            if not st.session_state.drill_mode and end_idx >= 90:
                is_last_page = True
            
            if is_last_page:
                if st.form_submit_button("Submit Quiz 🏁"):
                    st.session_state.quiz_submitted = True
                    st.rerun()
            else:
                if st.form_submit_button("Next ➡"):
                    # 1. Save answers is handled by radio keys
                    # 2. Check/Consume Background Task
                    new_questions = get_background_result()
                    if new_questions:
                        st.session_state.quiz_data.extend(new_questions)
                    
                    # 3. Trigger NEXT Background Task for Page+2
                    # Only if we haven't reached 90 in quiz mode
                    if st.session_state.drill_mode or len(st.session_state.quiz_data) < 90:
                         start_background_fetch(
                             is_mixed=not st.session_state.drill_mode,
                             category=st.session_state.quiz_data[0].get('category') if st.session_state.drill_mode else None
                         )
                    
                    # 4. Advance Page
                    st.session_state.current_page += 1
                    st.rerun()