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
import uuid

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

response_obj = requests.get(GITHUB + 'objattr_seed_set.csv')
df_obj = pd.read_csv(StringIO(response_obj.text))

response_bg = requests.get(GITHUB + 'bgr_seed_set.csv')
df_bg = pd.read_csv(StringIO(response_bg.text))

df = pd.merge(df_obj, df_bg, on=['concept', 'img_path'], how='inner')

df["attribute_values"] = df["attribute_values"].apply(ast.literal_eval)
df["ind_attribute_values"] = df["ind_attribute_values"].apply(ast.literal_eval)
df["out_attribute_values"] = df["out_attribute_values"].apply(ast.literal_eval)

IMAGE_LIST =  list(df['img_path'])# filenames in the GitHub repo
QUESTIONS = {}

for idx, row in df.iterrows():
    QUESTIONS[row['img_path']] = [{"entity_q": '**For answering this question, focus only on the primary entity. '+row['question']+'**', 
                                    "options": ['The enquired entity attribute is not visible in the image'] + row['attribute_values']},
                                  {"ind_q": '**'+row['ind_question']+'**', 
                                    "options": ['The enquired background attribute is not visible in the image'] + row['ind_attribute_values']},
                                  {"out_q": '**'+row['out_question']+'**', 
                                    "options": ['The enquired background attribute is not visible in the image'] + row['out_attribute_values']}]
# --- UI HEADER ---
st.title("A Study on Image-based Question Answering")
st.write("""You will be shown a number of images, and each such image will be accompanied by **FIVE questions**. The first question will be about the **primary entity** depicted in the image. The second, third and fourth questions will be about the background of the image, excluding the primary entity. The last question will ask you to rate your confidence in answering the questions.
Answer **ALL** questions.  
**Total time: 45 minutes**

### Instructions:

1. See the image very carefully before answering a question.  
2. Each question will be associated with options. 
3. **Multiple options can be correct for the first three questions.**  
4. If you do not feel any of the options is correct, select **None of the above**.
""")

db_name = "GeoDiv_VDI_Assessment"

def collate_info(db_name, prolific_id):
    # Fetch responses
    docs = db.collection(db_name).stream()
    data = [doc.to_dict() for doc in docs]
    df = pd.DataFrame(data) #.read_csv("vdi_2.csv")
    # df.to_csv(f"vdi_2.csv", index=False)
    # print("Downloaded to image_geolocalization_hs.csv")
    if len(df) == 0:
        return []
    df['responses'] = df['responses'].astype(str)
    df['responses'] = df['responses'].apply(ast.literal_eval)
    df = df[df['prolific_id'] == prolific_id]
    if len(df) == 0:
        return []
    row = df.iloc[0].to_dict()['responses']
    print(len(row))
    all_rows = []
    for lst in row:
        dic = {}
        dic["image"] = lst["image"]
        keys = [key for key in lst if ('Rate' not in key and key!="image")]
        dic["q1"] = keys[0]
        dic["a1"] = lst[keys[0]]
        dic["q2"] = keys[1]
        dic["a2"] = lst[keys[1]]
        dic["q3"] = keys[2]
        dic["a3"] = lst[keys[2]]
        dic["q4"] = keys[3]
        dic["a4"] = lst[keys[3]]
        dic["q5"] = keys[4]
        dic["a5"] = lst[keys[4]]

        all_rows.append(dic)
    return all_rows

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

db_len = len(collate_info(db_name, st.session_state.prolific_id))
# --- SESSION STATE ---
if "submitted_all" not in st.session_state:
    st.session_state.submitted_all = False

# --- FORM ---
with st.form("all_images_form"):
    
    # The `all_res` variable is storing the responses provided by the user for each image in the
    # survey. It is a list that contains dictionaries where each dictionary represents the responses
    # for a particular image. Each dictionary includes the image name, the answers to the questions
    # associated with that image, the confidence rating in answering the questions, and the rating
    # given to the image on its realism.
    all_responses = []
    missing_questions = []
    # Flag to check if any question was left unanswered
    for idx, img_name in enumerate(IMAGE_LIST[db_len:]):
        incomplete = False
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
        response = {"image": img_name, "q1": None, "q2": None, "q3": None, "q4": None, "q5": None}

        # Layout with 2 columns
        # if len(questions) == 4:
        # col1a, col1b = st.columns(2)
        # else:
            # col1 = col2 = st

        # Question 1
        # with col1a:
        q1 = questions[0]
        ans1 = st.multiselect(q1["entity_q"], q1["options"], key=f"q1_{idx}")
        response["q1"] = ans1
        if not ans1:
            incomplete = True
            missing_questions.append(f"Image {idx + 1} - Q1")
            # if "None of the above" in ans1:
            #     other1 = st.text_input("Please describe (Q1):", key=f"other1_{idx}")
            #     response[f"{q1['question']} - Other"] = other1
        # Question 2
        # with col1b:
        q2 = "Is the background of the image (i.e., the part excluding the primary entity) visible?"
        bg_visible = st.radio(q2, ['Choose an option', 'Yes', 'No'], key=f"q2_{idx}")
        response["q2"] =  bg_visible
        if bg_visible == 'Choose an option':
            incomplete = True
            missing_questions.append(f"Image {idx + 1} - Q2")
        st.write(bg_visible)
        # if bg_visible == 'Yes':
        q3 = "Is the image indoor or outdoor?"
        indoor_flag = st.radio(q3, ['Choose an option', 'Indoor', 'Outdoor'], key=f"q3_{idx}")
        response["q3"] = indoor_flag
        # if indoor_flag == 'Indoor':
        q4 = questions[1]["ind_q"]
        options = questions[1]["options"]
        ans_bg = st.multiselect(q4, options, key=f"q4_{idx}")
        response["q4"] = ans_bg
        # else:
        q6 = questions[2]["out_q"]
        options = questions[2]["options"]
        ans_bg1 = st.multiselect(q6, options, key=f"q6_{idx}")
        response["q6"] = ans_bg1
        # if indoor_flag == 'Choose an option':
        #     incomplete = True
        #     missing_questions.append(f"Image {idx + 1} - Q3")
        
        # response["q4"] = ans_bg
        if not ans_bg:
            incomplete = True
            missing_questions.append(f"Image {idx + 1} - Q4")

        q5 = {"question": "**Rate your confidence in answering the questions.**",
                "options": ["High confidence", "Medium confidence", "Low confidence"]}
        ans5 = st.radio(q5["question"], q5["options"], key=f"q5_{idx}")
        st.write(ans5)
        if not ans5:
            incomplete = True
            missing_questions.append(f"Image {idx + 1} - Q5")
        response["q5"] = ans5
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
        doc_ref = db.collection("GeoDiv_VDI_Assessment").document(st.session_state.prolific_id)
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