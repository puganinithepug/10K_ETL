#!/usr/bin/env python
# coding: utf-8

# In[1]:


import csv
import pprint
import pathlib
import collections
# instead of beautiful soup parsing
# API for parsing and creating XML data
import xml.etree.ElementTree as ET

import lxml.etree as ETL

import requests

import argparse


# build SEC url
# BASE = "https://data.sec.gov/submissions/"
# THIS IS FOR META
# NEED TO REBUILD BASE DYANMICALLY
# need to parse args.htm for name, contained in the link "meta-20250630_htm.xml"
# grab name
# get cik from name 
# need also accession number
# build base from cik and accession nummber
# use the resulting base 
# dynamically obtaining base 

# map ticker to CIK
TICKER_JSON = "https://www.sec.gov/files/company_tickers.json"

# get accession number from cik
SUB_URL = "https://data.sec.gov/submissions/"

#BASE = "https://www.sec.gov/Archives/edgar/data/1326801/000162828025036791"
BASE = "https://www.sec.gov/Archives/edgar/data/"

#reusable header for everywhere so website allows you to pass without seeming a bot
HEADERS_URL = {
    "User-Agent": "MyResearchBot/1.0 (contact: myemail@example.com)",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive"}

parse = ['label', 'labeLink', 'labelArc', 'loc', 'definitionLink', 'definitionArc', 'calculationArc']


def parse_args():
    parser = argparse.ArgumentParser(
        description="Fetch SEC XMLs"
    )
    # parser.add_argument("--htm", help="EXTRACTED XBRL INSTANCE DOCUMENT eg meta-20250630_htm.xml", default=None) # meta-20250630_htm.xml
    # parser.add_argument("--cal", help="XBRL TAXONOMY EXTENSION CALCULATION LINKBASE DOCUMENT", default=None) # meta-20250630_cal.xml
    # parser.add_argument("--lab", help="XBRL TAXONOMY EXTENSION LABEL LINKBASE DOCUMENT", default=None) # meta-20250630_lab.xml
    # parser.add_argument("--defi", help="XBRL TAXONOMY EXTENSION DEFINITION LINKBASE DOCUMENT", default=None) # meta-20250630_def.xml
    parser.add_argument("--ticker", help="Company ticker", default=None)
    parser.add_argument("--date", help="Date", default=None)
    # Accept unknown args
    args, _ = parser.parse_known_args()

    # Prompt user interactvely if missing arguments
    if not args.ticker:
        args.ticker = input("Company ticker")
        args.date = input("Date")
        # args.htm = input("EXTRACTED XBRL INSTANCE DOCUMENT eg meta-20250630_htm.xml").strip()
        # args.cal = input("XBRL TAXONOMY EXTENSION CALCULATION LINKBASE DOCUMENT eg meta-20250630_cal.xml").strip()
        # args.lab = input("XBRL TAXONOMY EXTENSION LABEL LINKBASE DOCUMENT eg meta-20250630_lab.xml").strip()
        # args.defi = input("XBRL TAXONOMY EXTENSION DEFINITION LINKBASE DOCUMENT eg meta-20250630_def.xml").strip()
    return args

# part of process is to create set of unique keys
# set obj to house info
# lookup benefit times vs use of list
# plus sets ensur eonly unique values, no duplicates
# create 2 sets to store keys

# go from company ticker to CIK
# since ticker is the probable prefix
def get_cik_from_ticker(first_arg: str) -> str:
    # ticker obtainable from prefix of args.htm or any other
    dash_index = first_arg.find('-')
    if dash_index != -1:  # Check if a dash exists
        prefix = first_arg[:dash_index]
        print(prefix)
    url = TICKER_JSON
    data = requests.get(url, headers=HEADERS_URL).json()
    for entry in data.values():
        # get json mapping from SEC and search of company ticker
        if entry['ticker'].lower() == prefix.lower():
            # fetch CIK
            cik = str(entry['cik_str']).zfill(10)
            print(f"Found CIK {cik} for ticker {prefix}")
            return cik
    raise ValueError(f"Ticker {prefix} not found in SEC database")

# if date is specified grab accession number for that date
# if date not specified then does recent
def get_accession_for_date(cik, filing_date=None):
    cik_str = str(cik).zfill(10)
    full_url = f"{SUB_URL}CIK{cik_str}.json"
    data = requests.get(full_url, headers=HEADERS_URL).json()

    if filing_date:  # Find accession for the exact date
        for i, date in enumerate(data["filings"]["recent"]["filingDate"]):
            if date == filing_date:
                accession_number = data["filings"]["recent"]["accessionNumber"][i]
                print("Accession number:", accession_number)
                return accession_number
        # If we got here, date not found
        raise ValueError(f"No filing found for date {filing_date}")
    else:  # Just get the latest filing
        accession_number = data["filings"]["recent"]["accessionNumber"][0]
        print("Accession number:", accession_number)
        return accession_number


def get_base_url (cik, accession_num):
    cik_no_zeros = str(int(cik))  # remove leading zeros for EDGAR folder
    acc_no_no_dashes = accession_num.replace("-", "")
    url = f"{BASE}{cik_no_zeros}/{acc_no_no_dashes}"
    return url


#can loop through each file
# P3
# del if breaks
def parse_linkbases(files_list, parse_tags):

    # list
    storage_list = []

    # dictionary 
    storage_values= {}

    # another dictionary
    storage_gaap = {}

    for file in files_list:

        #print(file)
        # that returns first item in file tuple, which is a list
        # we want to access file so we do files_list[0]
        # i.e file_cal for instance

        # parse file
        tree = ET.parse(file.file_path)
        # create element tree
        # print(tree)

        # grab all namespace_elements in tree
        elements = tree.findall(file.namespace_element)
        # will return all elements that match this: 
        # http://www.xbrl.org/2003/linkbase)calculationLink namespace
        #print(elements)

        # loop through each element
        # loop through child elements
        # P4
        for element in elements:
            # create iterator
            # loop through child element of each element
            for child_element in element.iter():

                #print(child_element)
                # get elements and their children from document
                # next is getting attributes of elements
                element_split_label = child_element.tag.split("}")
                # print(element_split_label)
                # want to remove the redundant prefix on label:
                # {http://www.xbrl.org/2003/linkbase}
                # get parts of label
                namespace = element_split_label[0]
                label = element_split_label[1]
                # is this label we want?
                # wanted labels in parse
                if label in parse:
                    element_type_label = file.namespace_label + "_" + label
                    #print(element_type_label)

                    # define dictionary
                    dict_storage = {}
                    dict_storage["item_type"] = element_type_label

                    # get attribute keys
                    cal_keys = child_element.keys()
                    # print(cal_keys)

                    for key in cal_keys:
                        if "}" in key:
                            new_key = key.split("}")[1]
                            dict_storage[new_key] = child_element.attrib[key]
                        else:
                            dict_storage[key] = child_element.attrib[key]
                    #print(dict_storage)

                    # choosing master key to be the label document
                    # could choose anything else - experimental
                    if element_type_label == "label_label":
                        key_store = dict_storage["label"]

                        # create master key
                        master_key = key_store.replace("lab_", "")

                        # split master key
                        label_split = master_key.split("_")

                        #a
                        # create gaap id
                        gaap_id =  label_split[0] + ";" + label_split[1]
                        #print(label_split)
                        # there are duplicates
                        # thats why we put it in a dicionary - unique key to value
                        # dict for xml files
                        storage_values[master_key] = {}
                        # dictionary storage values is created with the master key

                        storage_values[master_key]["label_id"] = key_store
                        storage_values[master_key]["location_id"] = key_store.replace("lab_", "loc_")
                        storage_values[master_key]["us_gaap_id"] = gaap_id
                        storage_values[master_key]["us_gaap_values"] = None
                        storage_values[master_key][element_type_label] = dict_storage
                        #b is a subdictiory of a
                        # dict for only values related to GAAP
                        storage_gaap[gaap_id] = {}
                        storage_gaap[gaap_id]["id"] = gaap_id
                        storage_gaap[gaap_id]["master_id"] = master_key
                        # a and b should be merged
                        # master keys created in big dictiory
                        # master key associated with smaller dictiory for GAAP stuff exclusively, organized as in b
            # add to dict
            storage_list.append([file.namespace_label, dict_storage])
            # parsing the html file with nonNumeric and nonFractional stuff
            # parse 10Q file
            # load file_htm
    # del if breaks
    return storage_list, storage_values, storage_gaap

# del if breaks
def parse_instance_doc(file_htm, storage_values, storage_list, storage_gaap):        
        tree = ET.parse(file_htm)
        # Process nonNumeric elements
        for element in tree.iter():
            #print(element.attrib)
            if "nonNumeric" in element.tag or "nonFractional" in element.tag:
                # get attribute name and master id
                attr_name = element.attrib["name"]
                gaap_id = storage_gaap[attr_name]["master_id"]

                storage_gaap[attr_name]["context_ref"] = element.attrib["contextRef"]
                storage_gaap[attr_name]["context_id"] = element.attrib["id"]
                storage_gaap[attr_name]["continued_at"] = element.attrib.get("continuedAt", "null")
                storage_gaap[attr_name]["escape"] = element.attrib.get("escape", "null")
                storage_gaap[attr_name]["format"] = element.attrib.get("format", "null")
                storage_gaap[attr_name]["unit_ref"] = element.attrib.get("unitRef", "null")
                storage_gaap[attr_name]["decimals"] = element.attrib.get("decimals", "null")
                storage_gaap[attr_name]["scale"] = element.attrib.get("scale", "null")
                storage_gaap[attr_name]["format"] = element.attrib.get("format", "null")
                storage_gaap[attr_name]["value"] = element.text.strip() if element.text else "null"

                if gaap_id in storage_values:
                    storage_values[gaap_id]["us_gaap_value"] = storage_gaap[attr_name]             

def write_csv(storage_list, storage_values):
    # create csv
    file_name = "sec_xbrl_scrape_content.csv"

    with open(file_name, mode = "w", newline = "") as sec_file:
        #create writer
        writer = csv.writer(sec_file)
        # write the header
        # pass to the row writer the list of things to go into the header
        writer.writerow(["FILE", "LABEL", "VALUE"])
        # dump dict into csv
        for dict_cont in storage_list:
            # write row by row the things stored inside the storage list
            # the first is the namespace label
            # the second item is the actual dict
            for item in dict_cont[1].items():
                # second item is list of lists
                # grab items per each item
                writer.writerow([dict_cont[0]] + list(item))

    # create csv
    file_name = "sec_xbrl_scrape_values.csv"

    with open(file_name, mode = "w", newline = "") as sec_file:
        writer = csv.writer(sec_file)
        writer.writerow(["ID", "CATEGORY", "LABEL", "VALUE"])
        for storage1 in storage_values:
            # storage1 are keys to the values extracted from the second level dict
            # the .items() call enumerates values in dict
            for storage2 in storage_values[storage1].items():
                # extract by key the value
                # the value might be another dict because elements can have child elements
                if isinstance(storage2[1], dict): # check if it is
                    for storage3 in storage2[1].items():
                        # write to csv
                        writer.writerow([storage1] + [storage2[0]] + list(storage3))
                else:
                    if storage2[1] != None:
                        #write to csv, if storage2 is not a dictionry (we dont go to storage3)
                        writer.writerow([storage1] + [storage2] + ["None"])
# main workflow
def main():

    # call parser
    args = parse_args()

    # results are args.ticker and args.date
    # check if date is present

    # if user doesnt provide date, we automate to grab most recent
    # if user does provide date then we search for that

    # get cik
    cik = get_cik_from_ticker(args.ticker)

    # get accession number
    accession_num = get_accession_num(cik, args.date)

    # build url
    base_url = get_base_url (cik, accession_num)

    # here we go look for xml files
    # either for specified date or for most recent
    # file for htm.xml stored in htm
    # file for cal.xml stored in cal
    # file for def.xml stored in defi



    # populate fmap
    fmap = {
    "XBRL_INSTANCE_DOCUMENT" : htm,  #"meta-20250630_htm.xml": "meta-20250630_htm.xml",
    "CALCULATION_LINKBASE" : cal,  # "meta-20250630_cal.xml": "meta-20250630_cal.xml",
    "LABEL_LINKBASE" : lab,  #"meta-20250630_lab.xml": "meta-20250630_lab.xml",
    "DEFINITION_LINKBASE" : defi # "meta-20250630_def.xml": "meta-20250630_def.xml",
    }

    # define working directory
    # obj stores cur directory
    # joining with a folder containing downloaded documents
    # later should replace with scraping
    # assumes folder exists, builds path to that folder
    sec_directory = pathlib.Path.cwd().joinpath("folder_to_store_xml_docs")
    sec_directory.mkdir(parents=True, exist_ok=True)

    for fname, tail in fmap.items():
        fpath = sec_directory / tail
        if not fpath.exists():
            try:
                response = requests.get(f"{base_url}/{tail}", headers=HEADERS_URL)
                #response = requests.get(f"{BASE}/{tail}", headers = HEADERS_URL)
                response.raise_for_status()
                fpath.write_bytes(response.content)
                print(f"Downloaded: {tail}")
            except requests.exceptions.RequestException as e:
                print(f"Error downloading {tail}: {e}")
        else:
            print(f"Already exists: {fname}")

    # P1
    # define file paths to documents
    # taken straight from data files
    # in this case for meta
    # https://www.sec.gov/Archives/edgar/data/1326801/000162828025036791/0001628280-25-036791-index.htm
    # the code just builds a file path to the files in the folder, assumes they are already there
    # so they should b placed there already for this to work

    # this has to be changed to be appropriate for vars rather than args
    file_htm = sec_directory.joinpath(args.htm).resolve() # htm
    file_cal = sec_directory.joinpath(args.cal).resolve() # calculation
    file_lab = sec_directory.joinpath(args.lab).resolve() # label
    file_def = sec_directory.joinpath(args.defi).resolve() # definition

    # create constructor for named tuple object type
    FilingTuple = collections.namedtuple("FilingTuple", ["file_path", "namespace_element", "namespace_label"])
    # create 3 of those each with a doc that will be parsed
    # file path already defined in P1, name space element, name space label
    # link to an online thing

    files_list = [
        FilingTuple(file_cal, '{http://www.xbrl.org/2003/linkbase}calculationLink', 'calculation'),
        FilingTuple(file_def, '{http://www.xbrl.org/2003/linkbase}definitionLink', 'definition'),
        FilingTuple(file_lab, '{http://www.xbrl.org/2003/linkbase}labelLink', 'label')
    ]

    # label categories
    #avoid = ['linkbase', 'roleRef'] # labels without relevant info
    # labelArc points to next element you want

#this returns 3 things, how do i store them separately
    storage_list, storage_values, storage_gaap = parse_linkbases(files_list, parse)
    parse_instance_doc(file_htm, storage_values, storage_list, storage_gaap)
    write_csv(storage_list, storage_values)

if __name__ == "__main__":
    main()         


# In[ ]:





# In[ ]:




