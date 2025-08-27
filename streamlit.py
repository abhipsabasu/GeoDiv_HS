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

# Extract unique concepts for selection
unique_concepts = sorted(df['concept'].str.split('_').str[0].unique())

# --- UI HEADER ---
st.title("A Study on Image-based Question Answering")

# Initialize session state variables
if "selected_concept" not in st.session_state:
    st.session_state.selected_concept = None

if "completed_concepts" not in st.session_state:
    st.session_state.completed_concepts = []

if "prolific_id" not in st.session_state:
    st.session_state.prolific_id = None

if "survey_complete" not in st.session_state:
    st.session_state.survey_complete = False

if "review_mode" not in st.session_state:
    st.session_state.review_mode = False

if "submitted_all" not in st.session_state:
    st.session_state.submitted_all = False
if "permanently_complete" not in st.session_state:
    st.session_state.permanently_complete = False

# Get available concepts (excluding completed ones)
available_concepts = [concept for concept in unique_concepts if concept not in st.session_state.completed_concepts]

# Check if Prolific ID is provided first
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

# Step-by-step database check and concept loading
if st.session_state.prolific_id:
    try:
        # Step a) Check if there is an entry for the given prolific_id in the db
        doc_ref = db.collection("GeoDiv_VDI_Assessment").document(st.session_state.prolific_id)
        existing_doc = doc_ref.get()
        
        if not existing_doc.exists:
            # No entry exists - load as usual (first time user)
            st.info("**Welcome! This is your first time taking the survey.**")
            st.session_state.completed_concepts = []
            st.session_state.survey_complete = False
        else:
            # Entry exists - load existing data
            existing_data = existing_doc.to_dict()
            stored_completed_concepts = existing_data.get('completed_concepts', [])
            st.session_state.completed_concepts = stored_completed_concepts
            st.session_state.survey_complete = existing_data.get('survey_complete', False)
            
            # Step b) Check what concepts are present within the entry
            total_concepts = len(unique_concepts)
            completed_count = len(st.session_state.completed_concepts)
            
            if completed_count >= total_concepts:
                # All concepts covered - exit the survey
                st.success("🎉 Congratulations! You have completed all available concepts!")
                st.write("**All concepts have been completed. Thank you for participating in the survey!**")
                st.stop()
            else:
                # Not all concepts covered - show remaining ones
                st.info(f"**Welcome back! You have completed {completed_count}/{total_concepts} concepts.**")
                st.info(f"**{total_concepts - completed_count} concept(s) remaining.**")
                st.info("**You can continue with the remaining concepts below.**")
                
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        st.session_state.completed_concepts = []
        st.session_state.survey_complete = False

# Calculate available concepts (excluding completed ones)
available_concepts = [concept for concept in unique_concepts if concept not in st.session_state.completed_concepts]

# Only show concept selection if no concept is currently selected
if not st.session_state.selected_concept:
    st.write("## Please select a concept to begin:")
    
    # Progress indicator
    total_concepts = len(unique_concepts)
    completed_count = len(st.session_state.completed_concepts)
    remaining_count = len(available_concepts)
    
    st.write(f"**Progress: {completed_count}/{total_concepts} concepts completed**")
    st.progress(completed_count / total_concepts)
    
    if st.session_state.completed_concepts:
        st.write(f"**Completed concepts: {', '.join(st.session_state.completed_concepts)}**")
    st.write(f"**Remaining concepts: {remaining_count}**")
    
    selected_concept = st.selectbox("Choose a concept:", available_concepts, key="concept_selector")
    
    if st.button("Start Survey with Selected Concept"):
        st.session_state.selected_concept = selected_concept
        st.success(f"Concept '{selected_concept}' selected! You may now proceed.")
        st.rerun()
    
    # Show completed concepts if any exist
    if st.session_state.completed_concepts:
        st.markdown("---")
        st.write("## 📚 Review Completed Concepts")
        st.write("Click on a completed concept to view your previous responses:")
        
        # Create columns for completed concepts (3 per row)
        completed_concepts = st.session_state.completed_concepts
        cols_per_row = 3
        for i in range(0, len(completed_concepts), cols_per_row):
            cols = st.columns(cols_per_row)
            for j, col in enumerate(cols):
                if i + j < len(completed_concepts):
                    concept = completed_concepts[i + j]
                    with col:
                        if st.button(f"📖 {concept}", key=f"review_{concept}"):
                            st.session_state.selected_concept = concept
                            st.session_state.review_mode = True
                            st.rerun()
        
        st.info("💡 **Tip:** You can review your completed concepts anytime to see your previous responses and track your progress.")
    
    st.stop()



# Handle review mode for completed concepts
if st.session_state.review_mode:
    st.write(f"## 📖 Reviewing Completed Concept: {st.session_state.selected_concept}")
    st.write("**This concept has been completed. Here are your previous responses:**")
    
    # Get previous responses for this concept
    doc_ref = db.collection("GeoDiv_VDI_Assessment").document(st.session_state.prolific_id)
    existing_doc = doc_ref.get()
    
    if existing_doc.exists:
        existing_data = existing_doc.to_dict()
        all_responses = existing_data.get('responses', [])
        
        # Filter responses for current concept
        concept_responses = []
        for resp in all_responses:
            if 'image' in resp and resp['image']:
                # Check if this image belongs to the current concept
                if resp['image'].startswith(st.session_state.selected_concept + "_"):
                    concept_responses.append(resp)
        
        # Show summary statistics
        st.write(f"**Total images in this concept: {len(concept_responses)}**")
        
        # Calculate confidence distribution
        confidence_counts = {}
        for resp in concept_responses:
            confidence = resp.get('q5', 'Not answered')
            confidence_counts[confidence] = confidence_counts.get(confidence, 0) + 1
        
        if confidence_counts:
            st.write("**Confidence Level Distribution:**")
            for confidence, count in confidence_counts.items():
                st.write(f"- {confidence}: {count} image(s)")
        
        # Show completion info if available
        if existing_data.get('timestamp'):
            st.write(f"**Completed on:** {existing_data['timestamp']}")
        
        st.markdown("---")
        
        # Display responses
        for idx, response in enumerate(concept_responses):
            st.markdown(f"### Image {idx + 1}: {response['image']}")
            
            # Display image
            img_url = GITHUB + response['image']
            try:
                img_data = requests.get(img_url).content
                image = Image.open(BytesIO(img_data))
                st.image(image, use_container_width=True, width=300)
            except:
                st.error("Could not load image.")
            
            # Display responses
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Q1 (Primary Entity):**")
                if response.get('q1'):
                    if isinstance(response['q1'], list):
                        st.write(", ".join(response['q1']))
                    else:
                        st.write(response['q1'])
                
                st.write("**Q2 (Background Visible):**")
                st.write(response.get('q2', 'Not answered'))
                
                st.write("**Q3 (Indoor/Outdoor):**")
                st.write(response.get('q3', 'Not answered'))
            
            with col2:
                st.write("**Q4 (Indoor Question):**")
                if response.get('q4'):
                    if isinstance(response['q4'], list):
                        st.write(", ".join(response['q4']))
                    else:
                        st.write(response['q4'])
                
                st.write("**Q6 (Outdoor Question):**")
                if response.get('q6'):
                    if isinstance(response['q6'], list):
                        st.write(", ".join(response['q6']))
                    else:
                        st.write(response['q6'])
                
                st.write("**Q5 (Confidence):**")
                st.write(response.get('q5', 'Not answered'))
            
            st.markdown("---")
        
        # Back button to return to concept selection
        if st.button("← Back to Concept Selection"):
            st.session_state.review_mode = False
            st.session_state.selected_concept = None
            st.rerun()
    else:
        st.error("No previous responses found for this concept.")
        if st.button("← Back to Concept Selection"):
            st.session_state.review_mode = False
            st.session_state.selected_concept = None
            st.rerun()
    
    st.stop()

# Filter dataframe based on selected concept
df_filtered = df[df['concept'].str.split('_').str[0] == st.session_state.selected_concept]

# Update IMAGE_LIST and QUESTIONS based on filtered dataframe
IMAGE_LIST = list(df_filtered['img_path'])
QUESTIONS = {}

for idx, row in df_filtered.iterrows():
    QUESTIONS[row['img_path']] = [{"entity_q": row['question']+'**', 
                                    "options": row['attribute_values']},
                                  {"ind_q": '**'+row['ind_question']+'**', 
                                    "options": row['ind_attribute_values']},
                                  {"out_q": '**'+row['out_question']+'**', 
                                    "options": row['out_attribute_values']}]

st.write(f"**Selected Concept: {st.session_state.selected_concept}**")
st.write(f"**Total images for this concept: {len(IMAGE_LIST)}**")

# Note: Progress details will be shown after loading user data
st.write("**Loading your progress...**")

db_name = "GeoDiv_VDI_Assessment"

@st.cache_data
def collate_info(db_name, prolific_id, concept=None):
    # Fetch responses
    docs = db.collection(db_name).stream()
    data = [doc.to_dict() for doc in docs]
    dfr = pd.DataFrame(data)
    if len(dfr) == 0:
        return [], 0
    dfr['responses'] = dfr['responses'].astype(str)
    dfr['responses'] = dfr['responses'].apply(ast.literal_eval)
    dfr = dfr[dfr['prolific_id'] == prolific_id]
    if len(dfr) == 0:
        return [], 0
    
    row = dfr.iloc[0].to_dict()['responses']
    print(len(row))
    all_rows = []
    
    # Filter responses by concept if specified
    if concept:
        concept_prefix = concept + "_"
        concept_responses = []
        for lst in row:
            if 'image' in lst and lst['image']:
                # Check if this image belongs to the current concept
                if any(lst['image'].startswith(concept_prefix) for concept_name in [concept]):
                    concept_responses.append(lst)
        row = concept_responses
    
    for lst in row:
        dic = {}
        dic["image"] = lst["image"]
        keys = [key for key in lst if ('Rate' not in key and key!="image")]
        if len(keys) >= 5:
            dic["q1"] = lst[keys[0]]
            dic["q2"] = lst[keys[1]]
            dic["q3"] = lst[keys[2]]
            dic["q4"] = lst[keys[3]]
            dic["q5"] = lst[keys[4]]
            all_rows.append(dic)
    
    db_len = 0
    for d in all_rows:
        if d["q1"] == "Choose an option" or not d["q1"]:
            break
        db_len = db_len + 1

    return all_rows, db_len

if "db_len" not in st.session_state:
    st.session_state.db_len = 0




# Only call collate_info if we have both prolific_id and selected concept
if st.session_state.prolific_id and st.session_state.selected_concept:
    db_prev, db_len = collate_info(db_name, st.session_state.prolific_id, st.session_state.selected_concept)
else:
    db_prev, db_len = [], 0

st.session_state.db_len = db_len

# Display progress information now that db_len is available
if st.session_state.selected_concept:
    st.write(f"**Images completed: {db_len}**")
    st.write(f"**Images remaining: {len(IMAGE_LIST) - db_len}**")
    
    # Progress bar for current concept
    if len(IMAGE_LIST) > 0:
        st.progress(db_len / len(IMAGE_LIST))
    
    # Add option to change concept
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Change Concept"):
            st.session_state.selected_concept = None
            st.rerun()
    
    with col2:
        if st.button("← Back to Concept Selection"):
            st.session_state.selected_concept = None
            st.rerun()
    
    st.write("""You will be shown a number of images, and each such image will be accompanied by **FIVE questions**. The first question will be about the **primary entity** depicted in the image. The second, third and fourth questions will be about the background of the image, excluding the primary entity. The last question will ask you to rate your confidence in answering the questions.
Answer **ALL** questions.  
**Total time: 45 minutes**

### Instructions:

1. See the image very carefully before answering a question.  
2. Each question will be associated with options. 
3. **Multiple options can be correct for the first three questions.**  
4. If you do not feel any of the options is correct, select **None of the above**.

### Survey Features:

- **Resume Functionality**: If you exit midway through a concept, you can resume from where you left off
- **Concept-by-Concept Submission**: Submit each concept individually or submit all at once
- **Progress Tracking**: See your progress across all concepts and within each concept
""")

# --- SURVEY QUESTIONS ---

# Only show the main survey form if we have a selected concept
if st.session_state.selected_concept:
    # --- SURVEY QUESTIONS ---
    
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
        entity = df_filtered.iloc[idx]['concept'].split("_")[0]    
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
        response = {"image": img_name, "q1": None, "q2": None, "q3": None, "q4": None, "q5": None, "q6": None}
        


        # Layout with 2 columns
        # if len(questions) == 4:
        # col1a, col1b = st.columns(2)
        # else:
            # col1 = col2 = st

        # Question 1
        # with col1a:
        st.markdown(f"**The primary entity depicted in the image is {entity}**")
        q1 = questions[0]
        options = q1["options"] + ["None of the above"]
        if 'yes' not in options:
            options = options + ['The enquired entity attribute is not visible in the image']
        ans1 = st.multiselect(q1["entity_q"], q1["options"] + ["None of the above"], key=f"q1_{idx}")
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
        
        # Only show q3, q4, and q6 if background is visible (q2 = 'Yes')
        if bg_visible == 'Yes':

            
            q3 = "Is the image indoor or outdoor?"
            indoor_flag = st.radio(q3, ['Choose an option', 'Indoor', 'Outdoor'], key=f"q3_{idx}")
            response["q3"] = indoor_flag
            
            if indoor_flag == 'Indoor':

                q4 = "**Indoor qn:** " + questions[1]["ind_q"]
                options = questions[1]["options"] + ["None of the above"]
                if 'yes' not in options:
                    options = options + ['The enquired background attribute is not visible in the image']
                ans_bg = st.multiselect(q4, options, key=f"q4_{idx}")
                response["q4"] = ans_bg
                
                if not ans_bg:
                    incomplete = True
                    missing_questions.append(f"Image {idx + 1} - Q4")
                    
            elif indoor_flag == 'Outdoor':

                q6 = "**Outdoor qn:** " + questions[2]["out_q"]
                options = questions[2]["options"] + ["None of the above"]
                if 'yes' not in options:
                    options = options + ['The enquired background attribute is not visible in the image']
                ans_bg1 = st.multiselect(q6, options, key=f"q6_{idx}")
                response["q6"] = ans_bg1
                
                if not ans_bg1:
                    incomplete = True
                    missing_questions.append(f"Image {idx + 1} - Q6")
                    
            elif indoor_flag == 'Choose an option':
                incomplete = True
                missing_questions.append(f"Image {idx + 1} - Q3")
        else:
            # If background is not visible, set these to None
            response["q3"] = None
            response["q4"] = None
            response["q6"] = None

        q5 = {"question": "**Rate your confidence in answering the questions.**",
                "options": ["High confidence", "Medium confidence", "Low confidence"]}
        ans5 = st.radio(q5["question"], q5["options"], key=f"q5_{idx}")
        if not ans5:
            incomplete = True
            missing_questions.append(f"Image {idx + 1} - Q5")
        response["q5"] = ans5
        all_responses.append(response)
        st.markdown("---")

    # Two columns for buttons
    col1, col2 = st.columns(2)
    
    with col1:
        submitted_concept = st.button(f"Submit Concept: {st.session_state.selected_concept}")
    
    with col2:
        submitted_all = st.button("Submit All & Take Break")
    
    # Show progress
    total_concepts = len(df['concept'].str.split('_').str[0].unique())
    remaining_concepts = total_concepts - len(st.session_state.completed_concepts)
    
    st.info(f"**Progress: {len(st.session_state.completed_concepts)}/{total_concepts} concepts completed**")
    if remaining_concepts > 0:
        st.info(f"**{remaining_concepts} concept(s) remaining**")
        st.info("**You can submit all and take a break, then return later to continue.**")
    else:
        st.success("**🎉 All concepts completed!**")
        st.info("**You can now complete the survey permanently.**")
        if st.button("Complete Survey Permanently"):
            st.session_state.permanently_complete = True
            st.rerun()
    
    # Store form submission state
    if submitted_concept or submitted_all:
        st.session_state.form_submitted = True
        st.session_state.submitted_concept = submitted_concept
        st.session_state.submitted_all_survey = submitted_all
        st.rerun()

# Handle form submissions outside the form
if st.session_state.get('form_submitted', False):
    submitted_concept = st.session_state.get('submitted_concept', False)
    submitted_all = st.session_state.get('submitted_all_survey', False)
    
    # Reset form submission state
    st.session_state.form_submitted = False
    st.session_state.submitted_concept = False
    st.session_state.submitted_all_survey = False
    
    # --- HANDLE CONCEPT SUBMISSION ---
    if submitted_concept:
        # Save responses for this concept to Firestore
        doc_ref = db.collection("GeoDiv_VDI_Assessment").document(st.session_state.prolific_id)
        
        # Get existing data
        existing_doc = doc_ref.get()
        if existing_doc.exists:
            existing_data = existing_doc.to_dict()
            existing_responses = existing_data.get('responses', [])
            # Add new responses
            all_responses_combined = existing_responses + all_responses
        else:
            all_responses_combined = all_responses
        
        # Update with new responses
        doc_ref.set({
            "prolific_id": st.session_state.prolific_id,
            "timestamp": firestore.SERVER_TIMESTAMP,
            "responses": all_responses_combined,
            "completed_concepts": st.session_state.completed_concepts + [st.session_state.selected_concept]
        })
        
        # Store the concept before resetting it
        completed_concept = st.session_state.selected_concept
        
        # Add completed concept to session state
        if completed_concept not in st.session_state.completed_concepts:
            st.session_state.completed_concepts.append(completed_concept)
        
        # Reset concept selection for next round
        st.session_state.selected_concept = None
        st.session_state.submitted_all = True
        
        st.success(f"🎉 Concept '{completed_concept}' completed successfully!")
        st.write(f"**You have completed {len(st.session_state.completed_concepts)} concept(s) so far.**")
        st.write("**Please select another concept to continue, or you're done if all concepts are completed.**")
        
        # Add option to reset survey if needed
        if st.button("🔄 Reset Survey (Start Over)"):
            # Clear completed concepts and survey completion
            st.session_state.completed_concepts = []
            st.session_state.survey_complete = False
            
            # Clear from Firestore
            doc_ref = db.collection("GeoDiv_VDI_Assessment").document(st.session_state.prolific_id)
            doc_ref.update({
                "completed_concepts": [],
                "survey_complete": False
            })
            
            st.success("Survey reset successfully! You can now start over.")
            st.rerun()
        
        # Rerun to show concept selection again
        st.rerun()

    # --- HANDLE SUBMIT ALL (TAKE BREAK) ---
    if submitted_all:
        # Save all responses but DON'T mark survey as complete
        doc_ref = db.collection("GeoDiv_VDI_Assessment").document(st.session_state.prolific_id)
        
        # Get existing data
        existing_doc = doc_ref.get()
        if existing_doc.exists:
            existing_data = existing_doc.to_dict()
            existing_responses = existing_data.get('responses', [])
            # Add new responses
            all_responses_combined = existing_responses + all_responses
        else:
            all_responses_combined = all_responses
        
        # Save progress but keep survey active
        doc_ref.set({
            "prolific_id": st.session_state.prolific_id,
            "timestamp": firestore.SERVER_TIMESTAMP,
            "responses": all_responses_combined,
            "completed_concepts": st.session_state.completed_concepts + [st.session_state.selected_concept],
            "last_break_timestamp": firestore.SERVER_TIMESTAMP
        })
        
        st.success("💾 Progress saved! You can take a break and return later.")
        st.write(f"**You have completed {len(st.session_state.completed_concepts) + 1} concept(s) so far.**")
        st.write("**When you return, you can continue with the remaining concepts.**")
        
        # Reset concept selection to show concept selection screen
        st.session_state.selected_concept = None
        st.rerun()

# Handle permanent survey completion
if st.session_state.get('permanently_complete', False):
    # Mark survey as permanently complete
    doc_ref = db.collection("GeoDiv_VDI_Assessment").document(st.session_state.prolific_id)
    
    doc_ref.update({
        "survey_complete": True,
        "completion_timestamp": firestore.SERVER_TIMESTAMP
    })
    
    st.session_state.survey_complete = True
    st.success("🎉 Congratulations! You have completed the entire survey!")
    st.write("**Thank you for participating in our study. Your responses have been recorded.**")
    st.stop()
else:
    # If no concept is selected, show a message
    st.info("Please select a concept from the concept selection screen to begin the survey.")