#!/usr/bin/env python
# coding: utf-8

# In[11]:


import pandas as pd
from collections import defaultdict

import importlib

import os

import Merge_Filing_Data_W2 as MFD

importlib.reload(MFD)

def make_numeric(some_str):
    try:
        return int(some_str)
    except (ValueError, TypeError):
        try:
            return float(some_str)
        except (ValueError, TypeError):
            return some_str  # Return original if not numeric


def building_disjoints(sort_ctx_by_type):
    shared_items = {}

    disjoint_sets = {}

    items_sorted = list(sort_ctx_by_type.items())

    for i in range(len(items_sorted)):
        for j in range(i + 1, len(items_sorted)):
            key1, values1 = items_sorted[i]
            key2, values2 = items_sorted[j]

            inters = values1.intersection(values2)

            values1d = values1 - values2
            values2d = values2 - values1

            key_s = key1 + "_" + key2
            key_1d = key1 +"d"
            key_2d = key2 +"d"

            value_s = inters	

            disjoint_sets[key_1d] = values1d
            disjoint_sets[key_2d] = values2d

            shared_items[key_s]=value_s

            # shared = values1 & values2
            # if shared:
            #     new_key = key1+"_"+key2
            #     shared_items[new_key]

    return shared_items, disjoint_sets

def compare_with_default(csv_bal, csv_inc_cf, df):
    # for comparing disjoint sets against data in bal_sheet_snapshot.csv and income_cashflow_term.csv
    # key assumption to test if context refs are organized by instant vs periodic
    # therefore need to see which of the data's intersection is none zero with disjoint defaults
    # a set has none zero intersection with income_cashflow_term.csv then it shouldnt intersect wit bal_sheet_snapshot.csv
    # so test for nonzero intersection with one of the csv and zero intersection with the other csv

    # get label column from the csv_filename and compare with labels in dataset

    df_bal = pd.read_csv(csv_bal)
    df_inc_cf = pd.read_csv(csv_inc_cf)

    if len(set(df_bal['label']).intersection(set(df['label'])))>0 and len(set(df_inc_cf['label']).intersection((set(df['label']))))==0:
            return "B"

    elif len(set(df_bal['label']).intersection(set(df['label'])))==0 and len(set(df_inc_cf['label']).intersection((set(df['label']))))>0:
        return "IC"

    return None  

def merge_contexts_by_shared_tags(items_list):
    merged = True
    while merged:
        merged = False
        i = 0

        while i < len(items_list):
            current_key, current_val = items_list[i]
            current_tags = set(tag for tag, val in current_val)

            j = i + 1
            while j < len(items_list):
                next_key, next_val = items_list[j]
                next_tags = set(tag for tag, val in next_val)

                if current_tags.intersection(next_tags):
                    merged_key = current_key + "_" + next_key
                    merged_val = list(set(current_val + next_val))
                    items_list[i] = (merged_key, merged_val)
                    items_list.pop(j)

                    current_key, current_val = merged_key, merged_val
                    current_tags = set(tag for tag, val in merged_val)
                    merged = True
                    # Don't increment j; check next item in shortened list
                else:
                    j += 1

            i += 1

    return items_list


def main():

    merged_file, ticker = MFD.main()

    #merged_file = "merged_sec_xbrl_aapl.csv"

    #ticker = merged_file.split('_')[2].split('.')[0]


    # check for us-gaap tag presence before doing anything


    # Load your merged SEC XBRL CSV
    df = pd.read_csv(merged_file)
    #print(f"Columns: {df.columns.tolist()}")

    # Optional: save context frequency
    df['contextRef'].value_counts().to_csv(f"SEC_contextRefs_{ticker}.csv")

    #print("contextRef done")

    # Build dictionary of lists grouped by context
    sort_by_context = defaultdict(list)

    # for every cxt ref key in sort_by_context if value list has at least one same tag, merge lists, for context ref keys make a new key which is a string conctenation of the context refs
    sort_ctx_by_type = defaultdict(list)

    for _, row in df.iterrows():
        if row['tag_prefix'] == 'us-gaap':
            context = row['contextRef']
            tag = row['tag_local']

            if "TextBlock" in tag:
                continue
            val = row['value_raw']
            sort_by_context[context].append((tag, val))
    #A context is a set or grouping of reported facts.  
    #Each reported fact has a taxonomy element and value in an XBRL document such as a financial report.  
    #A context groups together all the facts that share the same reporting period and certain other characteristics.

    # #---- builds sort_by_context
    #sort_by_context = builds_sort_by_context(sort_by_context, df)

    # # for every cxt ref key in sort_by_context if value list has at least one same tag, merge lists, for context ref keys make a new key which is a string conctenation of the context refs
    items_list = list(sort_by_context.items())

    new_items_list = merge_contexts_by_shared_tags(items_list)

    # for ctx, facts in items_list:
    for ctx, facts in new_items_list:
        # Rebuild facts list with converted values
        tag_dict = {}
        for tag, val in facts:
            num = make_numeric(val)
            if isinstance(num, str):
                continue
            if tag in tag_dict:
                tag_dict[tag]+=num
            else:
                tag_dict[tag]=num

        converted_facts = [(tag, val) for tag, val in tag_dict.items()]

        print(f"\nTotal metrics in context: {len(converted_facts)}")

        if len(converted_facts) >= 1:
            sort_ctx_by_type[ctx] = converted_facts
            # print(ctx)
            # print(converted_facts)
            # print()

        #---- builds sort_ctx_by_type

    #new_items_list = builds_sort_ctx_by_typeA(items_list)        
    #new_sort_ctx_by_type = builds_sort_ctx_by_typeB(sort_ctx_by_type, new_items_list, ticker)

    for ctx, converted_facts in sort_ctx_by_type.items():

        if len(converted_facts) >= 1:  

            df = pd.DataFrame(converted_facts, columns=['label', 'value'])
            df['value'] = df['value'].apply(lambda x: f"{int(x):,}" if pd.notna(x) else '')

            #df['context'] = ctx  # tracks which context each row came from

            csv_bal = "bal_sheet_example.csv"
            csv_inc_cf = "income_&_cashflow_example.csv"

            # check to see which one is bal and which one is cashflow/income by finding one thhat matches criteria:
            # meaning it has zero intersection for one sheet info and nonzero with other

            # balance sheet
            if compare_with_default(csv_bal, csv_inc_cf, df) == "B":
                filename = f'bal_sheet_{ticker}_data.csv'
            # income statement
            elif compare_with_default(csv_bal, csv_inc_cf, df) == "IC":
                filename = f'inc_cf_{ticker}_data.csv'
            else:     
                filename = f'{ticker}_data.csv'

            if os.path.exists(filename):
                df.to_csv(filename, mode='a', header=False, index=False)
                print(f"✓ Appended to: {filename}")
            else:
                df.to_csv(filename, index=False)
                print(f"✓ Created and exported to: {filename}")

    return ticker


if __name__ == "__main__":
    main()         


# In[ ]:




