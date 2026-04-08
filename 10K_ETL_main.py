#!/usr/bin/env python
# coding: utf-8

# In[1]:


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

import os
import shutil

# for fetching previosu pipeline steps
import importlib

# previous pipeline step
import NLP_Sort_10K_W4 as NLP

# updated
importlib.reload(NLP)

# run pipeline, clean up

def organize_files_after_run(ticker, new_dir, files_to_move):
    
    os.makedirs(new_dir, exist_ok=True)
    
    # List of files to move (adjust these to match your actual filenames)
    
    # Move each file into the new directory
    for file in files_to_move:
        source = file
        destination = os.path.join(new_dir, file)
        
        if os.path.exists(source):
            shutil.move(source, destination)
            print(f"Moved: {source} → {destination}")
        else:
            print(f"File not found: {source}")
    
    print(f"Done! Files moved to '{new_dir}'")

def main():

    ticker = NLP.main()
    
    new_dir_W1= "parsed_xbrl_data_W1"
    # SEC_contextRefs_{ticker}.csv
    # sec_xbrl_content_{ticker}.csv
    # sec_xbrl_contexts_{ticker}.csv
    # sec_xbrl_facts_{ticker}.csv
    # sec_xbrl_values_{ticker}.csv
    files_W1=[f"SEC_contextRefs_{ticker}.csv", f"sec_xbrl_content_{ticker}.csv", f"sec_xbrl_contexts_{ticker}.csv", f"sec_xbrl_facts_{ticker}.csv", f"sec_xbrl_values_{ticker}.csv"]

    new_dir_W2 = "merged_data_W2"
    # merged_sec_xbrl_{ticker}.csv
    files_W2 = [f"merged_sec_xbrl_{ticker}.csv"]

    new_dir_W3 = "sorted_inc&cf_bal_data_W3"
    #inc_cf_{ticker}_data.csv
    #bal_sheet_{ticker}_data.csv
    #{ticker}_data.csv
    files_W3 = [f"inc_cf_{ticker}_data.csv", f"bal_sheet_{ticker}_data.csv", f"{ticker}_data.csv"]
    
    new_dir_W4 = "nlp_classified_inc_cf_bal_data_W4"
    #uncertain_bal_sheet_{ticker}.csv
    #uncertain_inc_cf_{ticker}.csv
    #nlp_inc_cf_{ticker}.csv
    #nlp_inc_{ticker}.csv
    #nlp_cf_{ticker}.csv
    #nlp_bal_sheet_{ticker}_data.csv
    files_W4 = [f"uncertain_bal_sheet_{ticker}.csv", f"uncertain_inc_cf_{ticker}.csv", f"nlp_inc_cf_{ticker}.csv", f"nlp_inc_{ticker}.csv", f"nlp_cf_{ticker}.csv", f"nlp_bal_sheet_{ticker}_data.csv"]

    organize = [(new_dir_W1, files_W1), (new_dir_W2, files_W2), (new_dir_W3, files_W3), (new_dir_W4, files_W4)]

    for n_d, f in organize:
        organize_files_after_run(ticker, n_d, f)
    
if __name__ == "__main__":
    main()         

