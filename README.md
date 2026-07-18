## Dockerized ETL for Extraction, Parsing & Reconstruction from SEC EDGAR 10K Filings

**Overview of the ETL**

The ETL was inspired by my internship experience as an Accounting Assistant at Cadillac (Automotive Distribution Center). 
As an Accounting Assistant I supported ERP-based financial reporting, compliance controls, and structured enterprise data workflows with local ERP software (1C), building and reviewing audit trails, SOC1 internal reporting style process.
I also analyzed balance sheets, income statements, and cash flow statements monthly and quarterly fluxes. 

This project began as an initiative to deepen my understanding of financial reporting processes and controls by leveraging my technical skills to build an ETL for financial data processing and analysis. 

**The ETL converts US GAAP data into the key financial statements: the balance sheet, income statement, and cash flow statement, using the company ticker and year as input parameters.**

**ETL Structure**

The only script the user needs to run is the 10K_ETL_main.py.

The script will run through each module of the pipeline in order.

**The first module of the pipeline is the *Scrape_Parse_10K_W1.py*:**

- It scrapes 10K filings from the SEC EDGAR website as .xml files, these docs are the initial raw data obtained
- This data is located inside of the *xml_docs_W1 directory*.

These initial files are the instance doc, eg. *a10-k20199282019_htm.xml*
As well as the calculations, definitions, labels and pre .xmls:

eg.

  *aapl-20190928_cal.xml, aapl-20190928_def.xml, aapl-20190928_lab.xml, aapl-20190928_pre.xml*

- It parses and standardizes the .xml documents into readable csv format: *SEC_contextRefs_{ticker}.csv, sec_xbrl_content_{ticker}.csv, sec_xbrl_contexts_{ticker}.csv, sec_xbrl_facts_{ticker}.csv, sec_xbrl_values_{ticker}.csv*
- This data is stored inside of the *parsed_xbrl_data* directory

eg.
   
   *SEC_contextRefs_aapl.csv, sec_xbrl_content_aapl.csv, sec_xbrl_contexts_aapl.csv, sec_xbrl_facts_aapl.csv, sec_xbrl_values_aapl.csv*

**The second module of the pipeline is the *Merge_Filing_Data_W2.py*:**

- This module aggregates (or merges) the data from the *parsed_xbrl_data* into a unified file *merged_sec_xbrl_{ticker}.csv*, for easy handling in the next phase of the pipeline
- The new file is stored in the *merged_data_W2* directory

eg.

  *merged_sec_xbrl_aapl.csv*

**The third module of the pipeline is the *Sort_10K_by_Context_W3.py*:**

- This module is framework that achieves to segregate the data into three parts: data that composes the balance sheet, data that composes the income and cashflow statements, and miscellaneous data that does not belong to either
- In order to accomplish this the module leverages the meta-structure of the XBRL files organization to group data

How Data is Sorted:
- Each financial label and value, eg. *label: OtherAccruedLiabilitiesCurrent	value: 12,443,000,000* is associated with a context reference such as *c-12*
- Here I made a critical assumption that data entries which are associated with the same context reference, are related  - probably belonging to the same financial statement or was collected in the same way - i.e instance data vs periodic data
- The module groups data entries together if they are associated with the same context reference, thus is the first level of aggregation
- The data takes this form:

{ contextRef_1 : [(label_11, value_11), (label _12, value_12), …, (label _1n, value_1n)],
  contextRef_2 : [(label _21, value_21), (label _22, value_22), …, (label _2n, value_2n)],
  …,
  contextRef_n : [(label _n1, value_n1), (label _n2, value_n2), …, (label _nn, value_nn)]
}

- The next level of aggregation involves iterating through groupings of labels that belong to the different context references to check if any two groupings have the same labels, if this is case these groupings are merged:

Given: (contextRef_1, [(label_11, value_11), (label _12, value_12), …, (label _1n, value_1n)]) and (contextRef_2, [(label _21, value_21), (label _22, value_22), …, (label _2n, value_2n)])
- If any label from contextRef_1 matches at least one label from contextRef_2, the datasets are merged into one set:

The new merged dataset: (contextRef_1- contextRef_2, [(label_11, value_11), (label _12, value_12), …, (label _1n, value_1n), (label _21, value_21), (label _22, value_22), …, (label _2n, value_2n)])

- Note that the values are converted to integers, this allows the data to be properly consolidated. Specifically, in each dataset if there are entries with the same label, the values are summed

Generating Reference Data for Sorting and ML-based Classification:
- The first sets of data generated from this module was manually evaluated, to verify whether the approach taken yielded any meaningful results
- For each set keyed with a context reference label (contextRef_i-...-contextRef_j for some values i and j) only the sets with more than 10 (label, value) pairs were considered, considering the size of the key financial statements
- Through a rigorous process of open coding, relying on credible resources such as Deloitte's DART (https://dart.deloitte.com), FASB (https://asc.fasb.org) and PwC's Viewpoint (https://viewpoint.pwc.com), the datasets were evaluated and manually annotated to produce two primary reference data sets
- After manual annotation it was found that the method used in this module effectively categorized the data into two main sets: a set of data for the balance sheet and a set of data containing data for both the income statement and the cashflow statement
- The original manually annotated datasets became references for training and validation sets for ML-based annotation in the next module in the pipeline

The reference data for the balance sheet: *bal_sheet_example.csv*
- This csv contains the label and value columns, and the category column - which was manually annotated
- In the category column each entry corresponding to a label and value was annotated with one of the following: current assets, noncurrent assets, current liabilities, noncurrent liabilities, equity, subtotal assets, subtotal liabilities, total assets, total liabilities and equity, or disclosures

The reference data for the income and cashflow statements: *income_&_cashflow_example.csv*
- This csv contains label	and value columns, and the	statement, category	and comments columns - which were manually annotated
- In the statement column each entry corresponding to a label and value was annotated with either income or cashflow to indicate belonging to either the income statement or cashflow statement
- In the category column each entry corresponding to a label and value was annotated with categories subdividing the income and cashflow statements
- If annotated to belong to the income statement, the category could be one of the following: Comprehensive income, Dividends, EBT, Earnings per share, Expenses, Gross profit, Income tax, Net income, Nonoperating expenses, Nonoperating income, Operating Expenses, Operating Income, Revenue
- If annotated to belong to the cashflow statement, the category could be one of the following: Disclosures, Financing activities, Investing activities, Operating activities, Other

- The sorted data resulting from this module is stored in the *sorted_inc&cf_bal_data_W3* directory:
- Given that the framework of this module effectively produced balance sheet data (*bal_sheet_{ticker}_data.csv*) and income and cashflow statement data (*inc_cf_{ticker}_data.csv*), it was used to streamline the sorting of data from the last module into two main sets: the balance sheet data and the income and cashflow statements data

eg. *bal_sheet_aapl_data.csv, inc_cf_aapl_data.csv*

- The data which did not have any structural relationship to the other two sets, either through common context references or through common labels, was aggregated in a separate csv as data which would require manual consolidation

eg. *meta_data.csv*

**The fourth module of the pipeline is the ML_Sort_10K_W4.py:**

- In this module ML models were used to annotate the datasets produced by the last module, using the the reference datasets for training and validation:

Annotating the balance sheet data with ML-based classifiers:
- *bal_sheet_example.csv* is the reference dataset used for training to annotate *bal_sheet_{ticker}_data.csv*, to produce *ml_bal_sheet_{ticker}_data.csv*
- *bal_sheet_{ticker}_data.csv* contains label and value columns
- *ml_bal_sheet_{ticker}_data.csv* has the category column, which is annotated based on the reference dataset

Categorizing data into income statement vs cashflow statement data and annotating the categories for each statement dataset:
- *income_&_cashflow_example.csv* is the reference dataset used for training to annotate *inc_cf_{ticker}.csv*, to produce *ml_inc_cf_{ticker}.csv*
- *inc_cf_{ticker}.csv* contains label and value columns
- *_inc_cf_{ticker}.csv* has the statement and category columns, which are annotated based on the reference dataset
- *ml_inc_cf_{ticker}.csv* data was separated into two csvs based on the statement column annotation: if "income" -> _ml_inc_{ticker}.csv_, if "cashflow" -> _ml_cf_{ticker}.csv_

ML Feature Engineering (Simple) & Classifiers:
- TF-IDF is used fo simple and efficient vectorization of labels - for feature engineering
- LogisticRegression classifier was used for binary categorization for the statement type in the *ml_inc_cf_{ticker}.csv*
- For annotating the category columns in both the *ml_bal_sheet_{ticker}_data.csv* and *inc_cf_{ticker}.csv* datasets, the same training, validation and testing framework was used, leveraging multiple classifiers: LogisticRegression, MultinomialNB, and the DecisionTreeClassifier
- The classifiers were first trained and validated in a 70% and 30% split on the reference datasets, then the best classifier was chosen based on the validation results, trained on the full dataset and used to categorize the actual data

Inside of the *ml_bal_sheet_{ticker}_data.csv ml_inc_{ticker}.csv, and ml_cf_{ticker}.csv*, the proper organization of entries within the financial statements is imitated by placing items of the same category together and ordering by size of value 

Prior to initiating the workflow of this module, the user is prompted to enter the minimum confidence threshold score, a decimal value between 0 and 1.
- In the process of classifying data when the confidence of the classification for an entry falls below the confidence threshold assigned by the user, this entry is flagged
- Low confidence entries are printed in the console and stored in separate csv files for manual review: *uncertain_bal_sheet_{ticker}.csv, uncertain_inc_cf_{ticker}.csv*

The datasets produced in this module are stored in the *ml_classified_inc_cf_bal_data_W4* directory:

eg. *ml_bal_sheet_aapl_data.csv, ml_cf_aapl.csv, ml_inc_cf_aapl.csv, ml_inc_aapl.csv, uncertain_bal_sheet_aapl.csv, uncertain_inc_cf_aapl.csv*

**The fifth module of the pipeline is the NLP_Classifier_W5.py:**

ML Feature Engineering (complex) & CLustering:
- BERT-based Sentence Transformers embeddings - for feature engineering
- KMeans Clustering - for discovery of groupings based on the embeddings

- We refer to the ML methods used in this module as NLP-based because the main strength of the workflow comes from the use of Sentence Transformer embeddings, an ML method commonly associated with NLP domain
  
- In this module Sentence Transformer model 'all-MiniLM-L6-v2', is used to create semantically meaningful embeddings based on the training datasets produced by the last module
- In this case the model has not been fine-tuned using the dataset available
- An improvement to the quality of embeddings would be to fine-tune the embedding model using the trianing data set
 
- Instead if classification, KMeans clustering is used to naturally discover categories - this technique is based on grouping labels together based on the embeddings
- Using this approach (unsupervised learning), was hypothesized to be better approach given that the training dataset is incomplete
- Useful if it is not possible to guarantee that the training dataset of possible financial labels is inexhaustive
- The assumption made with choosing clustering is that the data set has incomplete labels and incomplete categories
- Generally, KMeans clustering approach was chosen over classification methods because there is a possibility that not only are there labels that are not covered in the training data, but there is possibility that there are categories that are not covered by the training data
- The training data is randomly sampled and aggregated finacial labels of SEC 10-K filings of several companies, across the past 20 years
- The labels were seprataed into balance sheet vs income statement and cashflow statement (aggregated in same file) files. For each file the entries (labels) were then annotated with statement type and category, manually via research-assisted open-coding process

**Why use KMeans over K-NN,	SVM, or	Random Forest?**

| Criterion | K-NN | SVM | Random Forest | KMeans |
|-----------|------|-----|---------------|--------|
| **Handles unseen labels?** | ❌ No | ❌ No | ❌ No | ✅ Yes |
| **Leverages embedding geometry?** | ⚠️ Partial (distance-based) | ❌ No (hyperplane splits) | ❌ No (tree splits) | ✅ Yes (centroid distance) |
| **Requires complete label set?** | ✅ Yes | ✅ Yes | ✅ Yes | ❌ No |
| **Confidence scoring?** | ⚠️ K-vote only | ❌ No | ❌ No | ✅ Yes (distance to centroid) |
| **Self-learning (pseudo-labeling)?** | ❌ Expensive retraining | ❌ Expensive retraining | ❌ Expensive retraining | ✅ Incremental updates |
| **Scalable to many labels?** | ⚠️ O(n) lookup | ❌ O(n) support vectors | ❌ Retraining required | ✅ O(k) where k = clusters |
| **Interpretability** | ⚠️ Low | ⚠️ Low | ✅ High | ✅ High (semantic clusters) |

- If a reasonale guarantee could have been made that the training data categry labels set is complete then SVM would be a better choice

| Criterion | Scenario: Incomplete Labels | Scenario: Fixed, Complete Labels |
|-----------|----------------------------|----------------------------------|
| **Best algorithm** | ✅ KMeans | ✅ SVM (or Random Forest) |
| **Reasoning** | No category ground truth; need to discover structure | Clear categories; need to learn boundaries |
| **Unseen label handling** | Maps to nearest cluster (semantic discovery) | Maps to most confident class (discriminative decision) |
| **Self-learning** | Incremental cluster refinement | Requires full retraining |
| **Assumption** | "Data naturally clusters" | "Categories are linearly separable (with kernel)" |

**Data Processed in this Module:**

Original datasets:
original_train_bal = 'bal_sheet_example.csv'
original_train_inc_cf = 'income_&_cashflow_example.csv'

Datasets enriched with maximum confidence predictions:
learned_bal = "learned_trainset_bal.csv"
learned_inc_cf = "learned_trainset_inc_cf.csv"

Annotating the balance sheet data with NLP-based classifiers:
- *bal_sheet_example.csv* is the reference dataset used for training to annotate *bal_sheet_{ticker}_data.csv*, to produce *nlp_bal_sheet_{ticker}_data.csv*
- *bal_sheet_{ticker}_data.csv* contains label and value columns
- *nlp_bal_sheet_{ticker}_data.csv* has the category column, which is annotated based on the reference dataset

Categorizing data into income statement vs cashflow statement data and annotating the categories for each statement dataset:
- *income_&_cashflow_example.csv* is the reference dataset used for training to annotate *inc_cf_{ticker}.csv*, to produce *ml_inc_cf_{ticker}.csv*
- *inc_cf_{ticker}.csv* contains label and value columns
- *_inc_cf_{ticker}.csv* has the statement and category columns, which are annotated based on the reference dataset
- *nlp_inc_cf_{ticker}.csv* data was separated into two csvs based on the statement column annotation: if "income" -> _nlp_inc_{ticker}.csv_, if "cashflow" -> _nlp_cf_{ticker}.csv_

Clustering-based Classification:
- Simple clustering using KMeans of tags into groupings relying on accuracy of embeddings produced by Sentence Transformers

Prior to initiating the workflow of this module, the user is prompted to enter the minimum confidence threshold score - a decimal value between 0 and 1, and a maximum confidence threshold - a decimal value between 1 and minimum confidence threshold
- In the process of classifying data when the confidence of the classification for an entry falls below the confidence threshold assigned by the user, this entry is flagged
- Low confidence entries are printed in the console and stored in separate csv files for manual review: *uncertain_bal_sheet_{ticker}.csv, uncertain_inc_cf_{ticker}.csv*
- In the process of classifying data when the confidence of the classification for an entry falls below the confidence threshold assigned by the user, this entry is flagged
- High confidence entries are appended to the _learned_trainset_bal.csv_ and _learned_trainset_inc_cf.csv_ - the model uses its own high confidence predictions data that it generated to retrain itself for better future predictons. Essentially, this allows the model to learn. This fine-tunes the model on the data.

The datasets produced in this module are stored in the *nlp_classified_inc_cf_bal_data_W5* directory:

eg. *nlp_bal_sheet_aapl_data.csv, nlp_cf_aapl.csv, nlp_inc_cf_aapl.csv, nlp_inc_aapl.csv, uncertain_bal_sheet_aapl.csv, uncertain_inc_cf_aapl.csv*

**Run ETL**

Clone the repo:

```bash
git clone git@github.com:puganinithepug/10K_ETL.git
cd 10K_ETL
```

**Run ETL With Docker**

Before running this project with Docker, make sure you have:
- **Docker installed** on your machine: https://docs.docker.com/engine/install/

- _Docker daemon running_
  - On macOS/Windows: Open Docker Desktop
  - On Debian Linux: Run `sudo dockerd` or `sudo systemctl start docker`

 1.  _Build the image:_
   ```bash
   docker build -t my-etl-app .
  ```

 2. _Run the container:_
   ```bash
   docker run -it my-etl-app
  ```

3. Enter the filing details when prompted:
   
   Company ticker: eg. AAPL
   
   Year: eg. 2020
   
   The console will display notifications about the progression of the workflow through modules W1 to W3.
4. Once the data has been stored and sorted, reaching the end of W3, before W4 begins the user will be prompted to enter the confidence threshold:

   Confidence threshold (0.0-1.0): eg. 0.5

   The data requiring manual review will be printed in the console in addition to being saved to its corresponding directory.

**Alternatively Run ETL Without Docker**

 _Prerequisites - No Docker_
- Make sure you have all required modules installed (as specified in requirements.txt doc)

1. Run the pipeline:

   └─$ python3 10K_ETL_main.py
   
2. Follow steps 3 and 4 from _Run Dockerized ETL_

See ETL_Example_Run file to see an example of what to expect after running python3 10K_ETL_main.py. Alternatively see 10K_ETL_main.ipynb for another example.

**What Needs to Be Improved:**
- **The issue:** confidence levels are consistently under 50% for many labels. Low confidence suggests the pre-trained embeddings aren't capturing your financial domain well enough.
- Siamese netwrks for fine-tuning si one way to address the issue
- However, it is important to consider multiple causes to the symptom, and therefore examine multiple solution options besides Siamese network-based fine-tuning

| **Issue** | **Underlying Cause** | **Solution** |
|-----------|-------------------|------------|
| **Pre-trained embeddings don't fit financial semantics** | `all-MiniLM-L6-v2` trained on generic web text, not domain-specific financial language | Fine-tune Siamese network on financial label pairs (50–200+ pairs of similar/dissimilar labels) |
| **KMeans hyperparameter K is off** | More financial categories exist in production data than in training dataset; fixed K doesn't adapt | Use elbow method or silhouette score to find optimal K; consider **hierarchical clustering** for variable cluster counts; or implement hierarchical clustering instead of KMeans for variable cluter counts |
| **Label ambiguity during manual coding** | Financial labels are inherently overlapping; it was hard to categorize the labels manually during open-coding | Accept ambiguity in embedding space; use soft clustering (Gaussian Mixture Model) instead of hard KMeans; lower confidence thresholds to capture borderline cases in `uncertain_*.csv`; retrain on high-confidence pseudo-labels |


**Other Minor Improvement**
- Add high confidence predicted categorized labels to the training datasets
- Fine-tune sentence tranformer model using the training dataset for better embeddings
- Convert balance sheet, income statement and cashflow statement csvs into standard tabular format (as it usually appears in formal financial documentation)
