import requests
import re
import pandas as pd
import unicodedata
import os
import warnings

import logging

import argparse

import math

import matplotlib_inline

import importlib

#get parser/scraper 
import Scrape_Parse_10K_W1 as SS10K


#for refreshing SS10K to have the latest version if is amended
importlib.reload(SS10K)

# for parsing csv
import csv
#defaultdict - providing a default value for keys that do not yet exist when they are accessed.
from collections import defaultdict

dict_csvs = {}

#helper to fetch csv file by their names from pwd
def csvs_from_pwd(csv_files):
    """Populate dict_csvs with paths to CSV files"""
    cur_dir_path = os.getcwd()
    
    for csv_file in csv_files:
        full_path = os.path.join(cur_dir_path, csv_file)
        
        if os.path.exists(full_path):
            dict_csvs[csv_file] = full_path
            print(f"✓ Added to dict_csvs: {csv_file}")
        else:
            print(f"✗ File not found: {csv_file}")

            
# helper to search in CSV for values needed
def merge_CSV(ticker):
    data_facts = None
    data_context = None
    # Try to build full paths manually if not in dict
    if f"sec_xbrl_facts_{ticker}.csv" in dict_csvs:
        full_path_facts = dict_csvs[f"sec_xbrl_facts_{ticker}.csv"]
    else:
        full_path_facts = None
    
    if f"sec_xbrl_contexts_{ticker}.csv" in dict_csvs:
        full_path_contexts = dict_csvs[f"sec_xbrl_contexts_{ticker}.csv"]
    else:
        full_path_contexts = None
        
    if full_path_facts:
        data_facts = pd.read_csv(full_path_facts)

    if full_path_contexts:
        data_context = pd.read_csv(full_path_contexts)
    
    # data_facts.columns = ['tag_prefix', 'tag_local', 'gaap_candidate', 'contextRef', 'unitRef', 'decimals', 'value_raw']
    # data_context.columns = ['contextRef', 'entity_identifier', 'period_start', 'period_end', 'instant']

    if data_facts is not None and data_context is not None:
    
        CommonCols = [col for col in data_facts.columns if col in data_context.columns]
        data = pd.merge(data_facts, data_context, on=CommonCols )
        #data = data.drop(columns=[""])
        
        merged_path = f"merged_sec_xbrl_{ticker}.csv"
        data.to_csv(merged_path, index=False)
        cur_dir_path = os.getcwd()
        full_path = os.path.join(cur_dir_path, merged_path)
        dict_csvs[merged_path] = full_path
        #match contextrefs from contexts to facts
    
        return merged_path
        
    elif data_facts is not None:
        print(f"Only sec_xbrl_facts_{ticker}.csv available" )
        data = data_facts
        merged_path = f"merged_sec_xbrl_{ticker}.csv"
        data.to_csv(merged_path, index=False)
        cur_dir_path = os.getcwd()
        full_path = os.path.join(cur_dir_path, merged_path)
        dict_csvs[merged_path] = full_path
        return merged_path
        
    elif data_context is not None:
        print(f"Only sec_xbrl_contexts_{ticker}.csv available" )

        data = data_context
        merged_path = f"merged_sec_xbrl_{ticker}.csv"
        data.to_csv(merged_path, index=False)
        cur_dir_path = os.getcwd()
        full_path = os.path.join(cur_dir_path, merged_path)
        dict_csvs[merged_path] = full_path
        return merged_path


    print(f"Check for sec_xbrl_contexts_{ticker}.csv and sec_xbrl_facts_{ticker}.csv")


def main():
    csv_files = []
    
    csv_files, ticker = SS10K.main()
    ticker = ticker
    
    csvs_from_pwd(csv_files)
    print(dict_csvs)
    
    # Create the merged file
    merged_data = merge_CSV(ticker)
    
    # Now read it if it was created successfully
    if merged_data:
        df = pd.read_csv(merged_data)
        print(f"Columns: {df.columns.tolist()}")
    else:
        print("Warning: merge_CSV() returned None. Check if context/facts files exist.")
    
    return merged_data, ticker

if __name__ == "__main__":
    main()

