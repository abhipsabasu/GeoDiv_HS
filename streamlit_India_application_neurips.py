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
import random

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
country = 'India'
response = requests.get(GITHUB + f'{country}_aff_paths.csv')
df = pd.read_csv(StringIO(response.text))

IMAGE_LIST =  list(df['paths'])# filenames in the GitHub repo
QUESTIONS = {}
ENTITY_LIST = "house"

q1 = "Rate this image on the level of *affluence* depicted in the *entire* image. The options are a scale of 1 to 5, where each score is defined within the options."

a1 = ["1 – **Impoverished**:	Severe visible decay; disrepair, dirt, broken infrastructure, minimal economic activity.",
      "2 – **Low Affluence**:	Basic but aging structures; modest upkeep; informal or patchy development visible.",
      "3 – **Moderate Affluence**:	Clean and functional spaces; organized but simple environments; middle-income indicators.",
      "4 – **High Affluence**:	Well-maintained, vibrant areas; professional storefronts; signs of prosperity and civic care.",
      "5 – **Very High Affluence (Luxury)**:	Sleek, modern, or designer elements; upscale brands; spotless, elite environments."]


for idx, row in df.iterrows():
    question = {"question": '**'+q1+'**', 
                                    "options": a1}
# --- UI HEADER ---
st.title("A Study on Image-based Question Answering")
st.write("""You will be shown a number of images, and each such image will be accompanied by **THREE questions**.  
Each image will *primarily* portray one *entity*, which shall be mentioned on the top of the image.
The questions will enquire about:\n 
*Affluence*: Whether the *overall* image reflects impoverished or affluent conditions.\n

Answer **ALL** questions.  \n
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
    
if "page_idx" not in st.session_state:
    st.session_state.page_idx = 0
if "responses" not in st.session_state:
    st.session_state.responses = []

if "shuffled_images" not in st.session_state:
    st.session_state.shuffled_images = random.sample(IMAGE_LIST, len(IMAGE_LIST))

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
img_name = st.session_state.shuffled_images[st.session_state.page_idx]
entity = "house"
questions = q1

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
    ans = st.radio(f"**This image is of the entity: {entity}**. "+question["question"], question["options"], index=None)
    response["human"] = ans
    if not ans:
        missing = True

    submitted = st.form_submit_button("Next")

if submitted:
    if missing:
        st.error("❗ Please answer all questions before proceeding.")
    else:
        user_doc = db.collection(f"GeoDiv_{country}_Affluence").document(st.session_state.prolific_id)

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
