import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from io import StringIO
import datetime
import time
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from PIL import Image
import ast
import json
import os

firebase_secrets = st.secrets["firebase"]

# Convert secrets to dict
cred_dict = {
    "type": firebase_secrets["type"],
    "project_id": firebase_secrets["project_id"],
    "private_key_id": firebase_secrets["private_key_id"],
    "private_key": firebase_secrets["private_key"].replace("\\n", "\n"),  # Fix multi-line key
    "client_email": firebase_secrets["client_email"],
    "client_id": firebase_secrets["client_id"],
    "auth_uri": firebase_secrets["auth_uri"],
    "token_uri": firebase_secrets["token_uri"],
    "auth_provider_x509_cert_url": firebase_secrets["auth_provider_x509_cert_url"],
    "client_x509_cert_url": firebase_secrets["client_x509_cert_url"],
    "universe_domain": firebase_secrets["universe_domain"],
}
cred = credentials.Certificate(json.loads(json.dumps(cred_dict)))
# Initialize Firebase (only if not already initialized)
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

# Get Firestore client
db = firestore.client()

# --- CONFIG ---
GITHUB = "https://raw.githubusercontent.com/abhipsabasu/GeoDiv_HS/main/"

response = requests.get(GITHUB + 'China.csv')
df = pd.read_csv(StringIO(response.text))

IMAGE_LIST =  list(df['new_image_path'])# filenames in the GitHub repo
QUESTIONS = {}
ENTITY_LIST = list(df['concept'])

q1 = "Rate this image on the level of *affluence*. The options are a scale of 1 to 5, where each score is defined within the options."
q2 = "Rate this image on the *general condition* of the primary entity. The options are a scale of 1 to 5, where each score is defined within the options."
q3 = "Rate this image on the *cultural localization* of the primary entity with respect to *your* country. The options are a scale of 1 to 5, where each score is defined within the options."

a1 = ["1 – **Impoverished**:	Severe visible decay; disrepair, dirt, broken infrastructure, minimal economic activity.",
      "2 – **Low Affluence**:	Basic but aging structures; modest upkeep; informal or patchy development visible.",
      "3 – **Moderate Affluence**:	Clean and functional spaces; organized but simple environments; middle-income indicators.",
      "4 – **High Affluence**:	Well-maintained, vibrant areas; professional storefronts; signs of prosperity and civic care."
      "5 – **Very High Affluence (Luxury)**:	Sleek, modern, or designer elements; upscale brands; spotless, elite environments."]

a2 = ["1 – **Severely Damaged**:	Major disrepair, heavy rust, breakage, or abandonment visible.",
      "2 – **Poor Condition**:	Noticeable wear, aging, dirt, minor missing parts, but still recognizable.",
      "3 – **Moderately Maintained**:	Functional, intact, but with small flaws like scuffs or fading.",
      "4 – **Well Maintained**:	Clean, organized, minor cosmetic wear only, no functional damage.",
      "5 – **Excellent Condition**:	Polished, pristine, flawless; appears new or recently serviced."]

a3 = ["1 – **Highly globalized**: The subject displays no distinct cultural markers and appears universally generic or global in design.",
      "2 – **Slightly localized**: The subject shows minor cultural hints, but these are subtle and easily overshadowed by global aesthetics.",
      "3 – **Moderately localized**: The subject blends global and cultural elements, suggesting a recognizable yet not dominant cultural identity.",
      "4 – **Strongly localized**: The subject prominently features distinctive cultural elements that are clearly tied to the local context.",
      "5 – **Deeply rooted in culture**: The subject embodies cultural uniqueness through highly characteristic and tradition-rich visual cues."]

for idx, row in df.iterrows():
    QUESTIONS[row['new_image_path']] = [{"question": '**'+q1+'**', 
                                    "options": a1},
                                  {"question": '**'+q2+'**', 
                                    "options": a2},
                                  {"question": '**'+q3+'**', 
                                    "options": a3}]
# --- UI HEADER ---
st.title("A Study on Image-based Question Answering")
st.write("""You will be shown a number of images, and each such image will be accompanied by **THREE questions**.  
Each image will primarily portray an entity.
The questions will enquire about three things: 
*Affluence*: Whether the image reflects impoverished or affluent conditions.
*General Condition*: The physical state of depicted objects (e.g., worn, damaged,or pristine).
*Cultural Localization*: The extent to which culturally specific symbols (e.g., religious motifs, traditional architecture) are present versus globalized visual cues in the primary entity.
Answer **ALL** questions.  
**Total time: 45 minutes**

### Instructions:

1. See the image very carefully before answering a question.  
2. Each question can be answered on a scale of 1 to 5. 
3. We will define the scores within each scale for each question. READ them carefully.  

""")

if "prolific_id" not in st.session_state:
    st.session_state.prolific_id = None

if not st.session_state.prolific_id:
    with st.form("prolific_form"):
        st.write("## Please enter your Prolific ID to begin:")
        pid = st.text_input("Prolific ID", max_chars=24)
        submitted = st.form_submit_button("Submit")
        if submitted:
            if pid.strip():
                st.session_state.prolific_id = pid.strip()
                st.success("Thank you! You may now begin the survey.")
                st.rerun()
            else:
                st.error("Please enter a valid Prolific ID.")
    st.stop()  # Stop further execution until ID is entered

# --- SESSION STATE ---
if "submitted_all" not in st.session_state:
    st.session_state.submitted_all = False

# --- FORM ---
with st.form("all_images_form"):
    
    all_responses = []
    missing_questions = []
    incomplete = False  # Flag to check if any question was left unanswered
    for idx, img_name in enumerate(IMAGE_LIST):
        st.markdown(f"### Image {idx + 1}")

        # Load and display image
        img_url = GITHUB + img_name
        try:
            img_data = requests.get(img_url).content
            image = Image.open(BytesIO(img_data))
            st.image(image, use_container_width=True)
        except:
            st.error("Could not load image.")
            continue

        questions = QUESTIONS.get(img_name, [])
        response = {"image": img_name}

        # Layout with 2 columns
        # if len(questions) == 4:
        # col1a, col1b = st.columns(2)
        # else:
            # col1 = col2 = st

        # Question 1
        # with col1a:
        q1 = questions[0]
        ans1 = st.radio(q1["question"], q1["options"], key=f"q1_{idx}")
        response[q1["question"]] = ans1
        if not ans1:
            incomplete = True
            missing_questions.append(f"Image {idx + 1} - Q1")
            # if "None of the above" in ans1:
            #     other1 = st.text_input("Please describe (Q1):", key=f"other1_{idx}")
            #     response[f"{q1['question']} - Other"] = other1

        # Question 2
        # with col1b:
        q2 = questions[1]
        ans2 = st.radio(q2["question"], q2["options"], key=f"q2_{idx}")
        response[q2["question"]] = ans2
        if not ans2:
            incomplete = True
            missing_questions.append(f"Image {idx + 1} - Q2")
            # if "None of the above" in ans2:
            #     other2 = st.text_input("Please describe (Q2):", key=f"other2_{idx}")
            #     response[f"{q2['question']} - Other"] = other2
        # col2a, col2b = st.columns(2)
        # with col2a:

        q3 = questions[2]
        ans3 = st.radio(q3["question"], q3["options"], key=f"q3_{idx}")
        response[q3["question"]] = ans3
        if not ans3:
            incomplete = True
            missing_questions.append(f"Image {idx + 1} - Q3")
        
        all_responses.append(response)
        st.markdown("---")

    submitted = st.form_submit_button("Submit All")

# --- HANDLE FINAL SUBMISSION ---
if submitted:
    if incomplete:
        st.error("Please answer all questions before submitting.")
        for q in missing_questions:
            st.warning(f"Missing: {q}")
    else:
        # timestamp = datetime.datetime.utcnow()
        doc_ref = db.collection("GeoDiv (CEVI) survey_responses").document(st.session_state.prolific_id)
        doc_ref.set({
            "prolific_id": st.session_state.prolific_id,
            "timestamp": firestore.SERVER_TIMESTAMP,
            "responses": all_responses
        })
        st.session_state.submitted_all = True
        df = pd.DataFrame(all_responses)
        st.success("Survey complete. Thank you!")
        # st.dataframe(df)

        # CSV download
        # csv = df.to_csv(index=False).encode("utf-8")
        # st.download_button("Download Responses", csv, "survey_responses.csv", "text/csv")