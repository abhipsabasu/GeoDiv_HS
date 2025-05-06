import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from io import StringIO
from PIL import Image
import ast
import os

# --- CONFIG ---
GITHUB = "https://raw.githubusercontent.com/abhipsabasu/GeoDiv_HS/main/"

response_obj = requests.get(GITHUB + 'sampled_object_attributes_withnewpaths.csv')
df_obj = pd.read_csv(StringIO(response_obj.text))

response_bg = requests.get(GITHUB + 'df_bgr_sampled_updated_withnewpaths.csv')
df_bg = pd.read_csv(StringIO(response_bg.text))

df = pd.merge(df_obj, df_bg, on=['concept_id', 'new_path'], how='inner')

df["attribute_values_x"] = df["attribute_values_x"].apply(ast.literal_eval)
df["attribute_values_y"] = df["attribute_values_y"].apply(ast.literal_eval)

IMAGE_LIST =  list(df['new_path'])# filenames in the GitHub repo
QUESTIONS = {}

for idx, row in df.iterrows():
    QUESTIONS[row['new_path']] = [{"question": row['question_x'], 
                                    "options": row['attribute_values_x']},
                                  {"question": row['question_y'], 
                                    "options": row['attribute_values_y']}]
# --- UI HEADER ---
st.title("A Survey on Image-based Question Answering")
st.write("""You will be shown a number of images, and each such image will 
            be accompanied by TWO questions. Each question will be associated 
            with a few options. Multiple options can be correct. If you do 
            not feel any of the options is correct, select None of this, 
            and mention your choice.""")

# --- SESSION STATE ---
if "submitted_all" not in st.session_state:
    st.session_state.submitted_all = False

# --- FORM ---
with st.form("all_images_form"):
    all_responses = []

    for idx, img_name in enumerate(IMAGE_LIST):
        # st.markdown(f"### Image {idx + 1}: `{img_name}`")

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
        if len(questions) == 2:
            col1, col2 = st.columns(2)
        else:
            col1 = col2 = st

        # Question 1
        with col1:
            q1 = questions[0]
            ans1 = st.multiselect(q1["question"], q1["options"], key=f"q1_{idx}")
            response[q1["question"]] = ans1
            if "None of the above" in ans1:
                other1 = st.text_input("Please describe (Q1):", key=f"other1_{idx}")
                response[f"{q1['question']} - Other"] = other1

        # Question 2
        with col2:
            q2 = questions[1]
            ans2 = st.multiselect(q2["question"], q2["options"], key=f"q2_{idx}")
            response[q2["question"]] = ans2
            if "None of the above" in ans2:
                other2 = st.text_input("Please describe (Q2):", key=f"other2_{idx}")
                response[f"{q2['question']} - Other"] = other2

        all_responses.append(response)
        st.markdown("---")

    submitted = st.form_submit_button("Submit All")

# --- HANDLE FINAL SUBMISSION ---
if submitted or st.session_state.submitted_all:
    st.session_state.submitted_all = True
    df = pd.DataFrame(all_responses)
    st.success("Survey complete. Thank you!")
    st.dataframe(df)

    # CSV download
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("Download Responses", csv, "survey_responses.csv", "text/csv")