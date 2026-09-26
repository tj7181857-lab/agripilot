# AgriPilot – AI-Powered Multilingual Crop Health & Farm Advisory System
## Mid-Semester Project Presentation (10 Slides)
**Degree:** B.Tech in Artificial Intelligence & Data Science  
**Student Name:** Tushar Manohar Jadhav  
**Institute:** Vishwakarma Institute of Technology (VIT Pune)  
**Project Category:** Machine Learning & Applied AI System  
**Evaluation Stage:** Mid-Semester Evaluation  

---

## Slide Overview & Summary Table

| Slide # | Slide Title | Key ML / Engineering Focus |
|:---:|:---|:---|
| **1** | Title Slide | Project identity, credentials, BTech AI & DS mid-sem context |
| **2** | Problem Statement & Context | Smallholder challenges: soil matching, disease diagnosis, language barrier |
| **3** | Project Objectives | ML objectives (models, Grad-CAM) vs. Application objectives (profiles, records) |
| **4** | System Architecture | End-to-end dataflow: Farmer & Analyst roles, ML inference, SQLite storage |
| **5** | Datasets & Preprocessing | 2,200-sample soil dataset (22 crops) & 330-image disease dataset (11 classes) |
| **6** | Machine Learning Methodology | Multi-model crop selection & MobileNetV2 transfer learning with Grad-CAM |
| **7** | Current Evaluation & Results | Verified benchmark metrics: Random Forest (99.55%), Disease Classifier (87.88%) |
| **8** | Application Workflow & Farmer Interface | User onboarding, farm profile isolation, multilingual advisory, SQLite history |
| **9** | Current Limitations & Challenges | Critical mid-sem appraisal: distribution shift, crop coverage, OCR absence |
| **10** | Future Work & End-Semester Roadmap | 6 actionable milestones: field data, OOD rejection, OCR pipeline, validation |

---

## Slide 1: Title Slide

### AgriPilot: AI-Powered Multilingual Crop Health & Farm Advisory System
**A Practical Machine Learning Framework for Site-Specific Agriculture**

#### Key Project Metadata
* **Student Name:** Tushar Manohar Jadhav
* **Program:** Bachelor of Technology (B.Tech)
* **Specialization:** Artificial Intelligence & Data Science
* **Institution:** Vishwakarma Institute of Technology (VIT Pune)
* **Project Type:** Machine Learning & Web-Integrated Farm Advisory System
* **Evaluation Level:** Mid-Semester Project Evaluation

#### System Highlights at Mid-Semester Stage
* **Crop Recommendation:** Multi-class classification based on soil minerals (N, P, K) and agro-climatic parameters.
* **Crop Disease Identification:** Deep transfer learning classifier for leaf pathology diagnosis.
* **Visual Interpretability:** Integrated Gradient-weighted Class Activation Mapping (Grad-CAM) to localize diseased leaf lesions.
* **Farmer-Centric Software Stack:** Role-based access control (Farmer vs. Analyst), isolated SQLite farm records, and tri-lingual support (English, Hindi, Marathi).

```
+-----------------------------------------------------------------------------------+
|                                     AGRIPILOT                                     |
|           Mid-Semester Evaluation - B.Tech Artificial Intelligence & Data Science  |
|                               VIT Pune - Academic Year 2025-2026                  |
+-----------------------------------------------------------------------------------+
```

> **Speaker Notes (Slide 1):**  
> *"Good morning, respected evaluators. My name is Tushar Manohar Jadhav, and I am presenting our mid-semester B.Tech project in Artificial Intelligence and Data Science at VIT Pune, titled 'AgriPilot – AI-Powered Multilingual Crop Health & Farm Advisory System'.  
> AgriPilot is an applied machine learning project designed to assist smallholder farmers with scientific crop selection and rapid leaf disease detection. At this mid-semester milestone, we have built and validated the core machine learning pipelines, integrated visual interpretability using Grad-CAM, and deployed a functional web application with multilingual support and persistent farm record management. I will now walk you through our problem context, methodology, experimental results, current limitations, and end-semester roadmap."*

---

## Slide 2: Problem Statement & Practical Context

### Understanding Smallholder Agricultural Bottlenecks

#### Practical Challenges in Indian Farming
* **Sub-optimal Crop Choice:** Farmers frequently rely on traditional habits rather than soil nutrient chemistry (N, P, K, pH) and rainfall conditions, causing yield loss and soil degradation.
* **Delayed Disease Diagnosis:** Visual leaf pathology requires expert agronomic inspection. In rural areas, plant pathologists are inaccessible, leading to delayed or incorrect fungicide spraying.
* **Linguistic Accessibility Barrier:** Most modern digital advisory systems are English-only or provide complex technical terminology that does not resonate with regional farmers.
* **Fragmented Historical Records:** Farmers lack simple, persistent mechanisms to record past soil tests, disease occurrences, and seasonal interventions.
* **The "Black-Box" ML Gap:** Standard computer vision classifiers output raw class labels without visual justification, making it difficult for farmers and extension workers to trust predictions.

```
+-----------------------------------------------------------------------------------+
|                             PROBLEM STATEMENT DEFINITION                          |
|                                                                                   |
|  "To design, develop, and evaluate an accessible, machine learning-driven farm    |
|   advisory system that delivers data-backed crop recommendations from soil-weather |
|   parameters, provides interpretable leaf disease diagnosis via Grad-CAM, and      |
|   maintains isolated, multilingual farm records within a lightweight interface."  |
+-----------------------------------------------------------------------------------+
```

> **Speaker Notes (Slide 2):**  
> *"In rural agricultural practices, critical farming decisions—such as what crop to sow or how to treat a diseased leaf—are often made without timely scientific guidance. While soil health cards exist, translating N-P-K values and rainfall forecasts into the optimal crop is not straightforward. Furthermore, when fungal or bacterial diseases strike, local farmers often wait days for agricultural extension officers or apply generic chemical sprays indiscriminately.  
> Existing software solutions often fail because they are monolingual, treat machine learning models as opaque black boxes, and do not track individual farm history. Our problem statement focuses on bridging this gap by uniting supervised crop recommendation, interpretable leaf disease classification using Grad-CAM, and a multilingual, profile-isolated web application."*

---

## Slide 3: Project Objectives

### Clear Separation of Machine Learning vs. Application Scope

#### Machine Learning Objectives
1. **Soil-Driven Crop Recommendation Model:** Train and benchmark multi-class classifiers (Decision Tree, Random Forest, Gradient Boosting) on 7 environmental and chemical features to recommend optimal crops.
2. **Transfer Learning for Disease Classification:** Implement a deep convolutional neural network (MobileNetV2) to classify crop leaf pathologies across held-out test splits.
3. **Model Explainability via Grad-CAM:** Formulate Gradient-weighted Class Activation Mapping to highlight specific leaf regions responsible for the disease classification, providing visual auditing.
4. **Offline Evaluation Artifacts:** Persist trained bundles (`.joblib`, `.keras`) and comprehensive metrics JSONs to decouple training from real-time inference.

#### Application & Software Engineering Objectives
1. **Strict Multi-Tenant Farm Isolation:** Implement session-based authentication in SQLite ensuring each farmer exclusively accesses their own farm profile, plots, and prediction history.
2. **Multilingual Farmer Interface:** Provide seamless switching between English, Hindi (हिंदी), and Marathi (मराठी) across input forms, advisories, and prediction logs.
3. **Analyst Analytics Portal:** Provide a dedicated analyst dashboard exposing dataset statistics, per-class model evaluation metrics, and system-wide activity aggregates.

```
                                  AGRIPILOT OBJECTIVES
               +---------------------------+---------------------------+
               |   Machine Learning Scope  |     Application Scope     |
               +---------------------------+---------------------------+
               | * 7-Feature Crop Modeling | * Multi-user Auth & Roles |
               | * MobileNetV2 Vision      | * Isolated Farm History   |
               | * Grad-CAM Visual Heatmaps| * English / Hindi / Mar.  |
               | * Benchmark Comparison    | * Analyst Metrics Portal  |
               +---------------------------+---------------------------+
```

> **Speaker Notes (Slide 3):**  
> *"To ensure a rigorous project execution, we have clearly divided our objectives into Machine Learning milestones and Software Application milestones.  
> On the ML side, our focus is twofold: first, benchmarking tree-based classifiers for 7-parameter crop recommendation, and second, training a lightweight transfer learning vision model paired with Grad-CAM for explainable disease detection.  
> On the engineering side, our primary objective is practical usability: ensuring strict data isolation so no farmer sees another's private farm data, supporting native Marathi and Hindi alongside English, and building an analyst module for project-level inspection of model artifacts."*

---

## Slide 4: Proposed System Architecture

### Multi-Tier Architecture: Presentation, Processing, ML Inference & Persistence

```
+---------------------------------------------------------------------------------------+
|                                  USER / ROLE LAYER                                    |
|         [ Farmer User ]                                     [ Agronomist / Analyst ]   |
+---------------------------------------------------------------------------------------+
                                           |
                                           v
+---------------------------------------------------------------------------------------+
|                         FLASK APPLICATION & ROUTING LAYER                             |
|  - Session-Based Authentication (Password Hashing via Werkzeug)                       |
|  - Role-Based Access Control: `/dashboard` vs. `/analyst/dashboard`                   |
|  - Multilingual Localization Handler (English | Hindi | Marathi)                       |
+---------------------------------------------------------------------------------------+
            |                                           |                   |
            v                                           v                   v
+-----------------------+                   +-----------------------+  +----------------+
|  CROP RECOMMENDATION  |                   |   LEAF DISEASE SCAN   |  |  FARM RECORDS  |
|  ENGINE               |                   |   & GRAD-CAM PIPELINE |  |  & ADVISORY    |
+-----------------------+                   +-----------------------+  +----------------+
| * Input Validator     |                   | * Image Preprocessor  |  | * Farm Profile |
|   (N, P, K, pH, etc.) |                   |   (224x224 RGB)       |  | * Plot Details |
| * Scikit-Learn Bundle |                   | * MobileNetV2 Model   |  | * Rule Engine  |
|   (Random Forest)     |                   | * Grad-CAM Generator  |  | * Weather Ctx. |
| * Class Probabilities |                   |   (Target: Conv_1)    |  | * History Log  |
+-----------------------+                   +-----------------------+  +----------------+
            |                                           |                   |
            +---------------------+---------------------+                   |
                                  |                                         |
                                  v                                         v
+---------------------------------------------------------------------------------------+
|                                PERSISTENCE & ARTIFACT LAYER                           |
|  SQLite Database: `users`, `farms`, `farm_crops`, `recommendations`, `disease_scans`  |
|  Model Artifacts: `crop_recommender_bundle.joblib`, `disease_model.keras`             |
|  Evaluation Stores: `crop_model_comparison.json`, `disease_model_metrics.json`        |
+---------------------------------------------------------------------------------------+
```

#### Layer Responsibilities
* **Client Layer:** Responsive HTML5/CSS/JavaScript UI designed for mobile and desktop screens.
* **Controller Layer:** Flask API endpoints managing authentication, parameter extraction, and role enforcement.
* **ML Inference Service:** In-memory cached models performing instant sub-second predictions without reloading weights.
* **Persistence Layer:** Relational SQLite database with foreign-key constraints guaranteeing farm data isolation.

> **Speaker Notes (Slide 4):**  
> *"This slide illustrates the architectural design of AgriPilot. The system separates the Farmer experience from the Analyst experience.  
> When a farmer logs in, their session is authenticated, and all requests are filtered by their unique user ID. If they request crop recommendations, the data passes through our input validation module into our cached Scikit-Learn ensemble model. If they upload a leaf photo, the image is resized to 224x224 and fed into our MobileNetV2 network; simultaneously, the target convolutional gradients are calculated to generate a Grad-CAM overlay.  
> All prediction outcomes are written into our SQLite database under that farmer's private history. Meanwhile, analysts log in to a dedicated portal that directly inspects aggregate activity and saved model evaluation artifacts."*

---

## Slide 5: Datasets and Data Processing

### Real Experimental Datasets & Preprocessing Pipelines

#### Dataset 1: Soil-Climate Crop Recommendation
* **Source & Size:** Standard agricultural benchmark dataset containing **2,200 verified records**.
* **Input Feature Space (7 Dimensions):**
  * Soil Nutrients: Ratio of Nitrogen ($N$), Phosphorus ($P$), and Potassium ($K$) in kg/ha
  * Environmental Factors: Temperature ($^\circ\text{C}$), Relative Humidity ($\%$), and Rainfall ($\text{mm}$)
  * Chemical Factor: Soil $\text{pH}$ level ($0 - 14$ scale)
* **Target Classes (22 Crops):** Apple, Banana, Blackgram, Chickpea, Coconut, Coffee, Cotton, Grapes, Jute, Kidneybeans, Lentil, Maize, Mango, Mothbeans, Mungbean, Muskmelon, Orange, Papaya, Pigeonpeas, Pomegranate, Rice, Watermelon.
* **Train/Test Split:** 80% Training ($1,760$ samples) and 20% Held-Out Testing ($440$ samples) with stratified splitting (`random_state=42`).

#### Dataset 2: Leaf Disease Pathology Dataset
* **Input Modality:** RGB leaf photographs resized to $224 \times 224 \times 3$ pixels.
* **Dataset Volume:** **330 labeled images** split into **264 training images** and **66 held-out test images**.
* **Scope & Coverage (11 Classes across 3 Crops):**
  * **Grape:** Black rot, Esca (Black Measles), Leaf blight (Isariopsis), Healthy
  * **Potato:** Early blight, Late blight, Healthy
  * **Tomato:** Bacterial spot, Early blight, Late blight, Healthy
* **Preprocessing Pipeline:** Image normalization ($[0, 1]$ rescaling), channel verification, and mini-batch tensor structuring.

```
CROP RECOMMENDATION DATASET (2,200 SAMPLES)       DISEASE IMAGE DATASET (330 IMAGES)
+-------------------+--------------------+       +-------------------+--------------------+
| 1,760 Train (80%) | 440 Held-Out (20%) |       |  264 Train (80%)  |  66 Held-Out (20%) |
+-------------------+--------------------+       +-------------------+--------------------+
        7 Input Features -> 22 Crops                  3 Crops (Grape, Potato, Tomato) -> 11 Classes
```

> **Speaker Notes (Slide 5):**  
> *"Let us examine the datasets utilized in our machine learning pipelines. We strictly use genuine dataset-backed sources.  
> For crop recommendation, we use 2,200 soil-climatic samples comprising 7 continuous features: Nitrogen, Phosphorus, Potassium, Temperature, Humidity, Soil pH, and Rainfall. The dataset covers 22 distinct crops and is split 80:20 into 1,760 training and 440 testing samples.  
> For disease classification, our mid-sem dataset consists of 330 curated images spanning 11 disease and healthy states across 3 crops: Grape, Potato, and Tomato. We allocate 264 images for training and 66 images for held-out evaluation. We emphasize that our model's disease detection capability is currently bounded by these 11 classes, and expanding crop coverage is a key objective for the final semester."*

---

## Slide 6: Machine Learning Methodology

### Two Specialized Pipelines: Tabular Ensemble & Explainable Vision

```
A) CROP RECOMMENDATION PIPELINE
[Soil N, P, K + Temp, Humidity, pH, Rain]
   |
   v
[Feature Validation & Range Checks]
   |
   v
[Multi-Algorithm Benchmarking: Decision Tree vs. Random Forest vs. Gradient Boosting]
   |
   v
[Hyperparameter Tuning & Stratified Evaluation on 440 Samples]
   |
   v
[Serialized Model Bundle (.joblib) -> Probabilistic Crop Prediction]
```

```
B) CROP DISEASE CLASSIFICATION & EXPLAINABILITY PIPELINE
[Input Leaf Photo (RGB)] -> [Resize 224x224x3 & Rescale [0, 1]]
   |
   v
[MobileNetV2 Feature Extractor (Pretrained on ImageNet)]
   |
   v
[Global Average Pooling -> Dense Classifier (11 Classes, Softmax)]
   |
   +---------------------------------------+
   |                                       |
   v                                       v
[Disease Class & Confidence]     [Grad-CAM Gradients @ 'Conv_1']
                                           |
                                           v
                                 [Class Activation Heatmap]
                                           |
                                           v
                                 [Visual Overlay on Leaf Image]
```

#### Technical Implementation Details
* **Crop Models Explored:** Evaluated Decision Tree, Random Forest (100 estimators), and Gradient Boosting. Ensemble bagging proved most resilient against high humidity-temperature collinearity.
* **Explainability via Grad-CAM:** Backpropagates the class score gradient to the final convolutional feature map (`Conv_1` in MobileNetV2), computing channel importance weights to generate a spatial attention heatmap.

> **Speaker Notes (Slide 6):**  
> *"Our ML methodology is split into two specialized pipelines.  
> In Pipeline A, tabular soil and climatic parameters are checked for boundary validity and passed into our multi-model training harness. We benchmarked Decision Tree, Random Forest, and Gradient Boosting. The best-performing model is serialized into a standalone joblib bundle for production inference.  
> In Pipeline B, we employ MobileNetV2 via transfer learning. MobileNetV2 was chosen for its parameter efficiency, making it suitable for edge and low-power server deployment. Instead of delivering an unverified prediction, we pass the gradients from our target convolutional layer, 'Conv_1', to compute a Grad-CAM heatmap. This highlights the exact visual lesions on the leaf that influenced the model's decision, providing farmers and evaluators with visual evidence rather than a blind label."*

---

## Slide 7: Current Model Evaluation & Results

### Verified Experimental Benchmark Metrics from Project Artifacts

#### Crop Recommendation Model Comparison ($N = 440$ Held-Out Test Samples)

| Machine Learning Model | Test Accuracy | Macro Precision | Macro Recall | Macro F1-Score | Training Time | Inference Time | Top Contributing Feature |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Decision Tree** | 97.95% | 98.10% | 97.95% | 97.94% | 0.010 s | 0.0008 s | Rainfall (30.4%) |
| **Random Forest (Selected)** | **99.55%** | **99.57%** | **99.55%** | **99.55%** | **0.223 s** | **0.1052 s** | **Humidity (22.8%)** |
| **Gradient Boosting** | 99.09% | 99.15% | 99.09% | 99.09% | 11.069 s | 0.0183 s | Humidity (24.1%) |

* *Finding:* Random Forest achieved the highest generalization performance with an F1-score of 99.55%, effectively balancing moisture and rainfall splits across all 22 crop classes.

#### Leaf Disease Classifier Benchmark (MobileNetV2, $N = 66$ Held-Out Test Images)

| Metric | Measured Value | Mid-Semester Benchmark Context |
|:---|:---:|:---|
| **Correct Predictions** | **58 / 66** | Evaluated on unseen test images across 11 classes |
| **Overall Test Accuracy** | **87.88%** | 87.88% held-out validation accuracy |
| **Macro-Averaged Precision** | **89.73%** | High true-positive rate across all 11 pathologies |
| **Macro-Averaged Recall** | **87.88%** | Sensitive detection across blight and healthy samples |
| **Macro-Averaged F1-Score** | **87.97%** | Harmonized metric across balanced class splits |

```
+-----------------------------------------------------------------------------------+
|                           CRITICAL EVALUATION NOTE                                |
|  "These performance numbers represent evaluation on our curated held-out test     |
|   split. They serve as a benchmark baseline and must NOT be interpreted as a     |
|   guarantee of 88% accuracy under unconstrained, real-world field conditions."    |
+-----------------------------------------------------------------------------------+
```

> **Speaker Notes (Slide 7):**  
> *"Slide 7 presents our actual, unembellished mid-semester evaluation metrics stored in our project artifacts.  
> For crop recommendation, evaluated on 440 held-out samples, Random Forest achieved an accuracy of 99.55% and an F1-score of 99.55%, outperforming Decision Tree at 97.95% and Gradient Boosting at 99.09%. Both Random Forest and Gradient Boosting identified relative humidity and rainfall as top predictive features.  
> For leaf disease classification, our MobileNetV2 model correctly identified 58 out of 66 held-out test images, yielding an overall accuracy of 87.88% and a macro F1-score of 87.97%.  
> As a matter of technical integrity, we explicitly note that these metrics reflect controlled test conditions and do not represent a blanket performance guarantee on arbitrary, noisy field photographs."*

---

## Slide 8: Application Workflow & Farmer Interface

### Practical Farmer Experience & Data Isolation

```
NEW FARMER ONBOARDING FLOW
[Register Account] -> [Set Language: EN/HI/MR] -> [Create Farm Profile: Name, Area, Soil, Irrigation]
                                                              |
                                                              v
RETURNING FARMER WORKFLOW <---------------------+             |
[Secure Login]                                  |             |
   |                                            |             |
   v                                            |             |
[Dashboard: View Active Farm & Soil Context]    |             |
   |                                            |             |
   +------------------------+-------------------+             |
   |                        |                                 |
   v                        v                                 v
[Crop Recommendation]    [Leaf Disease Scanner]     [Multilingual Assistant]
- Optional Soil N-P-K    - Upload Leaf Photo        - Context-Aware Guidance
- Contextual Weather     - Instant Inference        - Plain Language (No Jargon)
- Model Prediction       - Grad-CAM Heatmap         - Advisory Log
   |                        |                                 |
   +------------------------+---------------------------------+
                            |
                            v
               [Persist to SQLite Database]
               - Filtered strictly by `user_id`
               - Retrievable in Farm History Log
```

#### Core Design & Usability Decisions
* **No Fabricated Soil Values:** If a farmer has not performed a laboratory soil test, the system does not invent artificial N-P-K values; it clearly indicates missing parameters.
* **Strict Session Isolation:** Implemented via Flask secure cookies; querying `/api/records` only retrieves records matching the authenticated user's ID.
* **Multilingual Localization:** Dynamic client rendering in English, Hindi, and Marathi ensures accessibility for non-English-literate farmers.

> **Speaker Notes (Slide 8):**  
> *"This slide demonstrates how AgriPilot functions in practice.  
> When a new farmer registers, they specify their regional language and configure their farm profile—including plot size, location, soil category, and irrigation infrastructure. When a returning farmer logs in, their profile is automatically retrieved from SQLite.  
> A core ethical design choice we made is never fabricating chemical soil test numbers. If a farmer does not know their exact Nitrogen or Phosphorus levels, our system does not guess; it prompts them to input known parameters or consult nearby testing facilities.  
> Once a crop recommendation or leaf scan is executed, the results—including the Grad-CAM visualization—are saved directly to that farmer's private history. Strict foreign-key validation ensures complete data isolation between different farmers."*

---

## Slide 9: Current Limitations & Technical Challenges

### Critical Mid-Semester Appraisal (Areas Identified for Improvement)

#### 1. Constrained Disease Category Coverage
* The vision classifier is currently trained on **11 specific classes across 3 crops** (Grape, Potato, Tomato). Diseases outside this scope cannot be recognized.

#### 2. Domain Shift in Field Photography
* The held-out test accuracy of 87.88% was evaluated on standardized benchmark images. Real field photographs introduce complex backgrounds, variable sunlight, shadows, water droplets, and leaf occlusion, degrading classification confidence.

#### 3. Out-of-Distribution (OOD) Rejection Absence
* The mid-sem pipeline lacks a robust novelty detection mechanism. Uploading non-leaf images (e.g., soil, weeds, random objects) currently yields a forced prediction among the 11 classes rather than triggering a graceful rejection.

#### 4. Manual Soil Data Entry Bottleneck
* Farmers currently must manually enter N, P, K, and pH values. Many smallholders find it difficult to read laboratory soil test cards without guidance.

#### 5. Rule-Based Advisory Limitations
* The multilingual assistant provides curated advisory responses, but lacks deep retrieval over dynamic local market prices and real-time pesticide availability.

```
+-----------------------------------------------------------------------------------+
|                              MID-SEMESTER STATUS                                  |
|   "We view these limitations not as project shortcomings, but as clearly defined  |
|    technical challenges established during mid-sem development that provide       |
|    an objective, quantifiable roadmap for our final semester implementation."     |
+-----------------------------------------------------------------------------------+
```

> **Speaker Notes (Slide 9):**  
> *"In any genuine engineering evaluation, identifying limitations is as vital as showcasing successes. At this mid-semester stage, we have recognized five specific limitations.  
> First, our disease model is restricted to 11 classes across 3 crops. Second, test accuracy on curated images does not account for the domain shift caused by real-world field lighting, mud spots, and camera angles. Third, our system currently lacks out-of-distribution rejection: uploading a non-leaf photo will force a prediction rather than throwing an error.  
> Fourth, requiring manual data entry for soil values is a friction point for farmers who cannot easily interpret laboratory cards. And fifth, our agricultural advisory is currently template-driven. These are precisely the engineering challenges we are targeting for our end-semester phase."*

---

## Slide 10: Future Work & End-Semester Roadmap

### Structured Milestones Toward Final Submission

```
MILESTONES FOR END-SEMESTER COMPLETION
+-----------------------------------------------------------------------------------+
| Month 1: Dataset Expansion & Robustness                                           |
| - Expand disease dataset with diverse field images under variable lighting        |
| - Introduce image augmentation: contrast jitter, motion blur, affine transforms   |
+-----------------------------------------------------------------------------------+
| Month 2: OOD Filtering & Automated Ingestion                                      |
| - Implement Out-of-Distribution (OOD) filter to reject non-leaf uploads           |
| - Build OCR extraction pipeline (Tesseract/EasyOCR) for printed Soil Health Cards |
+-----------------------------------------------------------------------------------+
| Month 3: Advisory Scaling, Edge Optimization & Field Pilot                        |
| - Expand crop portfolio to regional staples: Cotton, Rice, Maize, Sugarcane       |
| - Quantize MobileNetV2 model (TFLite) for rapid, low-bandwidth edge inference     |
| - Conduct structured usability testing with local farmers in Maharashtra          |
+-----------------------------------------------------------------------------------+
```

#### Final Summary of Current Status
* **Current Status:** Core machine learning pipelines (tabular + vision + Grad-CAM) and multilingual web application fully implemented and integrated.
* **Final Deliverable:** Robust field-validated system with automated soil OCR, out-of-distribution rejection, and expanded regional crop coverage.

```
+-----------------------------------------------------------------------------------+
|  "AgriPilot demonstrates a functional, interpretable machine learning foundation   |
|   at mid-semester; our end-semester focus is on field robustness and usability."  |
+-----------------------------------------------------------------------------------+
```

### Thank You!
**Questions & Technical Discussion**  
*Tushar Manohar Jadhav | B.Tech Artificial Intelligence & Data Science | VIT Pune*

> **Speaker Notes (Slide 10):**  
> *"To conclude our mid-semester presentation, this roadmap charts our trajectory for the final semester submission.  
> In our first phase, we will expand our image dataset with challenging field samples and synthetic augmentations to close the domain gap. In the second phase, we will implement an out-of-distribution detection layer so the scanner rejects non-leaf images, and integrate an OCR pipeline to extract N-P-K parameters directly from photographed Soil Health Cards.  
> In the final phase, we will extend crop coverage to staple Maharashtra crops like Cotton and Sugarcane, optimize our model for low-bandwidth mobile execution, and conduct pilot user tests with farmers.  
> In summary, AgriPilot has a fully functional core ML and application integration today, with a clear engineering path toward end-sem completion. Thank you, and I look forward to your valuable feedback and questions."*

---
