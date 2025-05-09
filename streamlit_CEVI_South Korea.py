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
country = 'South Korea'
response = requests.get(GITHUB + f'{country}.csv')
df = pd.read_csv(StringIO(response.text))

IMAGE_LIST =  list(df['new_image_path'])# filenames in the GitHub repo
QUESTIONS = {}
ENTITY_LIST = list(df['concept'])

q1 = "Rate this image on the level of *affluence* depicted in the *entire* image. The options are a scale of 1 to 5, where each score is defined within the options."
q2 = "Rate this image on the *general condition* of the *entity*. The options are a scale of 1 to 5, where each score is defined within the options."
q3 = "Rate this image on the *cultural localization* of the *entity* with respect to *your* country. The options are a scale of 1 to 5, where each score is defined within the options."

a1 = ["1 – **Impoverished**:	Severe visible decay; disrepair, dirt, broken infrastructure, minimal economic activity.",
      "2 – **Low Affluence**:	Basic but aging structures; modest upkeep; informal or patchy development visible.",
      "3 – **Moderate Affluence**:	Clean and functional spaces; organized but simple environments; middle-income indicators.",
      "4 – **High Affluence**:	Well-maintained, vibrant areas; professional storefronts; signs of prosperity and civic care.",
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
st.title(f"A Study on Image-based Question Answering in {country}")
st.write("""You will be shown a number of images, and each such image will be accompanied by **THREE questions**.  
Each image will primarily portray an entity.
The questions will enquire about three things:\n 
**Affluence**: Whether the **overall** image reflects **impoverished** or **affluent conditions**.\n
**General Condition**: The **physical state** of the **depicted entity** (e.g., worn, damaged,or pristine).\n
**Cultural Localization**: The extent to which **culturally specific symbols** (e.g., religious motifs, traditional architecture) of **your country** are present versus globalized visual cues in the **entity**.\n
Answer **ALL** questions.  \n
**Total time: 30 minutes**

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
    
if "page_idx" not in st.session_state:
    st.session_state.page_idx = 0
if "responses" not in st.session_state:
    st.session_state.responses = []

# End of survey
if st.session_state.page_idx >= len(IMAGE_LIST):
    st.success("✅ Survey complete. Thank you!")

    # Save to Firestore
    doc_ref = db.collection(f"GeoDiv (CEVI) survey_responses_{country}").document(st.session_state.prolific_id)
    doc_ref.set({
        "prolific_id": st.session_state.prolific_id,
        "timestamp": firestore.SERVER_TIMESTAMP,
        "responses": st.session_state.responses
    })

    st.dataframe(pd.DataFrame(st.session_state.responses))
    st.stop()

# --- Current Image and Questions ---
img_name = IMAGE_LIST[st.session_state.page_idx]
entity = ENTITY_LIST[st.session_state.page_idx]
questions = QUESTIONS[img_name]

st.markdown(f"### Image {st.session_state.page_idx + 1}: `{entity}`")
img_url = GITHUB + img_name

try:
    img_data = requests.get(img_url).content
    image = Image.open(BytesIO(img_data))
    st.image(image, use_container_width=True)
except:
    st.error("Could not load image.")
    st.stop()

with st.form(f"form_{st.session_state.page_idx}"):
    response = {"image": img_name, "entity": entity}
    missing = False

    for q_idx, q in enumerate(questions):
        key = f"img{st.session_state.page_idx}_q{q_idx}"
        ans = st.radio(f"**This image is of the entity: {entity}**. "+q["question"], q["options"], key=key, index=None)
        response[q["question"]] = ans
        if not ans:
            missing = True

    submitted = st.form_submit_button("Next")

if submitted:
    if missing:
        st.error("❗ Please answer all questions before proceeding.")
    else:
        user_doc = db.collection(f"GeoDiv (CEVI) survey_responses_{country}").document(st.session_state.prolific_id)

        # Append to Firestore with arrayUnion
        user_doc.set({
            "prolific_id": st.session_state.prolific_id,
            "timestamp": firestore.SERVER_TIMESTAMP,
        }, merge=True)

        user_doc.update({
            "responses": firestore.ArrayUnion([response])
        })

        st.session_state.responses.append(response)
        st.session_state.page_idx += 1
        st.rerun()
