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
country = 'China'
response = requests.get(GITHUB + f'{country}.csv')
df = pd.read_csv(StringIO(response.text))

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
        ans = st.radio(q["question"], q["options"], key=key)
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
        st.experimental_rerun()
