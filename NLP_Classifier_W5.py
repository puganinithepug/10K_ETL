#!/usr/bin/env python
# coding: utf-8

# In[37]:


import pandas as pd

from sklearn.model_selection import train_test_split

import numpy as np

# imports for pipeline to run
import requests
import re
import unicodedata
import os
import warnings

import logging

import argparse

import math

import importlib

from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans, AgglomerativeClustering, DBSCAN
from scipy.spatial.distance import cdist
import torch

# previous pipeline step
import Sort_10K_by_Context_W3 as SortCxt

# updated
importlib.reload(SortCxt)

MODEL='all-MiniLM-L6-v2'

clustering_method = 'KMeans'      

W3_DIR = "./sorted_inc&cf_bal_data_W3"

learned_bal = "learned_trainset_bal.csv"

learned_inc_cf = "learned_trainset_inc_cf.csv"

original_train_bal = 'bal_sheet_example.csv'
original_train_inc_cf = 'income_&_cashflow_example.csv'

def ticker_list(directory):
    tiks=set()
    for f in os.listdir(directory):
        fname = f.lower()
        fname = fname.split("_data")
        t = fname[0].split("_")[-1] # tickers
        if len(t)<=4:
            tiks.add(t)

    for t in tiks:
        print(t)

    answer = input("Select ticker ")
    return answer

def create_empty_csv_same_header(original_csv, new_csv_same_header):
    df_bal = pd.read_csv(original_csv)
    # Write only the header row
    df_bal.head(0).to_csv(new_csv_same_header, index=False)
    return new_csv_same_header    

# parser
def parse_args():
    parser = argparse.ArgumentParser(description="New data or archive?")
    parser.add_argument("--data", help="run complete pipeline or get old data, choose new or archive", default=None)
    parser.add_argument("--ticker", help="ticker to search in archive, type ticker like aapl", default=None)
    parser.add_argument("--confidence_min", help="minimum confidence threshold, number between 1 and 0, float", default = None)
    parser.add_argument("--confidence_max", help="maximum confidence threshold, number between 1 and confidence_min", default = None)
    parser.add_argument("--train_new", help="option to train on new data - yes or no", default = None)

    args, _ = parser.parse_known_args()

    while not args.data:
        answer = input("Classify archive data - stored locally (type: archive) or scrape new data from SEC (type: new)? ")
        if "new" in answer:
            args.data=1
            break
        elif "archive" in answer:
            args.data=0
            break
        else:
            print("Error: select data")

    answer_ticker = ""
    found = False
    while args.data==0 and not found:
        if args.ticker==None:
            answer_ticker = input("Provide ticker of company to retrieve locally stored data or ask for list of selectable tickers ")
            if answer_ticker == "list":
                answer_ticker = ticker_list(W3_DIR)
        elif args.ticker=="list":
            answer_ticker = ticker_list(W3_DIR)
        else:
            answer_ticker=args.ticker

        for f in os.listdir(W3_DIR):
            if answer_ticker.strip() in f:
                print("Found file")
                found = True
                args.ticker = answer_ticker
                break

        if not found:
            print(f"File not found for ticker '{answer_ticker}'. Try again.")

    while args.confidence_min is None:
        answer_min = input("Give minimum confidence threshold for model predictions to flag those that fall below it for manual review")
        try:
            threshold_min = float(answer_min)
            if threshold_min < 1 and threshold_min > 0:
                args.confidence_min = threshold_min
            else:
                print("Expecting value between 1 and 0")
        except:
            print("Expecting value between 1 and 0")

    while args.confidence_max is None:
        answer_max = input("Give maximum confidence threshold for model predictions to add those that are above it to learned trainset for improving future predictions")
        try:
            threshold_max = float(answer_max)
            if threshold_max < 1 and threshold_max > args.confidence_min:
                args.confidence_max = threshold_max
            else:
                print("Expecting value between 1 and minimum confidence ")
        except:
            print("Expecting value between 1 and minimum confidence ")

    while args.train_new is None:
        if os.path.exists(learned_bal) and os.path.exists(learned_inc_cf):
            answer_option = input("Train with datasets self-generated from previously iterations? ")
            if answer_option == "yes":
                args.train_new=1
                break
            elif answer_option == "no":
                args.train_new = 0
                break
            else:
                answer_option = input("Train with datasets self-generated from previously iterations? ")
        else:
            args.train_new = 0
            break

    return args

def prepare_label_for_embedding(label):
    # Insert spaces before capital letters in camelCase
    spaced_label = re.sub(r'([a-z])([A-Z])', r'\1 \2', label)
    return spaced_label

def generate_embeddings(labels, model_name=MODEL):
    # Load the pre-trained model
    model = SentenceTransformer(model_name)

    # Prepare labels (break camelCase into words)
    prepared_labels = [prepare_label_for_embedding(label) for label in labels]

    # Generate embeddings
    # batch_size: process multiple at once for efficiency
    embeddings = model.encode(prepared_labels, batch_size=32, convert_to_numpy=True)

    return embeddings, model

# classify categories
def cluster_labels_by_category(train_df, test_df, n_clusters=None, model_name=MODEL, clustering_method=clustering_method):
    # uses kmeans only
    # STEP 1: Generate embeddings for training data
    print("Generating embeddings for training data...")
    train_embeddings, model = generate_embeddings(train_df['label'], model_name)

    # STEP 2: Determine optimal number of clusters if not specified
    if n_clusters is None:
        # If training data has category labels, use unique count as guide
        if 'category' in train_df.columns:
            n_clusters = train_df['category'].nunique()
            print(f"Auto-detected {n_clusters} clusters from training categories")
        else:
            # Fallback: use simple heuristic
            n_clusters = max(2, int(len(train_df) ** 0.5))
            print(f"Using heuristic: {n_clusters} clusters")

    # STEP 3: Fit clustering algorithm on training data
    print(f"Clustering training data ({clustering_method})...")


    clusterer = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    train_clusters = clusterer.fit_predict(train_embeddings)


    # STEP 4: Generate embeddings for test data using the SAME model
    print("Generating embeddings for test data...")
    test_embeddings = model.encode(
        [prepare_label_for_embedding(label) for label in test_df['label']], 
        batch_size=32, 
        convert_to_numpy=True
    )

    # STEP 5: Assign test data to nearest cluster

    test_clusters = clusterer.predict(test_embeddings)
    # Calculate distance from each point to its assigned cluster center
    test_distances = np.min(
        cdist(test_embeddings, clusterer.cluster_centers_, metric='cosine'),
        axis=1
    )

    # STEP 6: Convert cluster numbers to readable category names
    # Map cluster IDs to labels (optional but useful)
    cluster_to_category = {}
    for cluster_id in set(train_clusters):
        # Use the most common training label in this cluster as the name
        mask = train_clusters == cluster_id
        sample_labels = train_df[mask]['label'].values
        cluster_to_category[cluster_id] = f"Cluster_{cluster_id}"
        print(f"  {cluster_to_category[cluster_id]}: {len(sample_labels)} training items")

    # If training data has category labels, try to map clusters to them
    category_mapping = None
    if 'category' in train_df.columns:
        # Assign each cluster to the category it most overlaps with
        category_mapping = {}
        for cluster_id in set(train_clusters):
            mask = train_clusters == cluster_id
            most_common_category = train_df[mask]['category'].mode()
            if len(most_common_category) > 0:
                category_mapping[cluster_id] = most_common_category[0]

        # STEP 7: MAP test clusters to category names (THIS WAS MISSING!)
    test_categories = None
    if category_mapping is not None:
        test_categories = np.array([category_mapping.get(cluster_id, f"Cluster_{cluster_id}") for cluster_id in test_clusters])

    return {
        'clusterer': clusterer,
        'model': model,
        'train_embeddings': train_embeddings,
        'test_embeddings': test_embeddings,
        'train_clusters': train_clusters,
        'test_clusters': test_clusters,
        'test_categories' : test_categories,
        'test_distances': test_distances,
        'n_clusters': n_clusters,
        'cluster_to_category': cluster_to_category,
        'category_mapping': category_mapping,
        'method': clustering_method
    }

# classify statement type
def classify_statement_type_hybrid(train_df, test_df, model_name='all-MiniLM-L6-v2'):
    print("Classifying statement type (income vs cashflow) using clustering...")

    # Generate embeddings
    train_embeddings, model = generate_embeddings(train_df['label'], model_name)

    # Cluster into exactly 2 groups
    clusterer = KMeans(n_clusters=2, random_state=42, n_init=10)
    train_clusters = clusterer.fit_predict(train_embeddings)

    # Map clusters to statement types
    # Determine which cluster corresponds to "income" vs "cashflow"
    cluster_0_statements = train_df[train_clusters == 0]['statement'].unique()
    cluster_1_statements = train_df[train_clusters == 1]['statement'].unique()

    # Simple heuristic: whichever cluster has more "income" labels = income cluster
    cluster_to_statement = {}
    if list(train_df[train_clusters == 0]['statement']).count('income') > \
       list(train_df[train_clusters == 1]['statement']).count('income'):
        cluster_to_statement[0] = 'income'
        cluster_to_statement[1] = 'cashflow'
    else:
        cluster_to_statement[0] = 'cashflow'
        cluster_to_statement[1] = 'income'

    # Embed and predict test data
    test_embeddings = model.encode(
        [prepare_label_for_embedding(label) for label in test_df['label']], 
        batch_size=32, 
        convert_to_numpy=True
    )

    test_clusters = clusterer.predict(test_embeddings)
    test_statements = [cluster_to_statement[c] for c in test_clusters]

    # Confidence: inverse of normalized distance to cluster center
    # (closer to center = more confident)
    distances = np.min(
        cdist(test_embeddings, clusterer.cluster_centers_, metric='cosine'),
        axis=1
    )

    confidences = 1 - distances  # Scale to 0-1 range

    return {
        'predictions': np.array(test_statements),
        'confidences': confidences,
        'clusterer': clusterer,
        'model': model,
        'cluster_to_statement': cluster_to_statement
    }

#uncertain predictions 
def flag_uncertain_predictions(original_train_df, annotated_test_df, 
                             confidence_threshold=0.5, output_file=None):

    if 'statement' in annotated_test_df.columns:
        # income/cashflow case - if either statement or category confidence is below threshold
        uncertain_mask = (
            (annotated_test_df['statement_confidence'] < confidence_threshold) |
            (annotated_test_df['prediction_confidence'] < confidence_threshold)
        )
    else:
        # balance sheet case: check if category confidence is below threshold
        uncertain_mask = annotated_test_df['prediction_confidence'] < confidence_threshold

    # copy uncertain predictions into a separate file
    uncertain_df = annotated_test_df[uncertain_mask].copy()

    # if there re no uncertain predictions, return the original dataset
    if len(uncertain_df) == 0:
        print(f"✓ No uncertain predictions found (threshold: {confidence_threshold})")
        return pd.DataFrame()

    # Sort by confidence (lowest first) so highest priority uncertain cases appear first
    if 'statement' in uncertain_df.columns:
        # Use minimum confidence of both columns
        uncertain_df['min_confidence'] = uncertain_df[['statement_confidence', 'prediction_confidence']].min(axis=1)
        uncertain_df = uncertain_df.sort_values('min_confidence')
        uncertain_df = uncertain_df.drop(columns=['min_confidence'])
    else:
        uncertain_df = uncertain_df.sort_values('prediction_confidence')

    #summary
    print(f"\n⚠ Found {len(uncertain_df)} uncertain predictions (threshold: {confidence_threshold})")
    print(f"  Require manual review and annotation.\n")

    # Select columns to display
    cols_to_display = ['label', 'value']
    if 'statement' in uncertain_df.columns:
        cols_to_display.extend(['statement', 'statement_confidence', 'category', 'prediction_confidence'])
    else:
        cols_to_display.extend(['category', 'prediction_confidence'])

    print(uncertain_df[cols_to_display].to_string(index=False))

    # Save to CSV if output file specified
    if output_file:
        uncertain_df.to_csv(output_file, index=False)
        print(f"\n✓ Uncertain predictions saved to: {output_file}")
        print(f"  Please review and manually annotate these predictions.")

    return uncertain_df

# certain  predictions above 0.8 confidence threshold are appended to training csv
# f'nlp_cf_{ticker}.csv' is nlp, nlp_bal_{ticker).csv f'nlp_inc_{ticker}.csv' is nlp_csv
# bal_sheet_example.csv and income_&_cashflow_example.csv is example
def add_certain_predictions(train_df, test_df,  confidence_threshold, output_file=None):
    annotated_test_df = test_df
    original_train_df = train_df
    if 'statement' in annotated_test_df.columns:
        # income/cashflow case - if either statement or category confidence is below threshold
        certain_mask = (
            (annotated_test_df['statement_confidence'] >= confidence_threshold) &
            (annotated_test_df['prediction_confidence'] >= confidence_threshold)
        )
    else:
        # balance sheet case: check if category confidence is below threshold
        certain_mask = annotated_test_df['prediction_confidence'] >= confidence_threshold

    # copy uncertain predictions into a separate file
    certain_df = annotated_test_df[certain_mask].copy()

    # if there re no uncertain predictions, return the original dataset
    if len(certain_df) == 0:
        if "bal" in train_df:
            print(f"✓ No certain predictions found for balance sheet! (threshold {confidence_threshold})")
        else:
            print(f"✓ No certain predictions found for income and cashflow statements! (threshold {confidence_threshold})")
        return pd.DataFrame()

    # Sort by confidence (lowest first) so highest priority uncertain cases appear first
    if 'statement' in certain_df.columns:
        # Use mean confidence of both columns
        certain_df['max_confidence'] = certain_df[['statement_confidence', 'prediction_confidence']].mean(axis=1)
        certain_df = certain_df.sort_values('max_confidence')
        certain_df = certain_df.drop(columns=['max_confidence'])
    else:
        certain_df = certain_df.sort_values('prediction_confidence')

    #summary
    if "bal" in train_df:
        print(f"\n⚠ Found {len(certain_df)} certain predictions for balance sheet labels (threshold: {confidence_threshold})")
    else:
        print(f"\n⚠ Found {len(certain_df)} certain predictions for income and cashflow statements labels (threshold: {confidence_threshold})")


    new_train_df = pd.concat([original_train_df, certain_df], ignore_index=True)

    return new_train_df

def separate_income_cashflow(ticker):

    df = pd.read_csv(f'nlp_inc_cf_{ticker}_data.csv')

    # Filter by statement type
    income_df = df[df['statement'].str.lower() == 'income'].copy()
    cashflow_df = df[df['statement'].str.lower() == 'cashflow'].copy()

    # drop the 'statement' column
    income_df = income_df.drop(columns=['statement'])
    cashflow_df = cashflow_df.drop(columns=['statement'])

    # sort by category and value so that it resembles proper format
    income_df = income_df.sort_values(by=['category', 'value']).reset_index(drop=True)
    cashflow_df = cashflow_df.sort_values(by=['category', 'value']).reset_index(drop=True)

    return income_df, cashflow_df

def main():

    args = parse_args()

    ticker = ""

    # Run previous pipeline steps
    if args.data==1:
        ticker = SortCxt.main()
        bal_sheet_test = pd.read_csv(f'bal_sheet_{ticker}_data.csv') 
        income_cashflow_test = pd.read_csv(f'inc_cf_{ticker}_data.csv')

    elif args.data==0:
        ticker = args.ticker
        # need to access it from this dir:./sorted_inc&cf_bal_data_W3
        bal_sheet_test = pd.read_csv(os.path.join(W3_DIR, f'bal_sheet_{ticker}_data.csv'))
        income_cashflow_test = pd.read_csv(os.path.join(W3_DIR, f'inc_cf_{ticker}_data.csv'))


    confidence_threshold_min = args.confidence_min

    confidence_threshold_max = args.confidence_max

    # task 1
    # get training dataset for balance sheet # label, value, category
    if args.train_new==1:
        bal_sheet_train = pd.read_csv(learned_bal)
    else:
        bal_sheet_train = pd.read_csv(original_train_bal)

    bal_categories = bal_sheet_train["category"].nunique()

    # Use number of categories in training data as a guide
    bal_categories_results = cluster_labels_by_category(
        train_df=bal_sheet_train,
        test_df=bal_sheet_test,
        n_clusters=bal_categories,
        model_name='all-MiniLM-L6-v2'
    )

    # Add cluster assignments to test data
    bal_sheet_test['category'] = bal_categories_results['test_categories'].astype(str)
    bal_sheet_test['prediction_confidence'] = 1 - bal_categories_results['test_distances']

    # If category_mapping exists, map cluster IDs to actual category names
    if bal_categories_results['category_mapping']:
        bal_sheet_test['category'] = bal_sheet_test['category'].map(
            bal_categories_results['category_mapping']
        ).fillna(bal_sheet_test['category'])

    # Sort by category and value
    bal_sheet_test = bal_sheet_test.sort_values(by=['category', 'value']).reset_index(drop=True)

    # save annotated balance sheet file
    bal_sheet_test.to_csv(f'nlp_bal_sheet_{ticker}_data.csv', index=False)

    # task 2
    # get training dataset for income and cashflow statement # label, value, statement, category
    if args.train_new==1 and os.path.getsize(learned_inc_cf) > 0:
        income_cashflow_train = pd.read_csv(learned_inc_cf)
    else:
        income_cashflow_train = pd.read_csv(original_train_inc_cf)

    # get test dataset # label, value
    # income_cashflow_test = pd.read_csv(f'inc_cf_{ticker}_data.csv')
    income_categories = income_cashflow_train[income_cashflow_train['statement'] == 'income']['category'].nunique()
    cashflow_categories = income_cashflow_train[income_cashflow_train['statement'] == 'cashflow']['category'].nunique()
    statement_categories = income_categories + cashflow_categories

    statement_type_results = classify_statement_type_hybrid( 
        train_df=income_cashflow_train[['label', 'statement']],
        test_df=income_cashflow_test
    )

    income_cashflow_test['statement'] = statement_type_results['predictions']
    income_cashflow_test['statement_confidence'] = statement_type_results['confidences']

    statement_categories_results = cluster_labels_by_category(
        train_df=income_cashflow_train[['label', 'category']],
        test_df=income_cashflow_test,
        n_clusters=statement_categories,
        model_name='all-MiniLM-L6-v2'
    )

    # Add cluster assignments to test data
    income_cashflow_test['category'] = statement_categories_results['test_categories'].astype(str)
    income_cashflow_test['prediction_confidence'] = 1 - statement_categories_results['test_distances']

    # If category_mapping exists, map cluster IDs to actual category names
    if statement_categories_results['category_mapping']:
        income_cashflow_test['category'] = income_cashflow_test['category'].map(
            statement_categories_results['category_mapping']
        ).fillna(income_cashflow_test['category'])

    # Sort by category and value
    income_cashflow_test = income_cashflow_test.sort_values(by=['category', 'value']).reset_index(drop=True)

    # save annotated balance sheet file
    income_cashflow_test.to_csv(f'nlp_inc_cf_{ticker}_data.csv', index=False)

    # get df's for income and cashflow
    income_df, cashflow_df = separate_income_cashflow(ticker)

    # write to separate csv's income and cashflow
    income_df.to_csv(f'nlp_inc_{ticker}.csv', index=False)
    print(f"Income statement: {len(income_df)} rows in nlp_inc_{ticker}.csv")

    cashflow_df.to_csv(f'nlp_cf_{ticker}.csv', index=False)
    print(f"Cashflow statement: {len(cashflow_df)} rows in nlp_cf_{ticker}.csv")

    # Balance sheet uncertain predictions
    bal_sheet_uncertain = flag_uncertain_predictions(
        bal_sheet_train,
        bal_sheet_test,
        confidence_threshold=confidence_threshold_min,
        output_file=f'uncertain_bal_sheet_{ticker}.csv'
    )

    # Income/cashflow uncertain predictions
    inc_cf_uncertain = flag_uncertain_predictions(
        income_cashflow_train,
        income_cashflow_test,
        confidence_threshold=confidence_threshold_min,
        output_file=f'uncertain_inc_cf_{ticker}.csv'
    )

    # add high confidence data for learning
    new_bal_trainset = add_certain_predictions(bal_sheet_train, bal_sheet_test,  confidence_threshold_max, output_file=None)
    new_inc_cf_trainset = add_certain_predictions(income_cashflow_train, income_cashflow_test, confidence_threshold_max, output_file=None)

    if len(new_bal_trainset) > 0:
        if not os.path.exists(learned_bal):
            new_bal= pd.concat([bal_sheet_train, new_bal_trainset], ignore_index=True)
            new_bal = new_bal[bal_sheet_train.columns]
            new_bal_trainset.to_csv(learned_bal, index=False)
        else:
            existing_bal = pd.read_csv(learned_bal)
            updated_bal = pd.concat([existing_bal, new_bal_trainset], ignore_index=True)
            updated_bal = updated_bal[bal_sheet_train.columns]
            updated_bal.to_csv(learned_bal, index=False)
            print(f"Updated {learned_bal} with {len(new_bal_trainset)} new rows")

    if len(new_inc_cf_trainset) > 0:
        if not os.path.exists(learned_inc_cf):
            new_inc_cf = pd.concat([income_cashflow_train, new_inc_cf_trainset], ignore_index=True)
            new_inc_cf = new_inc_cf[income_cashflow_train.columns]
            new_inc_cf_trainset.to_csv(learned_inc_cf, index=False)
            print(f"Created {learned_inc_cf} with {len(new_inc_cf_trainset)} rows")
        else:
            existing_inc = pd.read_csv(learned_inc_cf)
            updated_inc = pd.concat([existing_inc, new_inc_cf_trainset], ignore_index=True)
            updated_inc = updated_inc[income_cashflow_train.columns]
            updated_inc.to_csv(learned_inc_cf, index=False)
            print(f"Updated {learned_inc_cf} with {len(new_inc_cf_trainset)} new rows")      

    return ticker

if __name__ == "__main__":
    main()         

