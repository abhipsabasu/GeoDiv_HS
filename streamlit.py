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

response_obj = requests.get(GITHUB + 'updated_sampled_object_attributes.csv')
df_obj = pd.read_csv(StringIO(response_obj.text))

response_bg = requests.get(GITHUB + 'df_bgr_sampled_updated_withnewpaths.csv')
df_bg = pd.read_csv(StringIO(response_bg.text))

df = pd.merge(df_obj, df_bg, on=['concept_id', 'new_path'], how='inner')

df["attribute_values_x"] = df["attribute_values_x"].apply(ast.literal_eval)
df["attribute_values_y"] = df["attribute_values_y"].apply(ast.literal_eval)

IMAGE_LIST =  list(df['new_path'])# filenames in the GitHub repo
QUESTIONS = {}

for idx, row in df.iterrows():
    QUESTIONS[row['new_path']] = [{"question": '**'+row['question_x']+'**', 
                                    "options": row['attribute_values_x']},
                                  {"question": '**'+row['question_y']+'**', 
                                    "options": row['attribute_values_y']}]
# --- UI HEADER ---
st.title("A Study on Image-based Question Answering")
st.write("""You will be shown a number of images, and each such image will be accompanied by **FOUR questions**.  
Answer **ALL** questions.  
**Total time: 45 minutes**

### Instructions:

1. See the image very carefully before answering a question.  
2. Each question will be associated with options. 
3. **Multiple options can be correct for the first two questions.**  
4. If you do not feel any of the options is correct, select **None of the above**.  
5. You can refer to the internet in case you want to know more about certain options.
6. The bottom two questions are **single-options only**.
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
        col1a, col1b = st.columns(2)
        # else:
            # col1 = col2 = st

        # Question 1
        with col1a:
            q1 = questions[0]
            ans1 = st.multiselect(q1["question"], q1["options"], key=f"q1_{idx}")
            response[q1["question"]] = ans1
            if not ans1:
                incomplete = True
                missing_questions.append(f"Image {idx + 1} - Q1")
            # if "None of the above" in ans1:
            #     other1 = st.text_input("Please describe (Q1):", key=f"other1_{idx}")
            #     response[f"{q1['question']} - Other"] = other1

        # Question 2
        with col1b:
            q2 = questions[1]
            ans2 = st.multiselect(q2["question"], q2["options"], key=f"q2_{idx}")
            response[q2["question"]] = ans2
            if not ans2:
                incomplete = True
                missing_questions.append(f"Image {idx + 1} - Q2")
            # if "None of the above" in ans2:
            #     other2 = st.text_input("Please describe (Q2):", key=f"other2_{idx}")
            #     response[f"{q2['question']} - Other"] = other2
        col2a, col2b = st.columns(2)
        with col2a:
            q3 = {"question": "**Rate your confidence in answering the question.**",
                  "options": ["High confidence", "Medium confidence", "Low confidence"]}
            ans3 = st.radio(q3["question"], q3["options"], key=f"q3_{idx}")
            response[q3["question"]] = ans3
            if not ans3:
                incomplete = True
                missing_questions.append(f"Image {idx + 1} - Q3")
        with col2b:
            q4 = {"question": "**Rate the image on its realism, on a scale of 1 to 5, where 1 means not realistic at all, 5 means highly realistic.**",
                  "options": ["1", "2", "3", "4", "5"]}
            ans4 = st.radio(q4["question"], q4["options"], key=f"q4_{idx}")
            response[q4["question"]] = ans4
            if not ans4:
                incomplete = True
                missing_questions.append(f"Image {idx + 1} - Q4")
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
        doc_ref = db.collection("GeoDiv survey_responses").document(st.session_state.prolific_id)
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