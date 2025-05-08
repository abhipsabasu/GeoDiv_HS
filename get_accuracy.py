import pandas as pd
import ast
import re

# df_hs = pd.read_csv('GeoDiv_survey_responses.csv')
# df_bgr = pd.read_csv('df_bgr_sampled_updated_withnewpaths.csv')
# df_obj = pd.read_csv('updated_sampled_object_attributes.csv')


# final_df = []
# new_row = {}
# answers = 4

# def get_correct_category(gemini, answers):
#     if gemini in [ans.lower() for ans in answers]:
#         return gemini
#     else:
#         for i, ans in enumerate([ans.lower() for ans in answers]):
#             match = re.search(r'\((.*?)\)', ans)
#             if match:
#                 items = [item.strip() for item in match.group(1).split(',')]
#                 if gemini in items:
#                     return answers[i]
#     return None
    

# for idx, row in df_hs.iterrows():
#     responses = ast.literal_eval(df_hs.loc[idx, 'responses'])
#     for response in responses:
#         for key in response:
#             if key == 'image' or key.strip('*').startswith('Rate'):
#                 continue
#             ans = response[key]
#             if response['image'] + '_' + key.strip('*') in new_row:
#                 new_row[response['image'] + '_' + key.strip('*')][row['prolific_id']] = ans
#             else:
#                 new_row[response['image'] + '_' + key.strip('*')] = {'question': key.strip('*'),
#                                                                     row['prolific_id']: ans,
#                                                                     'image': response['image']}
#                 d1, d2 = df_bgr[(df_bgr['question']==key.strip('*')) & (df_bgr['new_path']==response['image'])], df_obj[(df_obj['question']==key.strip('*')) & (df_obj['new_path']==response['image'])]
#                 if len(d1) > 0:
#                     gemini = d1['answer'].values.tolist()[0]
#                 else:
#                     gemini = d2['answer'].values.tolist()[0]
#                     new_row[response['image'] + '_' + key.strip('*')]['all_answers'] = d2['attribute_values'].values.tolist()[0]
#                 new_row[response['image'] + '_' + key.strip('*')]['gemini'] = gemini
                
# new_row = list(new_row.values())
# df = pd.DataFrame(new_row)
# df.to_csv('VQA_HS1.csv', index=False)

def has_intersection(list1, list2):
    return bool(set(list1) & set(list2))

df = pd.read_csv('VQA_HS.csv')
# df = df[df['type']=='background']
correct = []

for idx, row in df.iterrows():
    # print(idx, row['gemini'], row['majority'])
    gemini = ast.literal_eval(row['gemini'])
    majority = ast.literal_eval(row['majority'])
    # print(type(gemini), type(majority))
    correct.append(int(has_intersection(gemini, majority)))

df['correct'] = correct

df.to_csv('VQA_HS.csv', index=False)