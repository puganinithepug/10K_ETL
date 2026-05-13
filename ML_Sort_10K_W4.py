#!/usr/bin/env python
# coding: utf-8

# In[9]:


import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import MultinomialNB
from sklearn.tree import DecisionTreeClassifier
from sklearn.svm import LinearSVC
from sklearn.metrics import confusion_matrix
from sklearn.calibration import CalibratedClassifierCV

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

import matplotlib_inline

# for fetching previosu pipeline steps
import importlib

# previous pipeline step
import Sort_10K_by_Context_W3 as SortCxt

# updated
importlib.reload(SortCxt)

# options:
# word embeddings
# bag-of-words
# tf idf, confusion matrix to pick best classifier for csv annotation 

# using NLP for:

# task 1 - nlp
# use bal_sheet_example.csv for training
# copy bal_sheet_{ticker}_data.csv to nlp_bal_sheet_{ticker}_data.csv 
# annotate nlp_bal_sheet_{ticker}_data.csv with category column based on training 
# if there are labels in the nlp_bal_sheet_{ticker}_data.csv that are not present in the bal_sheet_example.csv, add (label, value, category) to the bal_sheet_example.csv where category is hypothesized

# task 2
# use income_&_cashflow_example.csv for training 
# copy inc_cf_{ticker}.csv to nlp_inc_cf_{ticker}.csv 
# annotate nlp_inc_cf_{ticker}.csv with statement column and category column based on training 
# if there are labels in the nlp_inc_cf_{ticker}.csv that are not present in the income_&_cashflow_example.csv, add (label, value, category) to the income_&_cashflow_example.csv where category is hypothesized

# task 3 - no nlp
# separate nlp_inc_cf_{ticker}.csv into two csvs: nlp_inc_{ticker}.csv and nlp_cf_{ticker}.csv based on statement column (if "income" -> nlp_inc_{ticker}.csv, if "cashflow" -> nlp_cf_{ticker}.csv)

# task 4 - no nlp
# reconstruct balance sheet from nlp_bal_sheet_{ticker}_data.csv, income statement from nlp_inc_{ticker}.csv, cashflow statement from nlp_cf_{ticker}.csv
# by placing items with the same value in category column together, ordered by size of value (smaller value first -> biggest listed last)

# parser
def parse_args():
    parser = argparse.ArgumentParser(description="Get confidence threshold")
    parser.add_argument("--confidence", help="confidence threshold", default=None)

    args, _ = parser.parse_known_args()

    while True:
        if not args.confidence:
            args.confidence = input("Confidence threshold (0.0-1.0): ")

        try:
            confidence_value = float(args.confidence)

            if 0.0 <= confidence_value <= 1.0:
                args.confidence = confidence_value
                break
            else:
                print("Error: Confidence threshold must be between 0 and 1")
                args.confidence = None  # Reset to retry

        except ValueError:
            print("Error: Enter a numeric value (e.g., 0.5)")
            args.confidence = None  # Reset to retry

    return args

def camelcase_tokenizer(text):
    # Split on camelCase boundaries
    tokens = re.findall(r'[A-Z]+(?=[A-Z][a-z]|\b)|[A-Z][a-z]+', text)
    return ' '.join(tokens)

def classify_income_cashflow_statement_type(train_df, test_df):
    # input:
    #     train_df: DataFrame with columns ['label', 'value', 'statement', 'category']
    #               (from income_&_cashflow_example.csv)
    #     test_df: DataFrame with columns ['label', 'value']

    # output:
    #     dictionary with classifier and "statement" predictions

    vectorizer = TfidfVectorizer(
        # since label items look like this: IncrementalCommonSharesAttributableToShareBasedPaymentArrangements
        tokenizer=camelcase_tokenizer,
        lowercase=False,
        min_df=1,           
        ngram_range=(1, 15)
    )

    X_full = vectorizer.fit_transform(train_df['label'])
    y_full = train_df['statement']  # "income" or "cashflow"

    # split into training and validation data
    X_train, X_val, y_train, y_val = train_test_split(X_full, y_full, test_size=0.3, random_state=0)

    # choose best for binary classification
    classifiers = {
        "LogisticRegression": LogisticRegression(random_state=0, max_iter=1000),
        #"LinearSVC": CalibratedClassifierCV(LinearSVC(random_state=0, max_iter=2000, dual=False), cv=2)
    }

    results = {}
    best_val_accuracy = -1
    best_classifier_name = None
    best_model = None

    for name, clf in classifiers.items():
        # Train on training set
        clf.fit(X_train, y_train)

        # Evaluate on validation set (unseen during training)
        val_accuracy = clf.score(X_val, y_val)

        results[name] = {
            'model': clf,
            'train_accuracy': clf.score(X_train, y_train),
            'val_accuracy': val_accuracy
        }

        print(f"{name}: train={clf.score(X_train, y_train):.4f}, val={val_accuracy:.4f}")

        if val_accuracy > best_val_accuracy:
            best_val_accuracy = val_accuracy
            best_classifier_name = name
            best_model = clf

    # Retrain best model on full training data
    best_model.fit(X_full, y_full)

    X_test = vectorizer.transform(test_df['label'])
    test_predictions = best_model.predict(X_test)
    test_probabilities = best_model.predict_proba(X_test)

    return {
        "best_classifier": best_classifier_name,
        "best_model": best_model,
        "vectorizer": vectorizer,
        "predictions": test_predictions,
        "probabilities": test_probabilities,
        "results": results,
        "val_accuracy": best_val_accuracy
    }

def classify_income_cashflow_bal_category(train_df, test_df): 
    # input:
    #     train_df: DataFrame with columns ['label', 'value', 'category']
    #               (from bal_sheet_example.csv)
    #     test_df: DataFrame with columns ['label', 'value'] 
    #              (from bal_sheet_{ticker}_data.csv, no category yet)

    # output:
    #     dictionary with best classifier, vectorizer, and predictions

    vectorizer = TfidfVectorizer(
        # since label items look like this: IncrementalCommonSharesAttributableToShareBasedPaymentArrangements
        tokenizer=camelcase_tokenizer,
        lowercase=False,
        min_df=1,           
        ngram_range=(1, 15)
    )

    # step 1 - data
    X_full = vectorizer.fit_transform(train_df['label'])
    y_full = train_df['category']

    # split: 70% train, 30% validate
    X_train, X_val, y_train, y_val = train_test_split(X_full, y_full, test_size=0.3, random_state=0)

    # step 2 - classifiers
    classifiers = {
        "LogisticRegression": LogisticRegression(random_state=0, max_iter=1000),
        "MultinomialNB": MultinomialNB(),
        "DecisionTreeClassifier": DecisionTreeClassifier(random_state=0, max_depth=5),
        #"LinearSVC": CalibratedClassifierCV(LinearSVC(random_state=0, max_iter=2000, dual=False), cv=2)
    }

    # step 3 - train and validate    
    results = {}
    best_val_accuracy = -1
    best_classifier_name = None
    best_model = None

    for name, clf in classifiers.items():
        # train on training set
        clf.fit(X_train, y_train)

        val_accuracy = clf.score(X_val, y_val)

        results[name] = {
            'model': clf,
            'train_accuracy': clf.score(X_train, y_train),
            'val_accuracy': val_accuracy
        }
        print(f"{name}: train={clf.score(X_train, y_train):.4f}, val={val_accuracy:.4f}")

        # pick best classifier
        if val_accuracy > best_val_accuracy:
            best_val_accuracy = val_accuracy
            best_classifier_name = name
            best_model = clf

    # retrain best model on full data set
    best_model.fit(X_full, y_full)

    # step 4 - predict on test data
    X_test = vectorizer.transform(test_df['label'])
    test_predictions = best_model.predict(X_test)

    # step 5 - prediction probabilities - to flag uncertain predictions
    test_probabilities = best_model.predict_proba(X_test)

    return {
        "best_classifier": best_classifier_name,
        "best_model": best_model,
        "vectorizer": vectorizer,
        "predictions": test_predictions,
        "probabilities": test_probabilities,
        "results": results,
        "training_accuracy": best_val_accuracy
    }

def flag_uncertain_predictions(original_train_df, annotated_test_df, 
                             confidence_threshold=0.5, output_file=None):
    # input:
    #     original_train_df: original training CSV (for reference only)
    #     annotated_test_df: annotated test CSV with predictions and confidence scores
    #     confidence_threshold: predictions below this threshold are flagged as uncertain
    #     output_file: path to save uncertain predictions CSV

    # output:
    #     DataFrame containing only uncertain predictions

    # identify uncertain predictions
    if 'statement' in annotated_test_df.columns:
        # income/cashflow case - if either statement or category confidence is below threshold
        uncertain_mask = (
            (annotated_test_df['statement_confidence'] < confidence_threshold) |
            (annotated_test_df['category_confidence'] < confidence_threshold)
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
        uncertain_df['min_confidence'] = uncertain_df[['statement_confidence', 'category_confidence']].min(axis=1)
        uncertain_df = uncertain_df.sort_values('min_confidence')
        uncertain_df = uncertain_df.drop(columns=['min_confidence'])
    else:
        uncertain_df = uncertain_df.sort_values('prediction_confidence')

    #summary
    print(f"\n⚠ Found {len(uncertain_df)} uncertain predictions (threshold: {confidence_threshold}):")
    print(f"  Require manual review and annotation.\n")

    # Select columns to display
    cols_to_display = ['label', 'value']
    if 'statement' in uncertain_df.columns:
        cols_to_display.extend(['statement', 'statement_confidence', 'category', 'category_confidence'])
    else:
        cols_to_display.extend(['category', 'prediction_confidence'])

    print(uncertain_df[cols_to_display].to_string(index=False))

    # Save to CSV if output file specified
    if output_file:
        uncertain_df.to_csv(output_file, index=False)
        print(f"\n✓ Uncertain predictions saved to: {output_file}")
        print(f"  Please review and manually annotate these predictions.")

    return uncertain_df

def separate_income_cashflow(ticker):

    # split nlp_inc_cf_{ticker}.csv into two files based on 'statement' column.

    df = pd.read_csv(f'nlp_inc_cf_{ticker}.csv')

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

    # Run previous pipeline steps
    ticker = SortCxt.main()

    args = parse_args()

    confidence_threshold = float(args.confidence)

    # task 1
    # get training dataset for balance sheet # label, value, category
    bal_sheet_train = pd.read_csv('bal_sheet_example.csv')

    # print("Testing tokenizer on first 5 labels:\n")
    # for i, label in enumerate(bal_sheet_train['label'].head()):
    #     tokens = camelcase_tokenizer(label)
    #     print(f"{i+1}. {label}")
    #     print(f"   Tokens: {tokens}")
    #     print(f"   Count: {len(tokens)}\n")

    # get test dataset # label, value
    bal_sheet_test = pd.read_csv(f'bal_sheet_{ticker}_data.csv') 

    # classify labels by balance sheet categories
    bal_sheet_results = classify_income_cashflow_bal_category(bal_sheet_train, bal_sheet_test)

    # add predictions to test data (balance sheet)
    bal_sheet_test['category'] = bal_sheet_results['predictions']
    bal_sheet_test['prediction_confidence'] = bal_sheet_results['probabilities'].max(axis=1)

    # sort by category and value so that it resembles proper format
    bal_sheet_test= bal_sheet_test.sort_values(by=['category', 'value']).reset_index(drop=True)

    # save annotated balance sheet file
    bal_sheet_test.to_csv(f'nlp_bal_sheet_{ticker}_data.csv', index=False)

    # task 2
    # get training dataset for income and cashflow statement # label, value, statement, category
    income_cashflow_train = pd.read_csv('income_&_cashflow_example.csv')

    # get test dataset # label, value
    income_cashflow_test = pd.read_csv(f'inc_cf_{ticker}_data.csv')

    # classify statement type
    statement_results = classify_income_cashflow_statement_type(income_cashflow_train, income_cashflow_test)
    income_cashflow_test['statement'] = statement_results['predictions']
    income_cashflow_test['statement_confidence'] = statement_results['probabilities'].max(axis=1)

    # classify category
    category_results = classify_income_cashflow_bal_category(income_cashflow_train, income_cashflow_test)
    income_cashflow_test['category'] = category_results['predictions']
    income_cashflow_test['category_confidence'] = category_results['probabilities'].max(axis=1)

    # save annotated file
    income_cashflow_test.to_csv(f'nlp_inc_cf_{ticker}.csv', index=False)

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
        confidence_threshold=confidence_threshold,
        output_file=f'uncertain_bal_sheet_{ticker}.csv'
    )

    # Income/cashflow uncertain predictions
    inc_cf_uncertain = flag_uncertain_predictions(
        income_cashflow_train,
        income_cashflow_test,
        confidence_threshold=confidence_threshold,
        output_file=f'uncertain_inc_cf_{ticker}.csv'
    )

    return ticker

if __name__ == "__main__":
    main()         


