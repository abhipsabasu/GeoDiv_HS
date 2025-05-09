import pandas as pd
import ast
import re

df_hs = pd.read_csv('GeoDiv_survey_responses_India.csv')

final_df = []
new_row = {}
answers = 4

for idx, row in df_hs.iterrows():
    responses = ast.literal_eval(df_hs.loc[idx, 'responses'])
    for response in responses:
        for key in response:
            if key == 'entity' or key == 'image' or 'general condition' in key or 'cultural localization' in key:
                continue
            ans = response[key]
            print(ans)
            ans = int(ans[0])
            if response['image'] not in new_row:
                new_row[response['image']] = {'image': response['image'], row['prolific_id']: ans}                
            else:
                new_row[response['image']][row['prolific_id']] = ans
new_row = list(new_row.values())
df = pd.DataFrame(new_row)
df.to_csv('Affluence_India.csv', index=False)

# def has_intersection(list1, list2):
#     return bool(set(list1) & set(list2))

# df = pd.read_csv('VQA_HS.csv')
# # df = df[df['type']=='background']
# correct = []

# for idx, row in df.iterrows():
#     # print(idx, row['gemini'], row['majority'])
#     gemini = ast.literal_eval(row['gemini'])
#     majority = ast.literal_eval(row['majority'])
#     # print(type(gemini), type(majority))
#     correct.append(int(has_intersection(gemini, majority)))

# df['correct'] = correct

# df.to_csv('VQA_HS.csv', index=False)