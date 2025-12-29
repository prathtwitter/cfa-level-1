import streamlit as st
import google.generativeai as genai
import json
import random

# --- CONFIGURATION ---
st.set_page_config(page_title="CFA Level 1 Drill", page_icon="♾️")

# --- AUTHENTICATION ---
def check_password():
    """Returns `True` if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["password"] == st.secrets["APP_PASSWORD"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store the password
        else:
            st.session_state["password_correct"] = False

    # Return True if the user has already validated the password
    if "password_correct" in st.session_state and st.session_state["password_correct"]:
        return True

    # Show input for password
    st.title("🔒 CFA Prep Access")
    st.text_input(
        "Enter Pass Key:", 
        type="password", 
        on_change=password_entered, 
        key="password"
    )
    
    if "password_correct" in st.session_state and not st.session_state["password_correct"]:
        st.error("😕 Incorrect pass key")

    return False

if not check_password():
    st.stop()  # Do not run any code below this line until authenticated

# --- APP STARTS HERE (Only runs if password is correct) ---

# --- API SETUP ---
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except FileNotFoundError:
    st.error("API Key not found. Please set GOOGLE_API_KEY in .streamlit/secrets.toml")
    st.stop()

# Set high temperature for maximum variety in questions
generation_config = genai.types.GenerationConfig(
    temperature=1.0  
)
model = genai.GenerativeModel('gemini-1.5-flash', generation_config=generation_config)

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

# --- SESSION STATE ---
if 'current_question' not in st.session_state:
    st.session_state.current_question = None
if 'answer_submitted' not in st.session_state:
    st.session_state.answer_submitted = False
if 'score' not in st.session_state:
    st.session_state.score = 0
if 'count' not in st.session_state:
    st.session_state.count = 0
if 'last_subtopic' not in st.session_state:
    st.session_state.last_subtopic = None

# --- GENERATOR LOGIC ---
def get_random_subtopic(category):
    raw_text = RAW_TOPICS[category]
    clean_text = raw_text.replace("specifically:", "").replace("specifically", "")
    subtopics = [x.strip() for x in clean_text.split(',')]
    return random.choice(subtopics)

def generate_question(category):
    subtopic = get_random_subtopic(category)
    st.session_state.last_subtopic = subtopic
    
    prompt = f"""
    You are a Senior CFA Level 1 Exam Writer. 
    Generate a SINGLE medium-to-hard multiple-choice question for CFA Level 1.
    
    PRIMARY FOCUS: {subtopic} (Inside the chapter: {category})
    
    INSTRUCTIONS:
    - Create a unique scenario-based vignette.
    - Do NOT ask a simple definition question. Require calculation or situational judgment.
    - Ensure the numbers and company names are unique and random.
    
    FORMAT: Return ONLY a raw JSON object.
    JSON STRUCTURE:
    {{
        "question": "The scenario text...",
        "options": ["A) ...", "B) ...", "C) ..."],
        "answer": "The full text of the correct option",
        "explanation": "Detailed explanation."
    }}
    """
    
    with st.spinner(f"Consulting the archives on '{subtopic}'..."):
        try:
            response = model.generate_content(prompt)
            clean_text = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_text)
        except Exception as e:
            st.error(f"Error: {e}")
            return None

# --- UI LAYOUT ---
st.title("♾️ CFA Level 1: Infinite Drill")

with st.sidebar:
    st.header("Setup")
    selected_category = st.selectbox("Select Chapter:", list(RAW_TOPICS.keys()))
    
    if st.button("Generate Question 🎲"):
        st.session_state.answer_submitted = False
        st.session_state.current_question = generate_question(selected_category)
        st.rerun()
        
    st.divider()
    st.metric("Score", f"{st.session_state.score} / {st.session_state.count}")

# --- MAIN AREA ---
if st.session_state.current_question:
    q = st.session_state.current_question
    
    st.caption(f"Chapter: {selected_category}  •  Concept: {st.session_state.last_subtopic}")
    st.subheader(q['question'])
    
    option = st.radio(
        "Choose your answer:", 
        q['options'], 
        key=f"q_{st.session_state.count}", 
        index=None,
        disabled=st.session_state.answer_submitted
    )

    if not st.session_state.answer_submitted:
        if st.button("Submit"):
            if option:
                st.session_state.answer_submitted = True
                st.session_state.count += 1
                if option == q['answer']:
                    st.session_state.score += 1
                st.rerun()
            else:
                st.warning("Please select an option.")
    else:
        if option == q['answer']:
            st.success("✅ Correct!")
        else:
            st.error(f"❌ Incorrect. Answer: {q['answer']}")
        
        st.info(f"**Explanation:** {q['explanation']}")
        
        if st.button("Next Question ➡"):
            st.session_state.answer_submitted = False
            st.session_state.current_question = generate_question(selected_category)
            st.rerun()

else:
    st.info("👈 Select a topic on the left to begin.")